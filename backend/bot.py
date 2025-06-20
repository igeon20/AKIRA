import os
from binance.client import Client
from dotenv import load_dotenv
import pandas as pd
import ta
import time

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
        
        self.running = False
        self.symbol = "BTCUSDT"
        self.leverage = 125   # 원본 전략 레버리지 반영
        self.trade_logs = ["봇 초기화 완료 🚀"]
        self.balance = 50.0   # 가상잔고

        # 전략값
        self.TAKE_PROFIT = 0.04
        self.STOP_LOSS   = -0.02
        self.position = 0         # 1: 롱 중, -1: 숏 중, 0: 미보유
        self.entry_price = None

        try:
            self.client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)
            self.trade_logs.append(f"[설정] 레버리지 {self.leverage}배 세팅성공 ✅")
        except Exception as e:
            self.trade_logs.append(f"[오류] 레버리지 변경 실패❌ {str(e)}")

    def fetch_ohlcv(self, interval="1m"):
        klines = self.client.futures_klines(symbol=self.symbol, interval=interval, limit=100)
        df = pd.DataFrame(klines, columns=[
            'timestamp','Open','High','Low','Close','Volume',
            'close_time','quote_vol','trades','taker_base_vol','taker_quote_vol','ignore'
        ])
        df[['Open','High','Low','Close','Volume']] = df[['Open','High','Low','Close','Volume']].astype(float)
        return df

    def start(self):
        self.running = True
        self.trade_logs.append("[시작] 봇 스타트!")

        while self.running:
            df = self.fetch_ohlcv()
            df['willr'] = ta.momentum.williams_r(df['High'], df['Low'], df['Close'], lbp=14)
            current_price = df['Close'].iloc[-1]
            willr = df['willr'].iloc[-1]

            # -- 진입전 (노포지션) --
            if self.position == 0:
                # 롱 진입
                if willr < -80:
                    self._enter_position("LONG", current_price)
                # 숏 진입
                elif willr > -20:
                    self._enter_position("SHORT", current_price)

            # -- 롱 보유중 --
            elif self.position == 1:
                pnl = (current_price - self.entry_price) / self.entry_price
                # TP, SL, 반전 진입시 청산/뒤집기
                if pnl >= self.TAKE_PROFIT or pnl <= self.STOP_LOSS or willr > -20:
                    self._close_position(current_price, pnl)
                    if willr > -20:  # 숏 반전 진입
                        self._enter_position("SHORT", current_price)

            # -- 숏 보유중 --
            elif self.position == -1:
                pnl = (self.entry_price - current_price) / self.entry_price
                # TP, SL, 반전 진입시 청산/뒤집기
                if pnl >= self.TAKE_PROFIT or pnl <= self.STOP_LOSS or willr < -80:
                    self._close_position(current_price, pnl)
                    if willr < -80:  # 롱 반전 진입
                        self._enter_position("LONG", current_price)

            # 1분 대기 (똑같이 1분봉 기준)
            time.sleep(60)

        self.trade_logs.append("[중지] 봇 스탑!")

    def stop(self):
        self.running = False
        self.trade_logs.append("[중지] 봇이 중단되었습니다.")

    def _enter_position(self, side, price):
        qty = 0.001 # 적은 수량 고정
        try:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side="BUY" if side == "LONG" else "SELL",
                type="MARKET",
                quantity=qty
            )
            self.entry_price = price
            self.position = 1 if side == "LONG" else -1
            self.trade_logs.append(f"[진입성공] {side} {price}$ / 수량:{qty}")
            self.trade_logs.append(f"잔고: {self.balance:.2f} USDT")
        except Exception as e:
            self.trade_logs.append(f"[진입실패] {side} @ {price}$ : {str(e)}")

    def _close_position(self, price, pnl):
        side = "SELL" if self.position == 1 else "BUY"
        qty = 0.001
        try:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side=side,
                type="MARKET",
                quantity=qty
            )
            profit = self.balance * (pnl * self.leverage)
            self.balance += profit
            self.trade_logs.append(f"[청산] 포지션 {'LONG' if self.position == 1 else 'SHORT'} 종료!")
            self.trade_logs.append(f"[손익] {pnl*100:.2f}% (레버리지:{self.leverage}배) / 수익:{profit:.2f} → 잔고:{self.balance:.2f} USDT")
        except Exception as e:
            self.trade_logs.append(f"[청산실패] @ {price}$ : {str(e)}")
        self.position = 0
        self.entry_price = None
