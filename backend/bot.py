import os
import time
from dotenv import load_dotenv
from binance.client import Client
import pandas as pd
import ta
import joblib
import json

load_dotenv()

class BinanceBot:
    SYMBOL = "BTCUSDT"
    QTY_PRECISION = 3
    PRICE_PRECISION = 2
    MIN_QTY = 0.001
    LEVERAGE = 125
    FEE = 0.0004

    INIT_BALANCE = 50.0
    TP = 0.08   # 목표 8% 익절
    SL = -0.04  # 목표 4% 손절

    # AI 모델/피처 경로 설정 (bot.py 위치 기준)
    BASE_DIR = os.path.dirname(__file__)
    AI_MODEL_PATH = os.path.join(BASE_DIR, "ai_model", "ai_model.pkl")
    FEATURE_CONFIG_PATH = os.path.join(BASE_DIR, "ai_model", "feature_config.json")

    # 진입 조건 설정
    USE_RSI_FILTER = True
    RSI_ENTRY_LONG = 70
    RSI_ENTRY_SHORT = 30
    USE_WHALE_FILTER = False

    def __init__(self):
        # Binance 클라이언트 설정
        self.client = Client(
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_SECRET_KEY"),
            testnet=True
        )
        self.client.API_URL = os.getenv("BINANCE_BASE_URL")

        self.balance = self.INIT_BALANCE
        self.position = 0
        self.entry_price = None
        self.entry_commission = 0
        self.last_qty = 0
        self.running = False
        self.trade_logs = []

        # AI 모델 및 피처 리스트 로드
        if os.path.exists(self.AI_MODEL_PATH) and os.path.exists(self.FEATURE_CONFIG_PATH):
            try:
                self.AI_MODEL = joblib.load(self.AI_MODEL_PATH)
                with open(self.FEATURE_CONFIG_PATH) as f:
                    self.FEATURE_COLS = json.load(f)
                self._log("[설정] AI 모델 로드 성공")
            except Exception as e:
                self.AI_MODEL = None
                self.FEATURE_COLS = []
                self._log(f"[오류] AI 모델 로드 실패: {e}")
        else:
            self.AI_MODEL = None
            self.FEATURE_COLS = []
            self._log("[경고] AI 모델 또는 피처 파일 없음, AI 미사용")

        # 레버리지 설정
        try:
            self.client.futures_change_leverage(symbol=self.SYMBOL, leverage=self.LEVERAGE)
            self._log(f"[설정] 레버리지 {self.LEVERAGE}x 적용")
        except Exception as e:
            self._log(f"[오류] 레버리지 설정 실패: {e}")

    def _log(self, msg):
        t = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{t}] {msg}"
        print(entry)
        self.trade_logs.append(entry)

    def align_to_tick(self, price):
        return round(round(price / 0.1) * 0.1, self.PRICE_PRECISION)

    def start_bot(self):
        self.running = True
        self._log("봇 시작 🤖")
        while self.running:
            try:
                self._log("-- 새로운 사이클 --")

                # 데이터 로드 및 현재가 조회
                df = self._fetch_data()
                price = self.get_price()
                if df is None or price is None:
                    time.sleep(5)
                    continue

                # 주요 지표 계산 (소문자 컬럼 사용)
                rsi = df['rsi'].iloc[-1]
                vol = df['volume'].iloc[-1]
                vol_ma = df['vol_ma5'].iloc[-1]
                whale = vol > vol_ma * 1.03
                ai_sig = self.get_ai_signal(df)
                self._log(f"가격={price:.2f}, RSI={rsi:.2f}, vol={vol:.0f}, whale={'Y' if whale else 'N'}, AI_signal={ai_sig}")

                # 자동 TP/SL 체크
                if self.manage_position(price):
                    time.sleep(1)
                    continue

                # 진입 조건
                enter_long = (ai_sig == 1)
                enter_short = (ai_sig == -1)
                if self.USE_RSI_FILTER:
                    enter_long &= (rsi < self.RSI_ENTRY_LONG)
                    enter_short &= (rsi > self.RSI_ENTRY_SHORT)
                if self.USE_WHALE_FILTER:
                    enter_long &= whale
                    enter_short &= whale

                if enter_long and self.position <= 0:
                    if self.position == -1:
                        self.close_position(price, "신호 전환")
                    self._trade('BUY', price)
                elif enter_short and self.position >= 0:
                    if self.position == 1:
                        self.close_position(price, "신호 전환")
                    self._trade('SELL', price)

            except Exception as e:
                self._log(f"[오류] 루프 실행 중 예외: {e}")
            finally:
                time.sleep(5)

    def stop(self):
        self.running = False
        self._log("봇 정지")

    def _fetch_data(self, interval='1m', limit=100):
        try:
            klines = self.client.futures_klines(symbol=self.SYMBOL, interval=interval, limit=limit)
            df = pd.DataFrame(klines, columns=['ts','Open','High','Low','Close','Volume','ct','qv','t','tbv','tqv','ign'])
            # 컬럼명을 모두 소문자로 변환
            df.columns = [col.lower() for col in df.columns]
            # 필수 컬럼 타입 캐스팅
            df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].astype(float)
            # 지표 계산
            df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
            df['vol_ma5'] = df['volume'].rolling(5).mean()
            df.dropna(inplace=True)
            return df if not df.empty else None
        except Exception as e:
            self._log(f"[오류] 데이터 로드 실패: {e}")
            return None

    def get_ai_signal(self, df=None):
        if self.AI_MODEL is None or not self.FEATURE_COLS:
            return 0
        try:
            # 전달받은 df에서 바로 피처 추출
            features = df[self.FEATURE_COLS].iloc[-1:].reset_index(drop=True)
            return int(self.AI_MODEL.predict(features)[0])
        except Exception as e:
            self._log(f"[오류] AI 예측 실패: {e}")
            return 0

    def get_price(self):
        try:
            return float(self.client.futures_symbol_ticker(symbol=self.SYMBOL)['price'])
        except:
            return None

    def calc_max_qty(self, price):
        notional = self.balance * self.LEVERAGE
        qty = max(notional / price, self.MIN_QTY)
        return round(qty, self.QTY_PRECISION)

    def _trade(self, side, price):
        qty = self.calc_max_qty(price)
        if qty <= self.MIN_QTY:
            self._log(f"[경고] 최소 수량 미달: {qty}")
            return
        order_price = self.align_to_tick(price * (0.999 if side == 'BUY' else 1.001))
        try:
            self.client.futures_create_order(symbol=self.SYMBOL, side=side, type='LIMIT', timeInForce='GTC', price=order_price, quantity=qty)
            self.position = 1 if side == 'BUY' else -1
            self.entry_price = order_price
            self.last_qty = qty
            commission = order_price * qty * self.FEE / 2
            self.balance -= commission
            self._log(f"{side} 진입: 가격={order_price}, 수량={qty}, 수수료={commission:.4f}")
        except Exception as e:
            self._log(f"[오류] {side} 실패: {e}")

    def close_position(self, price, reason=""):
        side = 'SELL' if self.position == 1 else 'BUY'
        order_price = self.align_to_tick(price * (1.001 if side == 'SELL' else 0.999))
        try:
            self.client.futures_create_order(symbol=self.SYMBOL, side=side, type='LIMIT', timeInForce='GTC', price=order_price, quantity=self.last_qty)
            pnl_raw = ((order_price - self.entry_price) if self.position == 1 else (self.entry_price - order_price)) * self.last_qty
            commission = order_price * self.last_qty * self.FEE / 2
            net_pnl = pnl_raw - (self.entry_commission + commission)
            self.balance += net_pnl
            self._log(f"{side} 청산({reason}): 가격={order_price}, 순PnL={net_pnl:.4f}, 잔고={self.balance:.2f}")
        except Exception as e:
            self._log(f"[오류] 청산 실패: {e}")
        finally:
            self.position = 0
            self.entry_price = None
            self.entry_commission = 0
            self.last_qty = 0

    def manage_position(self, price):
        if self.position == 0:
            return False
        pnl_rate = (price - self.entry_price) / self.entry_price if self.position == 1 else (self.entry_price - price) / self.entry_price
        if pnl_rate >= self.TP:
            self.close_position(price, "TP")
            return True
        if pnl_rate <= self.SL:
            self.close_position(price, "SL")
            return True
        return False
