import os
import time
import json
import asyncio
import logging
from collections import deque
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException
from binance.websockets import BinanceSocketManager
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

    # TP/SL 퍼센트 (차후 OCO 사용 시 직접 주문)
    TP_PCT = float(os.getenv('TP_PCT', 0.008))  # 0.8%
    SL_PCT = float(os.getenv('SL_PCT', -0.04)) # -4%

    # 주문 재시도 설정
    MAX_RETRIES = 5
    BACKOFF_INITIAL = 1  # 초

    # ATR 사이징 윈도우
    ATR_WINDOW = 14

    def __init__(self):
        # REST 클라이언트
        self.client = Client(api_key=os.getenv('BINANCE_API_KEY'),
                             api_secret=os.getenv('BINANCE_SECRET_KEY'),
                             testnet=True)
        self.client.API_URL = os.getenv('BINANCE_BASE_URL')
        self.client.futures_change_leverage(symbol=self.SYMBOL, leverage=self.LEVERAGE)

        # 웹소켓 매니저
        self.bm = BinanceSocketManager(self.client)
        self.price = None
        # 과거 가격 데이터 저장
        self.highs = deque(maxlen=self.ATR_WINDOW + 1)
        self.lows  = deque(maxlen=self.ATR_WINDOW + 1)
        self.closes= deque(maxlen=self.ATR_WINDOW + 1)
        # 포지션 상태
        self.position = 0
        self.entry_price = None
        self.entry_qty = 0

    def _start_ws(self):
        # 틱 가격 업데이트
        self.bm.start_symbol_ticker_socket(self.SYMBOL, self._on_ticker)
        self.bm.start()

    def _on_ticker(self, msg):
        try:
            price = float(msg['c'])  # 현재가
            self.price = round(price, self.PRICE_PRECISION)
            # ATR용 과거 데이터에 스냅샷 기록
            self.highs.append(float(msg['h']))
            self.lows.append(float(msg['l']))
            self.closes.append(float(msg['c']))
        except Exception:
            pass

    def calc_atr(self):
        if len(self.highs) < self.ATR_WINDOW + 1:
            return None
        df = { 'high': list(self.highs), 'low': list(self.lows), 'close': list(self.closes) }
        df = ta.utils.dropna(ta.trend.ATRIndicator(
            high=df['high'], low=df['low'], close=df['close'], window=self.ATR_WINDOW
        ).atr())
        return df.iloc[-1]

    def calc_qty(self):
        # ATR 기반 동적 사이징
        atr = self.calc_atr()
        if atr:
            risk_amount = (self.client.futures_account_balance()[0]['balance'])* self.RISK_PER_TRADE
            qty = risk_amount / atr
        else:
            # ATR이 없으면 최대 Notional 사용
            notional = float(self.client.futures_account_balance()[0]['balance']) * self.LEVERAGE
            qty = notional / self.price
        return round(qty, self.QTY_PRECISION)

    async def _retry_order(self, func, *args, **kwargs):
        backoff = self.BACKOFF_INITIAL
        for i in range(self.MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except BinanceAPIException as e:
                logger.warning(f"주문 실패({e.code}), 재시도 {i+1}/{self.MAX_RETRIES} after {backoff}s")
                await asyncio.sleep(backoff)
                backoff *= 2
        logger.error("최대 재시도 도달, 주문 실패")
        return None

    async def enter_position(self, side):
        qty = self.calc_qty()
        if qty <= 0:
            return
        # 시장 진입
        order = await self._retry_order(
            self.client.futures_create_order,
            symbol=self.SYMBOL, side=side, type='MARKET', quantity=qty
        )
        if order:
            self.position = 1 if side=='BUY' else -1
            self.entry_price = self.price
            self.entry_qty = qty
            logger.info(f"진입: {side} price={self.price}, qty={qty}")
            # OCO TP/SL 주문
            tp_price = self.price * (1 + self.TP_PCT * (1 if side=='BUY' else -1))
            sl_price = self.price * (1 + self.SL_PCT * (1 if side=='BUY' else -1))
            # TP Limit 주문
            await self._retry_order(
                self.client.futures_create_order,
                symbol=self.SYMBOL, side=('SELL' if side=='BUY' else 'BUY'),
                type='LIMIT', timeInForce='GTC', quantity=qty,
                price=round(tp_price, self.PRICE_PRECISION), reduceOnly=True
            )
            # SL Stop Market 주문
            await self._retry_order(
                self.client.futures_create_order,
                symbol=self.SYMBOL, side=('SELL' if side=='BUY' else 'BUY'),
                type='STOP_MARKET', stopPrice=round(sl_price, self.PRICE_PRECISION),
                quantity=qty, reduceOnly=True
            )

    async def manage(self):
        # 포지션 없으면 진입 로직
        if self.position == 0:
            # 예: 단순 RSI 기반 진입 (생략하고 AI/필터 로직 삽입 가능)
            # if self.should_enter():
            #     await self.enter_position('BUY' or 'SELL')
            return
        # 포지션 관리: OCO 활용, 별도 로직 불필요
        pass

    async def monitor(self):
        while True:
            if not self.price:
                await asyncio.sleep(0.1)
                continue
            # 주문 상태 모니터링, API Rate Limit 체크 등
            # (추가 구현 가능)
            await asyncio.sleep(1)

    async def run(self):
        self._start_ws()
        await asyncio.gather(
            self.monitor(),
        )

if __name__ == '__main__':
    bot = BinanceBot()
    asyncio.run(bot.run())
