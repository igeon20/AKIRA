import os
import time
from dotenv import load_dotenv
from binance.client import Client
import pandas as pd
import numpy as np
import ta

load_dotenv()

class BinanceBot:
    MIN_NOTIONAL = 5
    SYMBOL = "BTCUSDT"
    QTY_PRECISION = 3
    PRICE_PRECISION = 2
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
        self.price_precision = self.PRICE_PRECISION
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

    def _format_qty(self, qty):
        return float(round(qty, self.qty_precision))

    def _format_price(self, price):
        return float(round(price, self.price_precision))

    def _calc_qty(self, price):
        max_position_value = self.balance * self.leverage * self.max_position_ratio
        qty = max(round(max_position_value / price, self.qty_precision), self.min_qty)
        return self._format_qty(qty)

    def _can_trade(self, price, qty):
        return price * qty >= self.MIN_NOTIONAL and qty >= self.min_qty

    def _enter_position(self, side, price, qty):
        try:
            qty = self._format_qty(qty)
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side="BUY" if side == "LONG" else "SELL",
                type="MARKET",
                quantity=qty,
                leverage=self.leverage
            )
            self.position = 1 if side == "LONG" else -1
            self.entry_price = price
            self.last_qty = qty
            msg = f"[진입] {side} @ {price:.2f} / 수량: {qty:.4f} / 가치: {qty * price:.2f} USDT"
            self._log(msg)
            self._log(f"잔고: {self.balance:.2f} USDT")
        except Exception as e:
            msg = f"[진입실패] {side} @ {price:.2f}: {e}"
            self._log(msg)

    def _forcibly_close_position(self, price, qty):
        side = "SELL" if self.position == 1 else "BUY"
        qty = self._format_qty(qty)
        price = self._format_price(price)
        try:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side=side,
                type="MARKET",
                quantity=qty
            )
            realised_pnl = ((price - self.entry_price) if self.position == 1 else (self.entry_price - price)) * qty
            commission = abs(qty) * price * 0.0004
            pnl_pct = ((price - self.entry_price) / self.entry_price * 100) if self.position == 1 else ((self.entry_price - price) / self.entry_price * 100)
            self.balance += realised_pnl - commission
            msg1 = f"[청산] {side} MARKET @ {price:.2f} | 손익:{pnl_pct:.2f}% | 수량:{qty:.4f}"
            msg2 = f"[손익] 실손익:{realised_pnl:.4f} USDT (수수료:{commission:.4f}), 잔고:{self.balance:.2f} USDT"
            self._log(msg1)
            self._log(msg2)
            self._reset_position_state()
            return True
        except Exception as e1:
            self._log(f"[청산실패] MARKET @ {price:.2f}: {e1}")
        try:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side=side,
                type="LIMIT",
                price=str(price),
                timeInForce="GTC",
                quantity=qty,
                reduceOnly=True
            )
            self._log(f"[청산시도] LIMIT @ {price:.2f}(reduceOnly)")
            self._reset_position_state()
            return True
        except Exception as e2:
            self._log(f"[청산실패] LIMIT @ {price:.2f}: {e2}")
        self._reset_position_state()
        return False
