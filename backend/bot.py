import os
import time
from binance.client import Client
from dotenv import load_dotenv
import pandas as pd
import ta

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

        self.symbol = "BTCUSDT"
        self.qty_precision = 3
        self.min_qty = 0.001
        self.leverage = 125
        self.running = False
        self.trade_logs = ["🤖[봇초기화]🤖 리스크 관리 + 진입 신호 상세 기록"]
        self.balance = 50.0
        self.position = 0      # 1:롱, -1:숏, 0:무포지션
        self.entry_price = None
        self.last_qty = 0
        self.last_signal = 0
        self.last_trade_time = 0
        self.entry_time = 0
        self.TP_initial = 0.005
        self.SL_initial = -0.002
        self.TP_dynamic = 0.002
        self.SL_dynamic = -0.002

        try:
            self.client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)
            self.trade_logs.append(f"[설정] 레버리지 {self.leverage}배 적용 완료.")
        except Exception as e:
            self.trade_logs.append(f"[레버리지 실패] {e}")

    def fetch_ohlcv(self, interval="1m"):
        try:
            klines = self.client.futures_klines(symbol=self.symbol, interval=interval, limit=100)
            df = pd.DataFrame(klines, columns=[
                'timestamp','Open','High','Low','Close','Volume',
                'close_time','quote_vol','trades','taker_base_vol','taker_quote_vol','ignore'
            ])
            df[['Open','High','Low','Close','Volume']] = df[['Open','High','Low','Close','Volume']].astype(float)
            return df
        except Exception as e:
            self.trade_logs.append(f"[가격수집실패] {e}")
            return None

    def _calc_qty(self, price, factor=1.0):
        # factor=1.0이면 평상시, 0.4면 보수적 진입
        usdt = max(self.balance * 0.1 * factor, 2.0)
        raw_qty = usdt / price
        qty = max(round(raw_qty, self.qty_precision), self.min_qty)
        return qty

    def check_entry_signal(self, df):
        willr = float(df['Willr'].iloc[-1])
        rsi = float(df['RSI'].iloc[-1])
        vol = float(df['Volume'].iloc[-1])
        vol_ma = float(df['Vol_MA5'].iloc[-1])
        if (willr < -80) and (rsi < 36) and (vol > vol_ma * 1.05):
            return 1
        elif (willr > -20) and (rsi > 64) and (vol > vol_ma * 1.05):
            return -1
        else:
            return 0

    def adjust_tp_sl(self):
        # 진입 3분 넘으면 더 좁게 TP/SL 조정
        if self.position == 0 or self.entry_time == 0:
            return self.TP_initial, self.SL_initial
        elapsed = time.time() - self.entry_time
        if elapsed > 3*60:
            return self.TP_dynamic, self.SL_dynamic
        else:
            return self.TP_initial, self.SL_initial

    def start(self):
        self.running = True
        self.trade_logs.append("[시작] 전략 봇 가동 (상태/진입불가 사유/에러 모두 기록)")

        while self.running:
            df = self.fetch_ohlcv()
            if df is None:
                time.sleep(10)
                continue

            df['Willr'] = ta.momentum.williams_r(df['High'], df['Low'], df['Close'], lbp=14)
            df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
            df['Vol_MA5'] = df['Volume'].rolling(5).mean()

            current_price = float(df['Close'].iloc[-1])
            willr = float(df['Willr'].iloc[-1])
            rsi   = float(df['RSI'].iloc[-1])
            vol   = float(df['Volume'].iloc[-1])
            vol_ma= float(df['Vol_MA5'].iloc[-1])
            now_signal = self.check_entry_signal(df)
            now = time.time()
            tp, sl = self.adjust_tp_sl()

            # 진입 로직 (기존+방향 중복 허용)
            if now_signal != 0:
                # 무포지션 or 반전진입(기존 포지션과 방향 다를 때)
                if self.position == 0 or now_signal != self.position:
                    qty = self._calc_qty(current_price, 1.0)
                    if qty < self.min_qty:
                        if len(self.trade_logs)==0 or self.trade_logs[-1].startswith("[진입실패]") == False:
                            self.trade_logs.append(f"[진입실패] 최소 수량({self.min_qty}) 미만. 계산수량: {qty:.6f}")
                    else:
                        # 반전진입이면, 포지션이 있으면 청산 먼저!
                        if self.position != 0:
                            pnl = ((current_price - self.entry_price) / self.entry_price) if self.position == 1 \
                                else ((self.entry_price - current_price) / self.entry_price)
                            self._close_position(current_price, pnl, self.last_qty)
                            self.last_trade_time = now
                            time.sleep(1)
                        self._enter_position("LONG" if now_signal == 1 else "SHORT", current_price, qty)
                        self.entry_time = now
                        self.last_signal = now_signal
                        self.position = now_signal
                        self.last_trade_time = now
                # 기존포지션이 있고, 같은 방향 신호 → "보수적 중복진입"
                elif self.position == now_signal:
                    factor = 0.4  # 보수적으로 진입(기존보다 적게)
                    qty = self._calc_qty(current_price, factor)
                    if qty >= self.min_qty:
                        self._add_position("LONG" if now_signal == 1 else "SHORT", current_price, qty)
                        self.last_signal = now_signal
                        self.last_trade_time = now
                        # 중복진입시 TP 추가로 늘려줌(익절만큼만 바로 청산, 손실은 보수적으로!)
                        self.TP_initial += 0.002
                        self.TP_dynamic += 0.001
                        self.trade_logs.append("[추가진입] 신호방향 중복. 추가 소량진입. TP 상향조정")
                    else:
                        if len(self.trade_logs)==0 or self.trade_logs[-1].startswith("[중복진입실패]") == False:
                            self.trade_logs.append(f"[중복진입실패] 최소수량 미만: {qty:.6f}")
            # 청산 조건(진입 후 시간 따라 TP/SL 자동 조정)
            if self.position != 0:
                tp, sl = self.adjust_tp_sl()
                pnl = ((current_price - self.entry_price) / self.entry_price) if self.position == 1 \
                    else ((self.entry_price - current_price) / self.entry_price)
                take_profit_hit = pnl >= tp
                stop_loss_hit = pnl <= sl
                # 중복진입이면 TP가 더 큼!
                if take_profit_hit or stop_loss_hit:
                    self._close_position(current_price, pnl, self.last_qty)
                    self.last_signal = 0
                    self.position = 0
                    self.entry_price = None
                    self.last_qty = 0
                    self.entry_time = 0
                    # TP/SL 초기화
                    self.TP_initial = 0.005
                    self.TP_dynamic = 0.002

            # 한 줄로 대기로그 (중복 방지)
            position_status = {1: "LONG", -1: "SHORT", 0: "NO POSITION"}
            status_msg = f"[대기] {position_status[self.position]} 상태, Willr={willr:.1f}, RSI={rsi:.1f}, Vol/MA5={vol:.2f}/{vol_ma:.2f}"
            if len(self.trade_logs) == 0 or self.trade_logs[-1] != status_msg:
                self.trade_logs.append(status_msg)

            if self.balance <= 3.0: # 3달러 이하에서 운용 중지
                self.running = False
                self.trade_logs
