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
    LEVERAGE = 125  # 레버리지 (필요 시 조정)
    FEE = 0.0004  # Binance Futures 테이커 수수료 (0.04%)

    INIT_BALANCE = 50.0  # 초기 자산
    TP = 0.03   # 목표 순수익률
    SL = -0.009 # 목표 순손실률

    # (생략: ASCII 아트 생략하여 가독성 향상)
    AKIRA_ART = r"""
⣿⣿⣿⣿⣿⣿⣿⡿⠛⠉⠉⠉⠉⠛⠻⣿⣿⠿⠛⠛⠙⠛⠻⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⠟⠁⠀⠀⠀⢀⣀⣀⡀⠀⠈⢄⠀⠀⠀⠀⠀⠀⠀⢻⣿⣿⣿⣿⣿
⣿⣿⣿⣿⠏⠀⠀⠀⠔⠉⠁⠀⠀⠈⠉⠓⢼⡤⠔⠒⠀⠐⠒⠢⠌⠿⢿⣿⣿⣿
⣿⣿⣿⡏⠀⠀⠀⠀⠀⠀⢀⠤⣒⠶⠤⠭⠭⢝⡢⣄⢤⣄⣒⡶⠶⣶⣢⡝⢿⣿
⡿⠋⠁⠀⠀⠀⠀⣀⠲⠮⢕⣽⠖⢩⠉⠙⣷⣶⣮⡍⢉⣴⠆⣭⢉⠑⣶⣮⣅⢻
⠀⠀⠀⠀⠀⠀⠀⠉⠒⠒⠻⣿⣄⠤⠘⢃⣿⣿⡿⠫⣿⣿⣄⠤⠘⢃⣿⣿⠿⣿
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠓⠤⠭⣥⣀⣉⡩⡥⠴⠃⠀⠈⠉⠁⠈⠉⠁⣴⣾⣿
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⠤⠔⠊⠀⠀⠀⠓⠲⡤⠤⠖⠐⢿⣿⣿⣿
⠀⠀⠀⠀⠀⠀⠀⠀⣠⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣿⣿
⠀⠀⠀⠀⠀⠀⠀⢸⣿⡻⢷⣤⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣘⣿⣿
⠀⠀⠀⠀⠀⠠⡀⠀⠙⢿⣷⣽⣽⣛⣟⣻⠷⠶⢶⣦⣤⣤⣤⣤⣶⠾⠟⣯⣿⣿
⠀⠀⠀⠀⠀⠀⠉⠂⠀⠀⠀⠈⠉⠙⠛⠻⠿⠿⠿⠿⠶⠶⠶⠶⠾⣿⣟⣿⣿⣿
⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⣿⣿⣿⣿⣿⣿
⣿⣿⣶⣤⣀⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣤⣟⢿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣶⣶⣶⣶⣶⣶⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
    """
    PROFIT_ART = r"""
    ⣿⣿⣿⣿⣿⣿⣿⡿⠛⠉⠉⠉⠉⠛⠻⣿⣿⠿⠛⠛⠙⠛⠻⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⠟⠁⠀⠀⠀⢀⣀⣀⡀⠀⠈⢄⠀⠀⠀⠀⠀⠀⠀⢻⣿⣿⣿⣿⣿
⣿⣿⣿⣿⠏⠀⠀⠀⠔⠉⠁⠀⠀⠈⠉⠓⢼⡤⠔⠒⠀⠐⠒⠢⠌⠿⢿⣿⣿⣿
⣿⣿⣿⡏⠀⠀⠀⠀⠀⠀⢀⠤⣒⠶⠤⠭⠭⢝⡢⣄⢤⣄⣒⡶⠶⣶⣢⡝⢿⣿
⡿⠋⠁⠀⠀⠀⠀⣀⠲⠮⢕⣽⠖⢩⠉⠙⣷⣶⣮⡍⢉⣴⠆⣭⢉⠑⣶⣮⣅⢻
⠀⠀⠀⠀⠀⠀⠀⠉⠒⠒⠻⣿⣄⠤⠘⢃⣿⣿⡿⠫⣿⣿⣄⠤⠘⢃⣿⣿⠿⣿
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠓⠤⠭⣥⣀⣉⡩⡥⠴⠃⠀⠈⠉⠁⠈⠉⠁⣴⣾⣿
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⠤⠔⠊⠀⠀⠀⠓⠲⡤⠤⠖⠐⢿⣿⣿⣿
⠀⠀⠀⠀⠀⠀⠀⠀⣠⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣿⣿
⠀⠀⠀⠀⠀⠀⠀⢸⣿⡻⢷⣤⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣘⣿⣿
⠀⠀⠀⠀⠀⠠⡀⠀⠙⢿⣷⣽⣽⣛⣟⣻⠷⠶⢶⣦⣤⣤⣤⣤⣶⠾⠟⣯⣿⣿
⠀⠀⠀⠀⠀⠀⠉⠂⠀⠀⠀⠈⠉⠙⠛⠻⠿⠿⠿⠿⠶⠶⠶⠶⠾⣿⣟⣿⣿⣿
⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⣿⣿⣿⣿⣿⣿
⣿⣿⣶⣤⣀⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣤⣟⢿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣶⣶⣶⣶⣶⣶⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
    """
    LOSS_ART = r"""
⣿⣿⣿⣿⣿⣿⣿⠟⠋⠉⠁⠈⠉⠙⠻⢿⡿⠿⠛⠋⠉⠙⠛⢿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⠟⠁⠀⠀⢀⣀⣀⣀⣀⡀⠀⢆⠀⠀⠀⠀⠀⠀⠀⢻⣿⣿⣿⣿⣿
⣿⣿⣿⣿⠃⠀⠀⠠⠊⠁⠀⠀⠀⠀⠈⠑⠪⡖⠒⠒⠒⠒⠒⠒⠶⠛⠿⣿⣿⣿
⣿⣿⡿⡇⠀⠀⠀⠀⠀⠀⡠⢔⡢⠍⠉⠉⠩⠭⢑⣤⣔⠲⠤⠭⠭⠤⠴⢊⡻⣿
⡿⠁⢀⠇⠀⠀⠀⣤⠭⠓⠊⣁⣤⠂⠠⢀⡈⠱⣶⣆⣠⣴⡖⠁⠂⣀⠈⢷⣮⣹
⠁⠀⠀⠀⠀⠀⠀⠈⠉⢳⣿⣿⣿⡀⠀⠀⢀⣀⣿⡿⢿⣿⣇⣀⣥⣤⠤⢼⣿⣿
⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⡟⠑⠚⢹⡟⠉⣑⠒⢺⡇⡀⠀⡹⠀⠀⣀⣴⣽⣿⣿
⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⡇⠀⠀⣿⠒⠉⠀⠀⢠⠃⠈⠙⠻⣍⠙⢻⡻⣿⣿⣿
⠀⠀⠀⠀⠀⠀⠀⠀⣀⣘⡄⠀⠀⢸⡇⠀⠀⠀⠘⡇⠀⠀⠀⠘⡄⠀⢱⢸⣿⣿
⠀⠀⠀⠀⠠⡀⠀⠾⣟⣻⣛⠷⣶⣼⣥⣀⣀⣀⠀⢧⠀⠀⠀⠠⣧⣀⣼⣴⢽⣿
⠀⠀⠀⠀⠀⠈⠉⠁⠀⠹⡙⠛⠷⣿⣭⣯⣭⣟⣛⣿⣿⣿⣛⣛⣿⣭⣭⣾⣿⣿
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠸⡀⠀⠀⣇⠀⠉⠉⠉⡏⠉⠙⠛⠛⡿⣻⣯⣷⣿⣿⣿
⣶⣤⣀⠀⠀⠀⠀⠀⠀⠀⡇⠀⠀⢸⠀⠀⠀⡸⠁⣠⣴⣶⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣶⣶⣦⣤⣤⣤⣷⣤⣄⣈⣆⣤⣤⣧⣶⣷⣿⡻⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣾⢿⣿⣿⣿⣿⣿⣿
    """

    def __init__(self):
        self.client = Client(
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_SECRET_KEY"),
            testnet=True
        )
        self.client.API_URL = os.getenv("BINANCE_BASE_URL")

        self.symbol = self.SYMBOL
        self.qty_precision = self.QTY_PRECISION
        self.price_precision = self.PRICE_PRECISION
        self.min_qty = self.MIN_QTY
        self.leverage = self.LEVERAGE
        self.balance = self.INIT_BALANCE

        self.position = 0
        self.entry_price = None
        self.entry_commission = 0
        self.last_qty = 0
        self.entry_time = 0

        self.running = False
        self.trade_logs = []

        # 레버리지 설정
        try:
            self.client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)
            self._log(f"[설정] 🤖레버리지🤖 {self.leverage}x 설정 완료.")
        except Exception as e:
            self._log(f"[오류] 레버리지 설정 실패: {e}")

    def _log(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        self.trade_logs.append(log_entry)

    def start_bot(self):
        self.running = True
        self._log("[봇 시작] 트레이딩 루프 시작.")
        self._log(self.AKIRA_ART)

        while self.running:
            df = self.fetch_data()
            if df is None:
                time.sleep(5)
                continue

            signal = self.get_signal(df)
            current_price = self.get_price()
            if current_price is None:
                time.sleep(5)
                continue

            if signal == 1 and self.position <= 0:
                if self.position == -1:
                    self.close_position(current_price, "신호 전환")
                qty = self.calc_max_qty(current_price)
                if qty > self.min_qty:
                    self.enter_position("BUY", qty, current_price)
            elif signal == -1 and self.position >= 0:
                if self.position == 1:
                    self.close_position(current_price, "신호 전환")
                qty = self.calc_max_qty(current_price)
                if qty > self.min_qty:
                    self.enter_position("SELL", qty, current_price)

            self.manage_position(current_price)
            time.sleep(5)

    def stop(self):
        self.running = False
        self._log("[봇 정지] 트레이딩 루프 종료.")

    def fetch_data(self):
        try:
            klines = self.client.futures_klines(symbol=self.symbol, interval="1m", limit=100)
            df = pd.DataFrame(klines, columns=[
                'timestamp','Open','High','Low','Close','Volume','close_time','quote_vol','trades',
                'taker_base_vol','taker_quote_vol','ignore'
            ])
            df[['Open','High','Low','Close','Volume']] = df[['Open','High','Low','Close','Volume']].astype(float)
            df['Willr'] = ta.momentum.williams_r(df['High'], df['Low'], df['Close'], lbp=14)
            df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
            df['Vol_MA5'] = df['Volume'].rolling(5).mean()
            df.dropna(inplace=True)
            return None if df.empty else df
        except Exception as e:
            self._log(f"[오류] 데이터 수집 실패: {e}")
            return None

    def get_signal(self, df):
        willr, rsi = df['Willr'].iloc[-1], df['RSI'].iloc[-1]
        vol, vol_ma = df['Volume'].iloc[-1], df['Vol_MA5'].iloc[-1]
        if willr < -85 and rsi < 37 and vol > vol_ma * 1.05:
            self._log(f"[신호 발생] 롱 (Willr:{willr:.2f}, RSI:{rsi:.2f})")
            return 1
        if willr > -15 and rsi > 63 and vol > vol_ma * 1.05:
            self._log(f"[신호 발생] 숏 (Willr:{willr:.2f}, RSI:{rsi:.2f})")
            return -1
        return 0

    def get_price(self):
        try:
            return float(self.client.futures_symbol_ticker(symbol=self.symbol)['price'])
        except Exception as e:
            self._log(f"[오류] 현재가 조회 실패: {e}")
            return None

    def calc_max_qty(self, price):
        notional = self.balance * self.leverage
        qty = round(max(notional / price, self.min_qty), self.qty_precision)
        self._log(f"[계산] 최대 진입 수량: {qty} (자산: {self.balance:.2f}, 레버리지: {self.leverage}x)")
        return qty

    def enter_position(self, side, qty, price):
        try:
            self.client.futures_create_order(symbol=self.symbol, side=side, type="MARKET", quantity=qty)
            self.position = 1 if side == "BUY" else -1
            self.entry_price = price
            self.last_qty = qty
            # 진입 수수료 계산 및 차감
            commission_entry = price * qty * self.FEE
            self.balance -= commission_entry
            self.entry_commission = commission_entry
            self._log(f"[진입 성공] {('롱' if self.position==1 else '숏')} 수량: {qty}, 가격: {price:.2f} USDT")
            self._log(f"[진입 수수료] {commission_entry:.4f} USDT")
        except Exception as e:
            self._log(f"[진입 실패] {e}")
            self.position = 0

    def close_position(self, price, reason=""):
        if self.position == 0: return
        side_to_close = "SELL" if self.position == 1 else "BUY"
        current_pos = '롱' if self.position==1 else '숏'
        try:
            self.client.futures_create_order(symbol=self.symbol, side=side_to_close, type="MARKET", quantity=self.last_qty)
            # 원시 PnL
            pnl_raw = ((price - self.entry_price) if self.position==1 else (self.entry_price - price)) * self.last_qty
            # 청산 수수료
            commission_exit = price * self.last_qty * self.FEE
            total_commission = self.entry_commission + commission_exit
            net_pnl = pnl_raw - total_commission
            self.balance += net_pnl
            self._log(f"[청산 성공] {current_pos} 청산, 가격: {price:.2f}, 원인: {reason}")
            self._log(f"    원시 PnL: {pnl_raw:.4f} USDT, 수수료(입장): {self.entry_commission:.4f}, 수수료(청산): {commission_exit:.4f}, 순수익: {net_pnl:.4f} USDT, 잔고: {self.balance:.2f}")
            self._log(self.PROFIT_ART if net_pnl>=0 else self.LOSS_ART)
        except Exception as e:
            self._log(f"[청산 실패] {e}")
        finally:
            self.position = 0
            self.entry_price = None
            self.entry_commission = 0
            self.last_qty = 0

    def manage_position(self, current_price):
        if self.position == 0 or current_price is None: return
        # 미실현 PnL
        current_pnl = ((current_price - self.entry_price) if self.position==1 else (self.entry_price - current_price)) * self.last_qty
        # 투자 자본
        invested = (self.entry_price * self.last_qty) / self.leverage
        # 총 수수료 추정
        commission_exit = current_price * self.last_qty * self.FEE
        total_comm = self.entry_commission + commission_exit
        # 순수익 및 비율
        net_pnl = current_pnl - total_comm
        net_pct = net_pnl / invested if invested>0 else 0
        self._log(f"[포지션 관리] 순 PnL: {net_pnl:.4f} USDT, 순수익률: {net_pct*100:.2f}%")
        if net_pct >= self.TP:
            self.close_position(current_price, "TP 도달 (net)")
        elif net_pct <= self.SL:
            self.close_position(current_price, "SL 도달 (net)")
