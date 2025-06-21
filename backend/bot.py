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
        self.qty_precision = 3 # BTCUSDT는 0.001 단위
        self.min_qty = 0.001
        self.leverage = 125
        self.running = False
        self.trade_logs = ["🤖[봇초기화]🤖 리스크 관리 + 진입 신호 상세 기록"]
        self.balance = 50.0
        self.TAKE_PROFIT = 0.005
        self.STOP_LOSS   = -0.002
        self.position = 0      # 1:롱, -1:숏, 0:무포지션
        self.entry_price = None
        self.last_qty = 0
        self.last_signal = 0
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
        usdt = max(self.balance * 0.1, 2.0)
        raw_qty = usdt / price
        qty = max(round(raw_qty, self.qty_precision), self.min_qty)
        return qty

    def check_entry_signal(self, df):
        willr = float(df['Willr'].iloc[-1])
        rsi = float(df['RSI'].iloc[-1])
        vol = float(df['Volume'].iloc[-1])
        vol_ma = float(df['Vol_MA5'].iloc[-1])
        if (willr < -80) and (rsi < 36) and (vol > vol_ma * 1.05):
            return 1
        elif (willr > -20) and (rsi > 64) and (vol > vol_ma * 1.05):
            return -1
        else:
            return 0

    def start(self):
        self.running = True
        self.trade_logs.append("[시작] 전략 봇 가동 (상태/진입불가 사유/에러 모두 기록)")

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
            rsi   = float(df['RSI'].iloc[-1])
            vol   = float(df['Volume'].iloc[-1])
            vol_ma= float(df['Vol_MA5'].iloc[-1])
            now_signal = self.check_entry_signal(df)
            now = time.time()

            if self.position == 0:
                cond1 = now_signal != 0
                cond2 = now_signal != self.last_signal
                cond3 = (now - self.last_trade_time > 300)
                entry_reasons = []
                if cond1 and cond2 and cond3:
                    qty = self._calc_qty(current_price)
                    if qty < self.min_qty:
                        msg = f"[진입실패] 최소 수량({self.min_qty}) 미만. 계산수량: {qty:.6f}"
                        if len(self.trade_logs)==0 or self.trade_logs[-1] != msg:
                            self.trade_logs.append(msg)
                    else:
                        self._enter_position("LONG" if now_signal == 1 else "SHORT", current_price, qty)
                        self.last_signal = now_signal
                        self.last_trade_time = now
                else:
                    if not cond1:
                        entry_reasons.append("3중 신호 미충족")
                        entry_reasons.append(
                            f"→ Willr={willr:.1f}{' OK' if (willr < -80 or willr > -20) else ' X'}, "
                            f"RSI={rsi:.1f}{' OK' if (rsi < 36 or rsi > 64) else ' X'}, "
                            f"Vol/MA5={vol:.2f}/{vol_ma:.2f}{' OK' if (vol > vol_ma*1.05) else ' X'}"
                        )
                    if not cond2:
                        entry_reasons.append("바로 직전 신호와 중복 (중복진입 방지)")
                    if not cond3:
                        entry_reasons.append("최근 거래 이후 5분 미경과 (쿨다운중)")
                    msg = "[대기] 진입불가: " + ", ".join(entry_reasons)
                    if len(self.trade_logs)==0 or self.trade_logs[-1] != msg:
                        self.trade_logs.append(msg)
            else:
                # 포지션 있을 때도 항상 대기로그
                position_name = "LONG" if self.position == 1 else "SHORT"
                status_msg = (
                    f"[대기] {position_name} 포지션 유지중 - 진입불가, "
                    f"entry {self.entry_price:.2f} 현재가 {current_price:.2f} TP:{self.TAKE_PROFIT*100:.2f}% SL:{self.STOP_LOSS*100:.2f}%"
                )
                if len(self.trade_logs)==0 or self.trade_logs[-1] != status_msg:
                    self.trade_logs.append(status_msg)

            # 롱 청산 조건
            if self.position == 1:
                pnl = (current_price - self.entry_price) / self.entry_price
                close_signal = (now_signal == -1 and self.last_signal == 1)
                if pnl >= self.TAKE_PROFIT or pnl <= self.STOP_LOSS or close_signal:
                    self._close_position(current_price, pnl, self.last_qty)
                    self.last_trade_time = now
                    if close_signal:
                        qty = self._calc_qty(current_price)
                        if qty >= self.min_qty:
                            self._enter_position("SHORT", current_price, qty)
                            self.last_signal = -1
                            self.last_trade_time = now
                        else:
                            self.trade_logs.append(f"[진입실패] 반전 숏 최소수량 미만: {qty:.6f}")
                    else:
                        self.last_signal = 0

            # 숏 청산 조건
            if self.position == -1:
                pnl = (self.entry_price - current_price) / self.entry_price
                close_signal = (now_signal == 1 and self.last_signal == -1)
                if pnl >= self.TAKE_PROFIT or pnl <= self.STOP_LOSS or close_signal:
                    self._close_position(current_price, pnl, self.last_qty)
                    self.last_trade_time = now
                    if close_signal:
                        qty = self._calc_qty(current_price)
                        if qty >= self.min_qty:
                            self._enter_position("LONG", current_price, qty)
                            self.last_signal = 1
                            self.last_trade_time = now
                        else:
                            self.trade_logs.append(f"[진입실패] 반전 롱 최소수량 미만: {qty:.6f}")
                    else:
                        self.last_signal = 0

            if self.balance <= 0:
                self.running = False
                self.trade_logs.append("[종료] 💀 잔고 소진 - 봇 자동 종료")
                break

            time.sleep(60)

        self.trade_logs.append("[종료] 봇 정지 끝")

    def stop(self):
        self.running = False
        self.trade_logs.append("[수동정지] 사용자 요청 봇 중지")

    def _enter_position(self, side, price, qty):
        try:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side="BUY" if side == "LONG" else "SELL",
                type="MARKET",
                quantity=qty
            )
            self.entry_price = price
            self.position = 1 if side == "LONG" else -1
            self.last_qty = qty
            self.trade_logs.append(f"[진입] {side} @ {price} / 수량: {qty:.4f}")
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
            self.trade_logs.append(f"[청산] {'LONG' if self.position == 1 else 'SHORT'} CLOSE @ {price}")
            self.trade_logs.append(f"[손익] {pnl*100:.2f}% ({self.leverage}배), {profit:.2f} → 잔고:{self.balance:.2f} USDT")
        except Exception as e:
            self.trade_logs.append(f"[청산실패] @ {price}: {e}")

        # 포지션 상태 초기화
        self.position = 0
        self.entry_price = None
        self.last_qty = 0
