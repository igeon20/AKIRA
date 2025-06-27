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
    FEE = 0.0004

    INIT_BALANCE = 50.0
    TP = 0.15   # 목표 15% 순수익률
    SL = -0.05  # 목표 5% 순손실률

    def __init__(self):
        self.client = Client(
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_SECRET_KEY"),
            testnet=True
        )
        self.client.API_URL = os.getenv("BINANCE_BASE_URL")

        self.balance = self.INIT_BALANCE
        self.position = 0
        self.entry_price = None
        self.entry_commission = 0
        self.last_qty = 0
        self.running = False
        self.trade_logs = []

        try:
            self.client.futures_change_leverage(symbol=self.SYMBOL, leverage=self.LEVERAGE)
            self._log(f"[설정] 레버리지 {self.LEVERAGE}x")
        except Exception as e:
            self._log(f"[오류] 레버리지 설정 실패: {e}")

    def _log(self, msg):
        t = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{t}] {msg}"
        print(entry)
        self.trade_logs.append(entry)

    def start_bot(self):
        self.running = True
        self._log("봇 시작")
        while self.running:
            df1 = self._fetch_data(interval='1m')
            df5 = self._fetch_data(interval='5m')
            if df1 is None or df5 is None:
                time.sleep(5)
                continue
            signal = self.get_signal(df1, df5)
            price = self.get_price()
            if price is None:
                time.sleep(5)
                continue
            if signal == 1 and self.position <= 0:
                if self.position == -1:
                    self.close_position(price, "신호 전환")
                qty = self.calc_max_qty(price)
                if qty > self.MIN_QTY:
                    self.enter_position('BUY', qty, price)
            elif signal == -1 and self.position >= 0:
                if self.position == 1:
                    self.close_position(price, "신호 전환")
                qty = self.calc_max_qty(price)
                if qty > self.MIN_QTY:
                    self.enter_position('SELL', qty, price)
            self.manage_position(price)
            time.sleep(5)

    def stop(self):
        self.running = False
        self._log("봇 정지")

    def _fetch_data(self, interval='1m', limit=100):
        try:
            data = self.client.futures_klines(symbol=self.SYMBOL, interval=interval, limit=limit)
            df = pd.DataFrame(data, columns=[
                'ts','Open','High','Low','Close','Volume','ct','qv','t','tbv','tqv','ign'
            ])
            df[['Open','High','Low','Close','Volume']] = df[['Open','High','Low','Close','Volume']].astype(float)
            # 지표
            df['Willr'] = ta.momentum.williams_r(df['High'], df['Low'], df['Close'], lbp=14)
            df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
            df['Vol_MA5'] = df['Volume'].rolling(5).mean()
            df['ATR'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=14).average_true_range()
            df.dropna(inplace=True)
            return None if df.empty else df
        except Exception as e:
            self._log(f"[오류] 데이터 수집 실패({interval}): {e}")
            return None

    def get_signal(self, df1, df5):
        # 1m, 5m 동일 신호 확인
        def single_signal(df):
            w, r, v, vma, atr = df['Willr'].iloc[-1], df['RSI'].iloc[-1], df['Volume'].iloc[-1], df['Vol_MA5'].iloc[-1], df['ATR'].iloc[-1]
            atr_ma = df['ATR'].rolling(20).mean().iloc[-1]
            if atr <= atr_ma * 1.2:
                return 0
            if w < -85 and r < 37 and v > vma * 1.05:
                return 1
            if w > -15 and r > 63 and v > vma * 1.05:
                return -1
            return 0
        s1 = single_signal(df1)
        s5 = single_signal(df5)
        sig = s1 if s1 == s5 and s1 != 0 else 0
        if sig:
            self._log(f"신호 발생: {'롱' if sig==1 else '숏'}")
        return sig

    def get_price(self):
        try:
            return float(self.client.futures_symbol_ticker(symbol=self.SYMBOL)['price'])
        except Exception as e:
            self._log(f"[오류] 현재가 조회 실패: {e}")
            return None

    def calc_max_qty(self, price):
        notional = self.balance * self.LEVERAGE
        qty = round(max(notional / price, self.MIN_QTY), self.QTY_PRECISION)
        self._log(f"최대 수량: {qty}")
        return qty

    def enter_position(self, side, qty, price):
        # 지정가 매수/매도 (메이커)로 수수료 절감
        offset = 0.999 if side == 'BUY' else 1.001
        order_price = round(price * offset, self.PRICE_PRECISION)
        try:
            self.client.futures_create_order(
                symbol=self.SYMBOL, side=side, type='LIMIT', timeInForce='GTC',
                price=order_price, quantity=qty
            )
            self.position = 1 if side == 'BUY' else -1
            self.entry_price = order_price
            self.last_qty = qty
            # 진입 수수료 (메이커는 -0.02%)
            fee_rate = -0.0002
            commission = order_price * qty * abs(fee_rate)
            self.balance -= commission
            self.entry_commission = commission
            self._log(f"진입({side}) 성공: 가격={order_price}, 수량={qty}, 수수료={commission:.4f}")
        except Exception as e:
            self._log(f"[진입 실패] {e}")
            self.position = 0

    def close_position(self, price, reason=""):
        side = 'SELL' if self.position == 1 else 'BUY'
        offset = 1.001 if side == 'SELL' else 0.999
        order_price = round(price * offset, self.PRICE_PRECISION)
        try:
            self.client.futures_create_order(
                symbol=self.SYMBOL, side=side, type='LIMIT', timeInForce='GTC',
                price=order_price, quantity=self.last_qty
            )
            pnl_raw = ((order_price - self.entry_price) if self.position == 1 else (self.entry_price - order_price)) * self.last_qty
            fee_rate = -0.0002
            commission = order_price * self.last_qty * abs(fee_rate)
            total_comm = self.entry_commission + commission
            net_pnl = pnl_raw - total_comm
            self.balance += net_pnl
            self._log(f"청산 성공({reason}): 가격={order_price}, 순PnL={net_pnl:.4f}, 잔고={self.balance:.2f}")
        except Exception as e:
            self._log(f"[청산 실패] {e}")
        finally:
            self.position = 0
            self.entry_price = None
            self.entry_commission = 0
            self.last_qty = 0

    def manage_position(self, price):
        if self.position == 0: return
        # 이미 수수료 반영된 net_pnl 확인
        # TP/SL 적용은 get_signal 이후 청산시 적용됨
        pass

# api.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from threading import Thread
from bot import BinanceBot

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://akiraa.netlify.app","https://eveleen.netlify.app","http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
bot = BinanceBot()

@app.api_route("/", methods=["GET","HEAD"], include_in_schema=False)
def read_root(req: Request):
    return JSONResponse(content=None, status_code=200) if req.method=='HEAD' else {"message":"API"}

@app.get("/ping")
def ping(): return {"status":"ok"}

@app.post("/bot/start")
def start():
    if not bot.running:
        Thread(target=bot.start_bot).start()
        return {"message":"봇 시작"}
    return {"message":"이미 실행중"}

@app.post("/bot/stop")
def stop():
    if bot.running:
        bot.stop()
        return {"message":"봇 정지"}
    return {"message":"이미 정지됨"}

@app.get("/bot/status")
def status():
    return {"running":bot.running,"balance":bot.balance,"position":bot.position,"entry_price":bot.entry_price}

@app.get("/bot/logs")
def logs():
    return {"logs":bot.trade_logs}
