import os
import asyncio
import logging
from collections import deque
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException
import ta

load_dotenv()

# ─── 로깅 설정 ───────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

class BinanceBot:
    SYMBOL = os.getenv('SYMBOL', 'BTCUSDT')
    PRICE_PRECISION = 2
    QTY_PRECISION = 3
    LEVERAGE = int(os.getenv('LEVERAGE', 125))
    RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', 0.01))
    TP_PCT = float(os.getenv('TP_PCT', 0.008))
    SL_PCT = float(os.getenv('SL_PCT', -0.04))
    ATR_WINDOW = 14

    def __init__(self):
        # REST 클라이언트 세팅
        self.client = Client(
            api_key=os.getenv('BINANCE_API_KEY'),
            api_secret=os.getenv('BINANCE_SECRET_KEY'),
            testnet=True
        )
        self.client.API_URL = os.getenv('BINANCE_BASE_URL')
        self.client.futures_change_leverage(symbol=self.SYMBOL, leverage=self.LEVERAGE)

        # 가격·ATR 계산용 버퍼
        self.price = None
        self.highs  = deque(maxlen=self.ATR_WINDOW + 1)
        self.lows   = deque(maxlen=self.ATR_WINDOW + 1)
        self.closes = deque(maxlen=self.ATR_WINDOW + 1)

        # 포지션 상태
        self.position    = 0
        self.entry_price = None
        self.entry_qty   = 0

        # 로그
        self.trade_logs = []

        # 실행 플래그
        self.running = False

    def calc_atr(self):
        if len(self.highs) < self.ATR_WINDOW + 1:
            return None
        atr = ta.trend.ATRIndicator(
            high=list(self.highs),
            low=list(self.lows),
            close=list(self.closes),
            window=self.ATR_WINDOW
        ).atr().dropna()
        return atr.iloc[-1] if not atr.empty else None

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
            qty = (usdt_bal * self.LEVERAGE) / self.price if self.price else 0
        return round(qty, self.QTY_PRECISION)

    async def enter_position(self, side):
        qty = self.calc_qty()
        if qty <= 0 or not self.price:
            return

        # 시장가 진입
        try:
            order = self.client.futures_create_order(
                symbol=self.SYMBOL, side=side,
                type='MARKET', quantity=qty
            )
        except BinanceAPIException as e:
            logger.error(f"Order failed: {e}")
            return

        self.position = 1 if side == 'BUY' else -1
        self.entry_price = self.price
        self.entry_qty = qty
        msg = f"Entered {side}: price={self.price}, qty={qty}"
        logger.info(msg)
        self.trade_logs.append(msg)

        # TP / SL 설정
        tp_price = round(self.price * (1 + self.TP_PCT * (1 if side=='BUY' else -1)), self.PRICE_PRECISION)
        sl_price = round(self.price * (1 + self.SL_PCT * (1 if side=='BUY' else -1)), self.PRICE_PRECISION)

        try:
            self.client.futures_create_order(
                symbol=self.SYMBOL,
                side=('SELL' if side=='BUY' else 'BUY'),
                type='LIMIT',
                timeInForce='GTC',
                quantity=qty,
                price=tp_price,
                reduceOnly=True
            )
            self.client.futures_create_order(
                symbol=self.SYMBOL,
                side=('SELL' if side=='BUY' else 'BUY'),
                type='STOP_MARKET',
                stopPrice=sl_price,
                quantity=qty,
                reduceOnly=True
            )
        except BinanceAPIException as e:
            logger.warning(f"TP/SL 설정 실패: {e}")

    async def monitor(self):
        """
        REST 폴링 방식으로 1초마다 현재가를 조회,
        high/low/close 버퍼 업데이트 및 로그 기록
        """
        while True:
            if self.running:
                try:
                    tick = self.client.futures_symbol_ticker(symbol=self.SYMBOL)
                    p = float(tick['price'])
                    self.price = round(p, self.PRICE_PRECISION)
                    # ATR 계산용 버퍼에 추가
                    self.highs.append(self.price)
                    self.lows.append(self.price)
                    self.closes.append(self.price)
                    # 로그
                    msg = f"현재가: {self.price}"
                    logger.info(msg)
                    self.trade_logs.append(msg)
                except Exception as e:
                    logger.error(f"가격 조회 실패: {e}")
            await asyncio.sleep(1)

    async def run(self):
        await self.monitor()


if __name__ == "__main__":
    bot = BinanceBot()
    asyncio.run(bot.run())
