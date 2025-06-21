import os
import time
from binance.client import Client
from dotenv import load_dotenv
import pandas as pd
import ta

load_dotenv()

class BinanceBot:
    def __init__(self):
        self.TESTNET_URL = os.getenv("BINANCE_BASE_URL")
        self.client = Client(
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_SECRET_KEY"),
            testnet=True
        )
        self.client.API_URL = self.TESTNET_URL

        self.symbol = "BTCUSDT"
        self.leverage = 125   # 실전 추천: 5~15배 사이
        self.running = False
        self.trade_logs = ["🪙🪙🪙🪙🪙"]
        self.balance = 50.0           # 시작 잔고  
        self.TAKE_PROFIT = 0.005      # 이익실현 (0.5%)
        self.STOP_LOSS   = -0.002     # 손실감내   (0.2%)
        self.position = 0             # 1:롱, -1:숏, 0:무포지션
        self.entry_price = None
        self.last_qty = 0
        self.last_signal = 0          # 1: long, -1: short, 0: 없음
        self.last_trade_time = 0

        try:
            self.client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)
            self.trade_logs.append(f"[설정] 레버리지 {self.leverage}배 적용 완료.")
        except Exception as e:
            self.trade_logs.append(f"[레버리지 실패] {e}")

    def fetch_ohlcv(self, interval="1m"):
        try:
            klines = self.client.futures_klines(symbol=self.symbol, interval=interval, limit=100)
            df = pd.DataFrame(klines, columns=[
                'timestamp','Open','High','Low','Close','Volume',
                'close_time','quote_vol','trades','taker_base_vol','taker_quote_vol','ignore'
            ])
            df[['Open','High','Low','Close','Volume']] = df[['Open','High','Low','Close','Volume']].astype(float)
            return df
        except Exception as e:
            self.trade_logs.append(f"[가격수집실패] {e}")
            return None

    def _calc_qty(self, price):
        usdt = max(self.balance * 0.1, 2.0)   # 가용잔고의 10% (최소2usdt)
        return round(usdt / price, 6)

    def check_entry_signal(self, df):
        willr = float(df['Willr'].iloc[-1])
        rsi = float(df['RSI'].iloc[-1])
        vol = float(df['Volume'].iloc[-1])
        vol_ma = float(df['Vol_MA5'].iloc[-1])
        # 롱: 강한 과매도+RSI과매도+거래량폭발
        if (willr < -80) and (rsi < 36) and (vol > vol_ma * 1.05):
            return 1
        elif (willr > -20) and (rsi > 64) and (vol > vol_ma * 1.05):
            return -1
        else:
            return 0

    def start(self):
        self.running = True
        self.trade_logs.append("[시작] 전략 봇 가동")

        while self.running:
            df = self.fetch_ohlcv()
            if df is None:
                time.sleep(10)
                continue

            df['Willr'] = ta.momentum.williams_r(df['High'], df['Low'], df['Close'], lbp=14)
            df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
            df['Vol_MA5'] = df['Volume'].rolling(5).mean()

            current_price = float(df['Close'].iloc[-1])
            willr = float(df['Willr'].iloc[-1])
            rsi = float(df['RSI'].iloc[-1])
            vol = float(df['Volume'].iloc[-1])
            vol_ma = float(df['Vol_MA5'].iloc[-1])
            now_signal = self.check_entry_signal(df)
            now = time.time()
            
            # ==== 진입 여부/불가 로그 ====
            if self.position == 0:
                cond1 = now_signal != 0
                cond2 = now_signal != self.last_signal
                cond3 = (now - self.last_trade_time > 300)
                entry_reasons = []
                if cond1 and cond2 and cond3:
                    qty = self._calc_qty(current_price)
                    self._enter_position("LONG" if now_signal == 1 else "SHORT", current_price, qty)
                    self.last_signal = now_signal
                    self.last_trade_time = now
                else:
                    # 조건별 상세사유 추가
                    if not cond1:
                        entry_reasons.append("3중 신호 미충족")
                        entry_reasons.append(
                            f"→ Willr={willr:.1f}{' OK' if (willr < -80 or willr > -20) else ' X'}, "
                            f"RSI={rsi:.1f}{' OK' if (rsi < 36 or rsi > 64) else ' X'}, "
                            f"VolCur/MA5={vol:.2f}/{vol_ma:.2f}{' OK' if (vol > vol_ma*1.05) else ' X'}"
                        )
                    if not cond2:
                        entry_reasons.append("바로 직전 신호와 중복 (중복진입 방지)")
                    if not cond3:
                        entry_reasons.append("최근 거래 이후 5분 미경과 (쿨타임중)")
                    msg = "[대기] 진입불가🥶🥶: " + ", ".join(entry_reasons)
                    if len(self.trade_logs)==0 or self.trade_logs[-1] != msg:
                        self.trade_logs.append(msg)

            # 포지션 롱 유지: TP/SL 혹은 명확 숏 반전 신호(3중)에서만 청산
            if self.position == 1:
                pnl = (current_price - self.entry_price) / self.entry_price
                close_signal = (now_signal == -1 and self.last_signal == 1)
                if pnl >= self.TAKE_PROFIT or pnl <= self.STOP_LOSS or close_signal:
                    self._close_position(current_price, pnl, self.last_qty)
                    self.last_trade_time = now
                    if close_signal:  # 진정 숏 반전 신호면 바로 반대 진입허용
                        qty = self._calc_qty(current_price)
                        self._enter_position("SHORT", current_price, qty)
                        self.last_signal = -1
                        self.last_trade_time = now
                    else:
                        self.last_signal = 0

            # 포지션 숏 유지: TP/SL 혹은 명확 롱 반전 신호(3중)에서만 청산
            if self.position == -1:
                pnl = (self.entry_price - current_price) / self.entry_price
                close_signal = (now_signal == 1 and self.last_signal == -1)
                if pnl >= self.TAKE_PROFIT or pnl <= self.STOP_LOSS or close_signal:
                    self._close_position(current_price, pnl, self.last_qty)
                    self.last_trade_time = now
                    if close_signal:
                        qty = self._calc_qty(current_price)
                        self._enter_position("LONG", current_price, qty)
                        self.last_signal = 1
                        self.last_trade_time = now
                    else:
                        self.last_signal = 0

            if self.balance <= 0:
                self.running = False
                self.trade_logs.append("💀 잔고0, 봇 종료")
                break

            time.sleep(60)

        self.trade_logs.append("[종료] 봇 정지")

    def stop(self):
        self.running = False
        self.trade_logs.append("[수동정지] 사용자 요청 봇 중지🥶🥶")

    def _enter_position(self, side, price, qty):
        try:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side="BUY" if side=="LONG" else "SELL",
                type="MARKET",
                quantity=qty
            )
            self.entry_price = price
            self.position = 1 if side == "LONG" else -1
            self.last_qty = qty
            self.trade_logs.append(f"[진입] {side} @ {price} / qty:{qty:.4f}")
            self.trade_logs.append(f"잔고: {self.balance:.2f} USDT")
        except Exception as e:
            self.trade_logs.append(f"[진입실패] {side} @ {price}: {e}")

    def _close_position(self, price, pnl, qty):
        side = "SELL" if self.position == 1 else "BUY"
        try:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side=side,
                type="MARKET",
                quantity=qty
            )
            profit = self.balance * (pnl * self.leverage)
            self.balance += profit
            self.trade_logs.append(f"[청산] {'LONG' if self.position==1 else 'SHORT'} CLOSE @ {price}")
            self.trade_logs.append(f"[손익] {pnl*100:.2f}% ({self.leverage}배), {profit:.2f} → 잔고:{self.balance:.2f} USDT")
        except Exception as e:
            self.trade_logs.append(f"[청산실패] @ {price}: {e}")
        # 포지션 및 잔상태 초기화
        self.position = 0
        self.entry_price = None
        self.last_qty = 0
