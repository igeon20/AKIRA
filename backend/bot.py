import os
import time
from dotenv import load_dotenv
from binance.client import Client
import pandas as pd
import numpy as np
import ta

load_dotenv()

class BinanceBot:
    SYMBOL = "BTCUSDT"
    QTY_PRECISION = 3
    PRICE_PRECISION = 2
    MIN_QTY = 0.001
    LEVERAGE = 125
    INIT_BALANCE = 50.0

    TP = 0.04
    SL = -0.02

    def __init__(self):
        self.client = Client(
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_SECRET_KEY"),
            testnet=True
        )
        self.client.API_URL = os.getenv("BINANCE_BASE_URL")

        self.symbol = self.SYMBOL
        self.qty_precision = self.QTY_PRECISION
        self.price_precision = self.PRICE_PRECISION
        self.min_qty = self.MIN_QTY
        self.leverage = self.LEVERAGE
        self.balance = self.INIT_BALANCE

        self.position = 0
        self.entry_price = None
        self.last_qty = 0
        self.entry_time = 0

        self.running = False
        self.trade_logs = []

        try:
            self.client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)
        except Exception as e:
            self._log(f"[레버리지 설정 실패] {e}")

    def _log(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log = f"[{timestamp}] {message}"
        print(log)
        self.trade_logs.append(log)

    def start_bot(self):
        self.running = True
        self._log("[봇 시작]")

        while self.running:
            df = self.fetch_data()
            if df is None:
                self._log("[경고] 데이터프레임 없음")
                time.sleep(5)
                continue

            signal = self.get_signal(df)
            current_price = self.get_price()
            self._log(f"[신호] {signal} / 현재가: {current_price}")

            if signal == 1 and self.position <= 0:
                self._log("[시도] 롱 진입")
                self.close_position(current_price)
                qty = self.calc_max_qty(current_price)
                self.enter_position("BUY", qty, current_price)
            elif signal == -1 and self.position >= 0:
                self._log("[시도] 숏 진입")
                self.close_position(current_price)
                qty = self.calc_max_qty(current_price)
                self.enter_position("SELL", qty, current_price)

            self.manage_position(current_price)
            time.sleep(5)

    def stop(self):
        self.running = False
        self._log("[봇 정지]")

    def fetch_data(self):
        try:
            klines = self.client.futures_klines(symbol=self.symbol, interval="1m", limit=100)
            df = pd.DataFrame(klines, columns=[
                'timestamp','Open','High','Low','Close','Volume',
                'close_time','quote_vol','trades',
                'taker_base_vol','taker_quote_vol','ignore'
            ])
            df[['Open','High','Low','Close','Volume']] = df[['Open','High','Low','Close','Volume']].astype(float)
            df['Willr'] = ta.momentum.williams_r(df['High'], df['Low'], df['Close'], lbp=14)
            df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
            df['Vol_MA5'] = df['Volume'].rolling(5).mean()
            return df
        except Exception as e:
            self._log(f"[데이터 수집 실패] {e}")
            return None

    def get_signal(self, df):
        if df is None or df.empty:
            return 0

        willr = df['Willr'].iloc[-1]
        rsi = df['RSI'].iloc[-1]
        vol = df['Volume'].iloc[-1]
        vol_ma = df['Vol_MA5'].iloc[-1]

        self._log(f"[지표] Willr: {willr:.2f}, RSI: {rsi:.2f}, Vol: {vol:.2f}, Vol_MA: {vol_ma:.2f}")

        if np.isnan(willr) or np.isnan(rsi) or np.isnan(vol_ma):
            return 0

        if willr < -85 and rsi < 38 and vol > vol_ma * 1.05:
            return 1
        elif willr > -15 and rsi > 62 and vol > vol_ma * 1.05:
            return -1
        return 0

    def get_price(self):
        try:
            price = float(self.client.futures_symbol_ticker(symbol=self.symbol)['price'])
            return price
        except Exception as e:
            self._log(f"[가격 조회 실패] {e}")
            return None

    def calc_max_qty(self, price):
        notional = self.balance * self.leverage
        raw_qty = notional / price
        qty = round(max(raw_qty, self.min_qty), self.qty_precision)
        self._log(f"[계산] 최대 수량: {qty} (레버리지 반영)")
        return qty

    def enter_position(self, side, qty, price):
        try:
            self.client.futures_create_order(
                symbol=self.symbol,
                side=side,
                type="MARKET",
                quantity=qty
            )
            self.position = 1 if side == "BUY" else -1
            self.entry_price = price
            self.last_qty = qty
            pos = "롱" if self.position == 1 else "숏"
            self._log(f"[진입] {pos} 수량: {qty} 가격: {price}")
        except Exception as e:
            self._log(f"[진입 실패] {e}")

    def close_position(self, price):
        if self.position == 0:
            return
        side = "SELL" if self.position == 1 else "BUY"
        try:
            self.client.futures_create_order(
                symbol=self.symbol,
                side=side,
                type="MARKET",
                quantity=round(self.last_qty, self.qty_precision)
            )
            pnl = ((price - self.entry_price) if self.position == 1 else (self.entry_price - price)) * self.last_qty
            commission = price * self.last_qty * 0.0004
            self.balance += pnl - commission
            pos = "롱" if self.position == 1 else "숏"
            self._log(f"[청산] {pos} → {side} 수익: {pnl - commission:.4f} 잔고: {self.balance:.2f}")
        except Exception as e:
            self._log(f"[청산 실패] {e}")
        finally:
            self.position = 0
            self.entry_price = None
            self.last_qty = 0

    def manage_position(self, current_price):
        if self.position == 0 or current_price is None:
            return

        if self.position == 1:
            tp = self.entry_price * (1 + self.TP)
            sl = self.entry_price * (1 + self.SL)
            if current_price >= tp or current_price <= sl:
                self._log(f"[TP/SL 조건] 롱 포지션 청산 조건 만족 (현재가: {current_price})")
                self.close_position(current_price)
        elif self.position == -1:
            tp = self.entry_price * (1 - self.TP)
            sl = self.entry_price * (1 - self.SL)
            if current_price <= tp or current_price >= sl:
                self._log(f"[TP/SL 조건] 숏 포지션 청산 조건 만족 (현재가: {current_price})")
                self.close_position(current_price)
