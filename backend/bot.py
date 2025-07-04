# backend/bot.py
import os
import time
import json
import asyncio
import logging
from collections import deque
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException
# fixed import for latest python-binance
from binance.streams import BinanceSocketManager

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

    # 레버리지 & 리스크 설정
    LEVERAGE = int(os.getenv('LEVERAGE', 125))
    RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', 0.01))  # 계좌 대비 1% 리스크

    # TP/SL 퍼센트
    TP_PCT = float(os.getenv('TP_PCT', 0.008))   # 0.8%
    SL_PCT = float(os.getenv('SL_PCT', -0.04))   # -4%

    # 주문 재시도 설정
    MAX_RETRIES = 5
    BACKOFF_INITIAL = 1  # seconds

    # ATR 사이징 윈도우
    ATR_WINDOW = 14

    def __init__(self):
        # REST 클라이언트
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

        # ATR용 과거 데이터 저장
        self.highs = deque(maxlen=self.ATR_WINDOW + 1)
        self.lows  = deque(maxlen=self.ATR_WINDOW + 1)
        self.closes= deque(maxlen=self.ATR_WINDOW + 1)

        # 포지션 상태
        self.position = 0
        self.entry_price = None
        self.entry_qty = 0
        self.trade_logs = []

    def _start_ws(self):
        self.bm.start_symbol_ticker_socket(self.SYMBOL, self._on_ticker)
        self.bm.start()

    def _on_ticker(self, msg):
        try:
            price = float(msg['c'])
            self.price = round(price, self.PRICE_PRECISION)
            self.highs.append(float(msg['h']))
            self.lows.append(float(msg['l']))
            self.closes.append(float(msg['c']))
        except Exception:
            pass

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
        return atr_series.dropna().iloc[-1] if not atr_series.dropna().empty else None

    def calc_qty(self):
        # ATR 기반 동적 사이징
        atr = self.calc_atr()
        usdt_balance = float(next(
            (b['balance'] for b in self.client.futures_account_balance() if b['asset']=='USDT'), 0
        ))
        if atr:
            risk_amount = usdt_balance * self.RISK_PER_TRADE
            qty = risk_amount / atr
        else:
            notional = usdt_balance * self.LEVERAGE
            qty = notional / self.price
        return round(qty, self.QTY_PRECISION)

    async def _retry_order(self, func, *args, **kwargs):
        backoff = self.BACKOFF_INITIAL
        for i in range(self.MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except BinanceAPIException as e:
                logger.warning(f"Order failed (code {e.code}), retry {i+1}/{self.MAX_RETRIES} after {backoff}s")
                await asyncio.sleep(backoff)
                backoff *= 2
        logger.error("Max retries reached, giving up on order.")
        return None

    async def enter_position(self, side):
        qty = self.calc_qty()
        if qty <= 0:
            return
        # MARKET 진입
        order = await self._retry_order(
            self.client.futures_create_order,
            symbol=self.SYMBOL, side=side, type='MARKET', quantity=qty
        )
        if not order:
            return

        self.position = 1 if side=='BUY' else -1
        self.entry_price = self.price
        self.entry_qty = qty
        logger.info(f"Entered {side}: price={self.price}, qty={qty}")
        self.trade_logs.append(f"Entered {side}: price={self.price}, qty={qty}")

        # OCO 스타일 TP/SL 브래킷 주문
        tp_price = round(self.price * (1 + self.TP_PCT * (1 if side=='BUY' else -1)), self.PRICE_PRECISION)
        sl_price = round(self.price * (1 + self.SL_PCT * (1 if side=='BUY' else -1)), self.PRICE_PRECISION)

        # TAKE-PROFIT
        await self._retry_order(
            self.client.futures_create_order,
            symbol=self.SYMBOL,
            side=('SELL' if side=='BUY' else 'BUY'),
            type='LIMIT',
            timeInForce='GTC',
            quantity=qty,
            price=tp_price,
            reduceOnly=True
        )
        # STOP-LOSS
        await self._retry_order(
            self.client.futures_create_order,
            symbol=self.SYMBOL,
            side=('SELL' if side=='BUY' else 'BUY'),
            type='STOP_MARKET',
            stopPrice=sl_price,
            quantity=qty,
            reduceOnly=True
        )

    async def monitor(self):
        while True:
            # 예시 진입 로직 (여기에 RSI/AI 로직 삽입)
            # if self.position == 0 and some_entry_condition:
            #     await self.enter_position('BUY' or 'SELL')
            await asyncio.sleep(1)

    async def run(self):
        self._start_ws()
        await asyncio.gather(self.monitor())

if __name__ == '__main__':
    bot = BinanceBot()
    asyncio.run(bot.run())
