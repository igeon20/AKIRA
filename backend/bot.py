# backend/bot.py
import os
import asyncio
import logging
from collections import deque
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException
from binance import BinanceSocketManager   # ← 변경된 부분

import ta

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('trade_logs.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

class BinanceBot:
    SYMBOL = os.getenv('SYMBOL', 'BTCUSDT')
    PRICE_PRECISION = 2
    QTY_PRECISION = 3

    LEVERAGE = int(os.getenv('LEVERAGE', 125))
    RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', 0.01))

    TP_PCT = float(os.getenv('TP_PCT', 0.008))
    SL_PCT = float(os.getenv('SL_PCT', -0.04))

    MAX_RETRIES = 5
    BACKOFF_INITIAL = 1

    ATR_WINDOW = 14

    def __init__(self):
        self.client = Client(
            api_key=os.getenv('BINANCE_API_KEY'),
            api_secret=os.getenv('BINANCE_SECRET_KEY'),
            testnet=True
        )
        self.client.API_URL = os.getenv('BINANCE_BASE_URL')
        self.client.futures_change_leverage(symbol=self.SYMBOL, leverage=self.LEVERAGE)

        # WebSocket 매니저
        self.bm = BinanceSocketManager(self.client)
        self.price = None

        # ATR 데이터
        self.highs  = deque(maxlen=self.ATR_WINDOW+1)
        self.lows   = deque(maxlen=self.ATR_WINDOW+1)
        self.closes = deque(maxlen=self.ATR_WINDOW+1)

        self.position     = 0
        self.entry_price  = None
        self.entry_qty    = 0
        self.trade_logs   = []

    def _start_ws(self):
        self.bm.start_symbol_ticker_socket(self.SYMBOL, self._on_ticker)
        self.bm.start()

    def _on_ticker(self, msg):
        try:
            p = float(msg['c'])
            self.price = round(p, self.PRICE_PRECISION)
            self.highs.append(float(msg['h']))
            self.lows.append(float(msg['l']))
            self.closes.append(float(msg['c']))
        except:
            pass

    def calc_atr(self):
        if len(self.highs) < self.ATR_WINDOW+1:
            return None
        df_high = list(self.highs)
        df_low  = list(self.lows)
        df_close= list(self.closes)
        atr = ta.trend.ATRIndicator(
            high=df_high, low=df_low, close=df_close, window=self.ATR_WINDOW
        ).atr()
        atr = atr.dropna()
        return atr.iloc[-1] if not atr.empty else None

    def calc_qty(self):
        usdt_bal = float(next(
            (b['balance'] for b in self.client.futures_account_balance() if b['asset']=='USDT'), 0
        ))
        atr = self.calc_atr()
        if atr:
            risk_amt = usdt_bal * self.RISK_PER_TRADE
            qty = risk_amt / atr
        else:
            qty = (usdt_bal * self.LEVERAGE) / self.price
        return round(qty, self.QTY_PRECISION)

    async def _retry_order(self, func, *args, **kwargs):
        backoff = self.BACKOFF_INITIAL
        for i in range(self.MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except BinanceAPIException as e:
                logger.warning(f"Order failed (code {e.code}), retry {i+1} after {backoff}s")
                await asyncio.sleep(backoff)
                backoff *= 2
        logger.error("Max retries reached.")
        return None

    async def enter_position(self, side):
        qty = self.calc_qty()
        if qty <= 0: return

        order = await self._retry_order(
            self.client.futures_create_order,
            symbol=self.SYMBOL, side=side, type='MARKET', quantity=qty
        )
        if not order: return

        self.position    = 1 if side=='BUY' else -1
        self.entry_price = self.price
        self.entry_qty   = qty
        msg = f"Entered {side}: price={self.price}, qty={qty}"
        logger.info(msg)
        self.trade_logs.append(msg)

        tp = round(self.price * (1 + self.TP_PCT*(1 if side=='BUY' else -1)), self.PRICE_PRECISION)
        sl = round(self.price * (1 + self.SL_PCT*(1 if side=='BUY' else -1)), self.PRICE_PRECISION)

        # TP Limit
        await self._retry_order(
            self.client.futures_create_order,
            symbol=self.SYMBOL,
            side=('SELL' if side=='BUY' else 'BUY'),
            type='LIMIT',
            timeInForce='GTC',
            quantity=qty,
            price=tp,
            reduceOnly=True
        )
        # SL Stop Market
        await self._retry_order(
            self.client.futures_create_order,
            symbol=self.SYMBOL,
            side=('SELL' if side=='BUY' else 'BUY'),
            type='STOP_MARKET',
            stopPrice=sl,
            quantity=qty,
            reduceOnly=True
        )

    async def monitor(self):
        while True:
            # 전략 진입/청산 로직 삽입 위치
            await asyncio.sleep(1)

    async def run(self):
        self._start_ws()
        await asyncio.gather(self.monitor())


if __name__ == '__main__':
    bot = BinanceBot()
    asyncio.run(bot.run())
