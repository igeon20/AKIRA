import os
import time
from dotenv import load_dotenv
from binance.client import Client
import pandas as pd
import numpy as np
import ta

load_dotenv()

class BinanceBot:
    MIN_NOTIONAL = 100
    SYMBOL = "BTCUSDT"
    QTY_PRECISION = 3
    MIN_QTY = 0.001
    LEVERAGE = 125
    MAX_POSITION_RATIO = 1.0
    INIT_BALANCE = 50.0

    TP = 0.04
    SL = -0.02

    def __init__(self):
        self.TESTNET_URL = os.getenv("BINANCE_BASE_URL")
        self.client = Client(
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_SECRET_KEY"),
            testnet=True
        )
        self.client.API_URL = self.TESTNET_URL

        self.symbol = self.SYMBOL
        self.qty_precision = self.QTY_PRECISION
        self.min_qty = self.MIN_QTY
        self.leverage = self.LEVERAGE
        self.max_position_ratio = self.MAX_POSITION_RATIO
        self.balance = self.INIT_BALANCE
        self.position = 0
        self.entry_price = None
        self.last_qty = 0
        self.entry_time = 0

        self.running = False
        self.trade_logs = []
        print("🤖[봇초기화]🤖")

        try:
            self.client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)
            print(f"[설정] 레버리지 {self.leverage}배 적용 완료.")
        except Exception as e:
            print(f"[레버리지 실패] {e}")

    def fetch_ohlcv(self, interval="1m"):
        try:
            klines = self.client.futures_klines(symbol=self.symbol, interval=interval, limit=100)
            df = pd.DataFrame(klines, columns=[
                'timestamp','Open','High','Low','Close','Volume',
                'close_time','quote_vol','trades',
                'taker_base_vol','taker_quote_vol','ignore'
            ])
            df[['Open','High','Low','Close','Volume']] = df[['Open','High','Low','Close','Volume']].astype(float)
            return df
        except Exception as e:
            print(f"[가격수집실패] {e}")
            return None

    def get_realtime_price(self):
        try:
            ticker = self.client.futures_symbol_ticker(symbol=self.symbol)
            if ticker and 'price' in ticker:
                return float(ticker['price'])
            else:
                return None
        except Exception as e:
            print(f"[실시간가격에러] {e}")
            return None

    def _calc_qty(self, price, factor=1.0):
        max_position = self.balance * self.max_position_ratio
        invest = max_position
        raw_qty = invest / price
        qty = max(round(raw_qty, self.qty_precision), self.min_qty)
        return float(qty)

    def _can_trade(self, price, qty):
        return price * qty >= self.MIN_NOTIONAL and qty >= self.min_qty

    def _reset_position_state(self):
        self.position = 0
        self.entry_price = None
        self.last_qty = 0
        self.entry_time = 0

    def _log(self, msg):
        self.trade_logs.append(msg)
        print(msg)

    def check_entry_signal(self, df):
        try:
            willr = float(df['Willr'].iloc[-1])
            rsi = float(df['RSI'].iloc[-1])
            vol = float(df['Volume'].iloc[-1])
            vol_ma = float(df['Vol_MA5'].iloc[-1])
        except (KeyError, IndexError, ValueError):
            return 0

        if np.isnan(willr) or np.isnan(rsi) or np.isnan(vol_ma):
            return 0

        if (willr < -85) and (rsi < 38) and (vol > vol_ma * 1.05):
            return 1
        elif (willr > -15) and (rsi > 62) and (vol > vol_ma * 1.05):
            return -1
        else:
            return 0

    def _log_position_status(self, cur_price):
        if self.position == 0:
            return
        if self.last_qty > 0 and self.entry_price is not None:
            pnl = ((cur_price - self.entry_price) if self.position == 1 else (self.entry_price - cur_price)) * self.last_qty
            pnl_pct = ((cur_price - self.entry_price) / self.entry_price * 100) if self.position == 1 else ((self.entry_price - cur_price) / self.entry_price * 100)
            msg = f"[포지션상태] {'LONG' if self.position == 1 else 'SHORT'} | 진입가 {self.entry_price:.2f} | 현가 {cur_price:.2f} | 수량 {self.last_qty:.4f} | 손익 {pnl_pct:.2f}% | 실손익 {pnl:.4f} USDT | 잔고 {self.balance:.2f}"
            self._log(msg)

    def stop(self):
        self.running = False
        self._log("[수동정지] 사용자 요청 봇 중지")
