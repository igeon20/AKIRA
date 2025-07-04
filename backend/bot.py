import os
import time
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException
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
    TP = 0.08   # 목표 0.8% 익절
    SL = -0.04  # 목표 0.4% 손절

    BASE_DIR = os.path.dirname(__file__)
    AI_MODEL_PATH = os.path.join(BASE_DIR, "ai_model", "ai_model.pkl")
    FEATURE_CONFIG_PATH = os.path.join(BASE_DIR, "ai_model", "feature_config.json")

    USE_RSI_FILTER = True
    RSI_ENTRY_LONG = 70
    RSI_ENTRY_SHORT = 30
    USE_WHALE_FILTER = False

    def __init__(self):
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

        if os.path.exists(self.AI_MODEL_PATH) and os.path.exists(self.FEATURE_CONFIG_PATH):
            try:
                self.AI_MODEL = joblib.load(self.AI_MODEL_PATH)
                with open(self.FEATURE_CONFIG_PATH) as f:
                    self.FEATURE_COLS = json.load(f)
            except Exception:
                self.AI_MODEL = None
                self.FEATURE_COLS = []
        else:
            self.AI_MODEL = None
            self.FEATURE_COLS = []

        try:
            self.client.futures_change_leverage(symbol=self.SYMBOL, leverage=self.LEVERAGE)
        except Exception:
            pass

    def _log(self, msg):
        t = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{t}] {msg}"
        print(entry)
        self.trade_logs.append(entry)

    def align_to_tick(self, price):
        tick_size = 1 / (10 ** self.PRICE_PRECISION)
        return round(round(price / tick_size) * tick_size, self.PRICE_PRECISION)

    def start_bot(self):
        self.running = True
        self._log("봇 시작 🤖")
        while self.running:
            try:
                df = self._fetch_data()
                if df is None:
                    time.sleep(5)
                    continue

                price = self.get_price()
                if price is None:
                    time.sleep(5)
                    continue

                # RSI·Whale 필터, AI 시그널
                rsi = df['rsi'].iloc[-1]
                vol = df['volume'].iloc[-1]
                vol_ma = df['vol_ma5'].iloc[-1]
                whale = vol > vol_ma * 1.03
                ai_sig = self.get_ai_signal(df)

                # TP/SL 관리
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

                if enter_long and self.position == 0:
                    self._trade('BUY', price, '롱 진입')
                elif enter_short and self.position == 0:
                    self._trade('SELL', price, '숏 진입')

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
            df = pd.DataFrame(klines, columns=[
                'ts','open','high','low','close','volume','ct','qv','t','tbv','tqv','ign'
            ])
            df = df[['open','high','low','close','volume']].astype(float)
            df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
            df['vol_ma5'] = df['volume'].rolling(5).mean()
            df.dropna(inplace=True)
            return df
        except Exception:
            return None

    def get_ai_signal(self, df=None):
        if not getattr(self, 'AI_MODEL', None) or not self.FEATURE_COLS:
            return 0
        try:
            features = df[self.FEATURE_COLS].iloc[-1:].reset_index(drop=True)
            return int(self.AI_MODEL.predict(features)[0])
        except Exception:
            return 0

    def get_price(self):
        try:
            return float(self.client.futures_symbol_ticker(symbol=self.SYMBOL)['price'])
        except Exception:
            return None

    def calc_max_qty(self, price):
        notional = self.balance * self.LEVERAGE
        qty = max(notional / price, self.MIN_QTY)
        return round(qty, self.QTY_PRECISION)

    def _trade(self, side, price, label):
        qty = self.calc_max_qty(price)
        if qty <= self.MIN_QTY:
            return
        order_price = self.align_to_tick(price * (0.999 if side == 'BUY' else 1.001))
        try:
            # MARKET 주문으로 즉시 체결
            self.client.futures_create_order(
                symbol=self.SYMBOL,
                side=side,
                type='MARKET',
                quantity=qty
            )
            self.position = 1 if side == 'BUY' else -1
            self.entry_price = order_price
            self.last_qty = qty
            # 진입 수수료만 저장
            commission = order_price * qty * self.FEE / 2
            self.entry_commission = commission
            self._log(f"{label}: 가격={order_price}, 수량={qty}, 예상 수수료={commission:.4f}")
        except BinanceAPIException as e:
            if e.code != -2027:
                self._log(f"[오류] {label} 실패: {e}")

    def close_position(self, price, reason=""):
        if self.position == 0:
            return
        closing_label = '롱 청산' if self.position == 1 else '숏 청산'
        side = 'SELL' if self.position == 1 else 'BUY'
        try:
            self.client.futures_create_order(
                symbol=self.SYMBOL,
                side=side,
                type='MARKET',
                quantity=self.last_qty
            )
            executed_price = self.get_price()
            order_price = self.align_to_tick(executed_price)
            # PnL 계산
            if self.position == 1:
                raw_pnl = (order_price - self.entry_price) * self.last_qty
            else:
                raw_pnl = (self.entry_price - order_price) * self.last_qty
            closing_commission = order_price * self.last_qty * self.FEE / 2
            # 진입+청산 수수료를 합산 차감
            net_pnl = raw_pnl - (self.entry_commission + closing_commission)
            self.balance += net_pnl
            self._log(f"{closing_label}({reason}): 가격={order_price}, 순PnL={net_pnl:.4f}, 잔고={self.balance:.2f}")
        except BinanceAPIException as e:
            if e.code != -2027:
                self._log(f"[오류] {closing_label} 실패: {e}")
        finally:
            # 상태 초기화
            self.position = 0
            self.entry_price = None
            self.entry_commission = 0
            self.last_qty = 0

    def manage_position(self, price):
        if self.position == 0:
            return False
        # 현재 수익률(%)
        if self.position == 1:
            pnl_pct = (price - self.entry_price) / self.entry_price
        else:
            pnl_pct = (self.entry_price - price) / self.entry_price
        self._log(f"현재 PnL%: {pnl_pct:.4%} (TP {self.TP:.2%}, SL {self.SL:.2%})")
        # TP 또는 SL 조건
        if pnl_pct >= self.TP:
            self.close_position(price, "TP")
            return True
        if pnl_pct <= self.SL:
            self.close_position(price, "SL")
            return True
        return False
