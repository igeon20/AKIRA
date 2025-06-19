import os
from binance.client import Client
from dotenv import load_dotenv
import pandas as pd
import ta
import time

load_dotenv()

class BinanceBot:
    def __init__(self):
        TESTNET_URL = os.getenv("BINANCE_BASE_URL")

        self.client = Client(
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_SECRET_KEY"),
            testnet=True
        )
        self.client.API_URL = TESTNET_URL
        
        self.running = False
        self.symbol = "BTCUSDT"
        self.leverage = 10  # 안정적 테스트를 위한 권장레버리지
        self.trade_logs = ["봇 초기화 완료 🔥 가상 잔고 50$ 부터 시작"]
        self.balance = 50.0  # 가상의 50$로 시작

        try:
            self.client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)
            self.trade_logs.append(f"[설정] 레버리지 {self.leverage}배 설정 성공 ✅")
        except Exception as e:
            self.trade_logs.append(f"[오류] 레버리지 변경 실패 ❌ {str(e)}")

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
        self.trade_logs.append("🚀 봇이 시작되었습니다!")
        while self.running:
            df = self.fetch_ohlcv()
            df['willr'] = ta.momentum.williams_r(df['High'], df['Low'], df['Close'], lbp=14)
            current_price = df['Close'].iloc[-1]
            willr = df['willr'].iloc[-1]

            if willr < -80:
                self.execute_trade("BUY", current_price)

            elif willr > -20:
                self.execute_trade("SELL", current_price)

            time.sleep(60)  # 1분 간격

    def stop(self):
        self.running = False
        self.trade_logs.append("🛑 봇이 정지되었습니다!")

    def execute_trade(self, side, price):
        quantity = 0.001  # 안전한 소량 거래 테스트

        self.trade_logs.append(f"[주문요청] {side} @ {price}$ 시작 🎯")

        try:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side=side,
                type="MARKET",
                quantity=quantity
            )

            self.trade_logs.append(f"[체결성공] {side} @ {price}$ (수량: {quantity}BTC) ✅ 주문성공!")
            
            # 가상 잔고에 정상체결 기록
            approx_trade_value = quantity * price
            if side == "BUY":
                self.balance -= approx_trade_value
                self.trade_logs.append(f"[매수완료] 잔고: {self.balance:.2f} USD")
            else:
                self.balance += approx_trade_value
                self.trade_logs.append(f"[매도완료] 잔고: {self.balance:.2f} USD")

        except Exception as e:
            self.trade_logs.append(f"[체결실패] {side} @ {price}$ ❌ 실패사유: {str(e)}")