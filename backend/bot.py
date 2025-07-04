import os
import asyncio
import logging
import threading
from collections import deque
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException
from binance import ThreadedWebsocketManager

import ta

# 환경변수 로드
load_dotenv()

# 로그 설정
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

    TP_PCT = float(os.getenv('TP_PCT', 0.008))   # 0.8%
    SL_PCT = float(os.getenv('SL_PCT', -0.04))   # -4%

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

        self.bm = ThreadedWebsocketManager(
            api_key=os.getenv('BINANCE_API_KEY'),
            api_secret=os.getenv('BINANCE_SECRET_KEY'),
            testnet=True
        )
        self.price = None

        self.highs  = deque(maxlen=self.ATR_WINDOW + 1)
        self.lows   = deque(maxlen=self.ATR_WINDOW + 1)
        self.closes = deque(maxlen=self.ATR_WINDOW + 1)

        self.position    = 0
        self.entry_price = None
        self.entry_qty   = 0
        self.trade_logs  = []

    def _on_ticker(self, msg):
        try:
            p = float(msg['c'])
            self.price = round(p, self.PRICE_PRECISION)
            self.highs.append(float(msg['h']))
            self.lows.append(float(msg['l']))
            self.closes.append(float(msg['c']))
        except Exception:
            pass

    def _start_ws(self):
        # WebSocket Manager를 별도 스레드로 실행
        t = threading.Thread(target=self.bm.start, daemon=True)
        t.start()
        # Futures 개별 심볼 티커 구독
        self.bm.start_symbol_ticker_futures_socket(
            symbol=self.SYMBOL,
            callback=self._on_ticker
        )

    def calc_atr(self):
        if len(self.highs) < self.ATR_WINDOW + 1:
            return None
        df = {
            'high': list(self.highs),
            'low': list(self.lows),
            'close': list(self.closes)
        }
        atr_series = ta.trend.ATRIndicator(
            high=df['high'], low=df['low'], close=df['close'], window=self.ATR_WINDOW
        ).atr()
        cleaned = atr_series.dropna()
        return cleaned.iloc[-1] if not cleaned.empty else None

    def calc_qty(self):
        usdt_bal = float(next(
            (b['balance'] for b in self.client.futures_account_balance() if b['asset']=='USDT'),
            0
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
        for attempt in range(self.MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except BinanceAPIException as e:
                logger.warning(f"Order failed (code {e.code}), retry {attempt+1}/{self.MAX_RETRIES} after {backoff}s")
                await asyncio.sleep(backoff)
                backoff *= 2
        logger.error("Max retries reached.")
        return None

    async def enter_position(self, side):
        qty = self.calc_qty()
        if qty <= 0:
            return
        order = await self._retry_order(
            self.client.futures_create_order,
            symbol=self.SYMBOL,
            side=side,
            type='MARKET',
            quantity=qty
        )
        if not order:
            return
        self.position    = 1 if side == 'BUY' else -1
        self.entry_price = self.price
        self.entry_qty   = qty
        msg = f"Entered {side}: price={self.price}, qty={qty}"
        logger.info(msg)
        self.trade_logs.append(msg)

        tp = round(self.price * (1 + self.TP_PCT * (1 if side=='BUY' else -1)), self.PRICE_PRECISION)
        sl = round(self.price * (1 + self.SL_PCT * (1 if side=='BUY' else -1)), self.PRICE_PRECISION)
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
        # WebSocket 구독 시작
        self._start_ws()
        while True:
            # 전략 진입/청산 로직 위치
            await asyncio.sleep(1)

    async def run(self):
        await self.monitor()

if __name__ == '__main__':
    bot = BinanceBot()
    asyncio.run(bot.run())
