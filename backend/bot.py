import os
import time
from dotenv import load_dotenv
from binance.client import Client
import pandas as pd
import numpy as np
import ta

load_dotenv()

class BinanceBot:
    MIN_NOTIONAL = 100
    SYMBOL = "BTCUSDT"
    QTY_PRECISION = 3
    MIN_QTY = 0.001
    LEVERAGE = 125
    MAX_POSITION_RATIO = 0.95
    INIT_BALANCE = 50.0

    TP = 0.04
    SL = -0.02

    def __init__(self):
        # 환경변수
        self.TESTNET_URL = os.getenv("BINANCE_BASE_URL")
        self.client = Client(
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_SECRET_KEY"),
            testnet=True
        )
        self.client.API_URL = self.TESTNET_URL

        # 거래 상태
        self.symbol = self.SYMBOL
        self.qty_precision = self.QTY_PRECISION
        self.min_qty = self.MIN_QTY
        self.leverage = self.LEVERAGE
        self.max_position_ratio = self.MAX_POSITION_RATIO
        self.balance = self.INIT_BALANCE
        self.position = 0
        self.entry_price = None
        self.last_qty = 0
        self.entry_time = 0

        self.running = False
        self.trade_logs = []
        print("🤖[봇초기화]🤖")

        try:
            self.client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)
            print(f"[설정] 레버리지 {self.leverage}배 적용 완료.")
        except Exception as e:
            print(f"[레버리지 실패] {e}")

    def fetch_ohlcv(self, interval="1m"):
        try:
            klines = self.client.futures_klines(symbol=self.symbol, interval=interval, limit=100)
            df = pd.DataFrame(klines, columns=[
                'timestamp','Open','High','Low','Close','Volume',
                'close_time','quote_vol','trades',
                'taker_base_vol','taker_quote_vol','ignore'
            ])
            df[['Open','High','Low','Close','Volume']] = df[['Open','High','Low','Close','Volume']].astype(float)
            return df
        except Exception as e:
            print(f"[가격수집실패] {e}")
            return None

    def get_realtime_price(self):
        # 실시간(틱) 가격
        try:
            ticker = self.client.futures_symbol_ticker(symbol=self.symbol)
            if ticker and 'price' in ticker:
                return float(ticker['price'])
            else:
                return None
        except Exception as e:
            print(f"[실시간가격에러] {e}")
            return None

    def _calc_qty(self, price, factor=1.0):
        cur_pos_value = abs(self.last_qty) * price if self.last_qty else 0
        max_position = self.balance * self.max_position_ratio
        invest = min(max(self.balance * 0.1 * factor, 2.0), max_position - cur_pos_value)
        raw_qty = invest / price
        qty = max(round(raw_qty, self.qty_precision), self.min_qty)
        # 재확인
        if (qty * price + cur_pos_value) > max_position:
            qty = max(self.min_qty, round((max_position - cur_pos_value) / price, self.qty_precision))
        return float(qty)

    def _can_trade(self, price, qty):
        return price * qty >= self.MIN_NOTIONAL and qty >= self.min_qty

    def _reset_position_state(self):
        self.position = 0
        self.entry_price = None
        self.last_qty = 0
        self.entry_time = 0

    def _log(self, msg):
        self.trade_logs.append(msg)
        print(msg)

    def check_entry_signal(self, df):
        # Willr, RSI, Vol MA 계산 후 nan 처리
        try:
            willr = float(df['Willr'].iloc[-1])
            rsi = float(df['RSI'].iloc[-1])
            vol = float(df['Volume'].iloc[-1])
            vol_ma = float(df['Vol_MA5'].iloc[-1])
        except (KeyError, IndexError, ValueError):
            return 0

        if np.isnan(willr) or np.isnan(rsi) or np.isnan(vol_ma):
            return 0

        # 예제 전략
        if (willr < -80) and (rsi < 43) and (vol > vol_ma * 1.05):
            return 1
        elif (willr > -20) and (rsi > 57) and (vol > vol_ma * 1.05):
            return -1
        else:
            return 0

    def _log_position_status(self, cur_price):
        if self.position == 0:
            return
        if self.last_qty > 0 and self.entry_price is not None:
            pnl = ((cur_price - self.entry_price) if self.position == 1 else (self.entry_price - cur_price)) * self.last_qty
            pnl_pct = ((cur_price - self.entry_price) / self.entry_price * 100) if self.position == 1 else ((self.entry_price - cur_price) / self.entry_price * 100)
            msg = f"[포지션상태] {'LONG' if self.position == 1 else 'SHORT'} | 진입가 {self.entry_price:.2f} | 현가 {cur_price:.2f} | 수량 {self.last_qty:.4f} | 손익 {pnl_pct:.2f}% | 실손익 {pnl:.4f} USDT | 잔고 {self.balance:.2f}"
            self._log(msg)

    def start(self):
        self.running = True
        self._log("[시작] 전략 봇 가동")
        pre_status_msg = ""
        while self.running:
            df = self.fetch_ohlcv()
            if df is None or len(df) < 20:
                time.sleep(3)
                continue
            # 지표계산
            df['Willr'] = ta.momentum.williams_r(df['High'], df['Low'], df['Close'], lbp=14)
            df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
            df['Vol_MA5'] = df['Volume'].rolling(5).mean()

            # nan 처리: 데이터 적을 때 신호내지 않음
            if np.any(pd.isnull(df[['Willr', 'RSI', 'Vol_MA5']].iloc[-1])):
                status_msg = f"[대기] 신호 적용 불가 (데이터 부족/NaN) 현가: ---"
                if status_msg != pre_status_msg:
                    self._log(status_msg)
                    pre_status_msg = status_msg
                time.sleep(3)
                continue

            willr = float(df['Willr'].iloc[-1])
            rsi = float(df['RSI'].iloc[-1])
            vol = float(df['Volume'].iloc[-1])
            vol_ma = float(df['Vol_MA5'].iloc[-1])

            current_price = self.get_realtime_price()
            if not current_price:
                current_price = float(df['Close'].iloc[-1])

            # 상태 메시지
            position_status = {1: "LONG", -1: "SHORT", 0: "NO POSITION"}
            status_msg = (
                f"[대기] {position_status[self.position]} | Willr={willr:.1f}, RSI={rsi:.1f}, "
                f"Vol/MA5={vol:.2f}/{vol_ma:.2f} | 현가:{current_price:.2f}"
            )
            if status_msg != pre_status_msg:
                self._log(status_msg)
                pre_status_msg = status_msg

            # 포지션 진입 조건 검토
            entry_signal = self.check_entry_signal(df)

            if entry_signal != 0 and (self.position == 0 or (self.position != entry_signal)):
                qty = self._calc_qty(current_price)
                if self._can_trade(current_price, qty):
                    if self.position != 0:
                        self._forcibly_close_position(current_price, self.last_qty)
                        time.sleep(1)
                    self._enter_position("LONG" if entry_signal == 1 else "SHORT", current_price, qty)
                    self.entry_time = time.time()
                    self.position = entry_signal
                    self.last_qty = qty
                    self.entry_price = current_price
                else:
                    self._log(f"[진입불가] 최소 Notional 미만 (price*qty={current_price*qty:.2f} < {self.MIN_NOTIONAL})")

            # 포지션 관리(익절/손절)
            if self.position != 0 and self.last_qty > 0 and self.entry_price is not None:
                # LONG
                if self.position == 1:
                    tp_hit = current_price >= self.entry_price * (1 + self.TP)
                    sl_hit = current_price <= self.entry_price * (1 + self.SL)
                # SHORT
                elif self.position == -1:
                    tp_hit = current_price <= self.entry_price * (1 - self.TP)
                    sl_hit = current_price >= self.entry_price * (1 - self.SL)
                else:
                    tp_hit = sl_hit = False
                if tp_hit:
                    self._log(f"[익절발동] {'LONG' if self.position==1 else 'SHORT'} | 진입가:{self.entry_price:.2f}, 현가:{current_price:.2f}")
                    self._forcibly_close_position(current_price, self.last_qty)
                elif sl_hit:
                    self._log(f"[손절발동] {'LONG' if self.position==1 else 'SHORT'} | 진입가:{self.entry_price:.2f}, 현가:{current_price:.2f}")
                    self._forcibly_close_position(current_price, self.last_qty)

            self._log_position_status(current_price)

            # 잔고 소진 시 봇 종료
            if self.balance <= 3.0:
                self.running = False
                self._log("[종료] 💀 잔고 소진 - 봇 종료")
                break

            time.sleep(5)
        self._log("[종료] 봇 정지 끝")

    def stop(self):
        self.running = False
        self._log("[수동정지] 사용자 요청 봇 중지")

    def _enter_position(self, side, price, qty):
        try:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side="BUY" if side == "LONG" else "SELL",
                type="MARKET",
                quantity=qty
            )
            self.position = 1 if side == "LONG" else -1
            self.entry_price = price
            self.last_qty = qty
            msg = f"[진입] {side} @ {price:.2f} / 수량: {qty:.4f}"
            self._log(msg)
            self._log(f"잔고: {self.balance:.2f} USDT")
        except Exception as e:
            msg = f"[진입실패] {side} @ {price:.2f}: {e}"
            self._log(msg)

    def _forcibly_close_position(self, price, qty):
        side = "SELL" if self.position == 1 else "BUY"
        try:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side=side,
                type="MARKET",
                quantity=qty
            )
            realised_pnl = ((price - self.entry_price) if self.position == 1 else (self.entry_price - price)) * qty
            commission = abs(qty) * price * 0.0004
            pnl_pct = ((price - self.entry_price) / self.entry_price * 100) if self.position == 1 else ((self.entry_price - price) / self.entry_price * 100)
            self.balance += realised_pnl - commission
            msg1 = f"[청산] {side} MARKET @ {price:.2f} | 손익:{pnl_pct:.2f}% | 수량:{qty:.4f}"
            msg2 = f"[손익] 실손익:{realised_pnl:.4f} USDT (수수료:{commission:.4f}), 잔고:{self.balance:.2f} USDT"
            self._log(msg1)
            self._log(msg2)
            self._reset_position_state()
            return True
        except Exception as e1:
            msg = f"[청산실패] MARKET @ {price:.2f}: {e1}"
            self._log(msg)
        try:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side=side,
                type="LIMIT",
                price=str(price),
                timeInForce="GTC",
                quantity=qty,
                reduceOnly=True
            )
            msg = f"[청산시도] LIMIT @ {price:.2f}(reduceOnly)"
            self._log(msg)
            self._reset_position_state()
            return True
        except Exception as e2:
            msg = f"[청산실패] LIMIT @ {price:.2f}: {e2}"
            self._log(msg)
        self._reset_position_state()
        return False

# 사용 예시
# bot = BinanceBot()
# bot.start()
