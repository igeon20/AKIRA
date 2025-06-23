import os
import time
from dotenv import load_dotenv
from binance.client import Client
import pandas as pd
import ta

load_dotenv()

class BinanceBot:
    MIN_NOTIONAL = 100  # BTCUSDT 기준

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
        self.max_position_ratio = 0.95
        self.balance = 50.0

        self.position = 0          # 1: LONG, -1: SHORT, 0: NO POSITION
        self.entry_price = None
        self.last_qty = 0
        self.entry_time = 0

        self.TP = 0.04     # +4%
        self.SL = -0.02    # -2%

        self.running = False
        self.trade_logs = ["🤖[봇초기화]🤖"]
        print(self.trade_logs[-1])

        try:
            self.client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)
            msg = f"[설정] 레버리지 {self.leverage}배 적용 완료."
            self.trade_logs.append(msg)
            print(msg)
        except Exception as e:
            msg = f"[레버리지 실패] {e}"
            self.trade_logs.append(msg)
            print(msg)

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
            msg = f"[가격수집실패] {e}"
            self.trade_logs.append(msg)
            print(msg)
            return None

    def get_realtime_price(self):
        try:
            price = float(self.client.futures_symbol_ticker(symbol=self.symbol)['price'])
            return price
        except Exception as e:
            msg = f"[실시간가격에러] {e}"
            self.trade_logs.append(msg)
            print(msg)
            return None

    def total_position_value(self, price=None):
        if self.position == 0 or self.last_qty == 0 or self.entry_price is None:
            return 0
        use_price = self.entry_price if price is None else price
        return abs(use_price * self.last_qty)

    def _calc_qty(self, price, factor=1.0):
        cur_pos_value = self.total_position_value(price)
        max_position_value = self.balance * self.max_position_ratio
        invest = max(self.balance * 0.1 * factor, 2.0)
        if cur_pos_value + invest > max_position_value:
            invest = max(min(max_position_value - cur_pos_value, invest), 0)
        raw_qty = invest / price
        qty = max(round(raw_qty, self.qty_precision), self.min_qty)
        if cur_pos_value + (qty * price) > max_position_value:
            qty = max(self.min_qty, round((max_position_value - cur_pos_value)/price, self.qty_precision))
        return qty

    def check_entry_signal(self, df):
        willr = float(df['Willr'].iloc[-1])
        rsi = float(df['RSI'].iloc[-1])
        vol = float(df['Volume'].iloc[-1])
        vol_ma = float(df['Vol_MA5'].iloc[-1])
        if (willr < -80) and (rsi < 43) and (vol > vol_ma * 1.05):
            return 1  # 롱
        elif (willr > -20) and (rsi > 57) and (vol > vol_ma * 1.05):
            return -1  # 숏
        else:
            return 0   # 진입 없음

    def _can_trade(self, price, qty):
        return price * qty >= self.MIN_NOTIONAL

    def _log_position_status(self, cur_price):
        if self.position != 0 and self.last_qty > 0 and self.entry_price is not None:
            pnl = ((cur_price - self.entry_price) / self.entry_price) if self.position == 1 else ((self.entry_price - cur_price) / self.entry_price)
            commission = abs(self.last_qty) * cur_price * 0.0004
            realised_pnl = ((cur_price - self.entry_price) if self.position == 1 else (self.entry_price - cur_price)) * self.last_qty
            pnl_pct = ((cur_price - self.entry_price) / self.entry_price * 100) if self.position == 1 else ((self.entry_price - cur_price) / self.entry_price * 100)
            status = (
                f"[포지션상태] {'LONG' if self.position == 1 else 'SHORT'} / 진입가 {self.entry_price:.2f} / 현시가 {cur_price:.2f} / 수량 {self.last_qty:.4f} / "
                f"원금기준손익:{pnl_pct:.2f}% / 실손익:{realised_pnl:.4f} USDT / 잔고 {self.balance:.2f}"
            )
            if len(self.trade_logs) == 0 or self.trade_logs[-1] != status:
                self.trade_logs.append(status)
                print(status)

    def start(self):
        self.running = True
        msg = "[시작] 전략 봇 가동"
        self.trade_logs.append(msg)
        print(msg)
        while self.running:
            df = self.fetch_ohlcv()
            if df is None:
                time.sleep(5)
                continue
            df['Willr'] = ta.momentum.williams_r(df['High'], df['Low'], df['Close'], lbp=14)
            df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
            df['Vol_MA5'] = df['Volume'].rolling(5).mean()

            willr = float(df['Willr'].iloc[-1])
            rsi = float(df['RSI'].iloc[-1])
            vol = float(df['Volume'].iloc[-1])
            vol_ma = float(df['Vol_MA5'].iloc[-1])

            # 실시간가
            current_price = self.get_realtime_price()
            if not current_price:
                current_price = float(df['Close'].iloc[-1])

            now_signal = self.check_entry_signal(df)
            now = time.time()

            # 진입/중복진입
            if now_signal != 0 and (self.position == 0 or now_signal != self.position):
                qty = self._calc_qty(current_price, 1.0)
                if self._can_trade(current_price, qty):
                    if self.position != 0:
                        self._forcibly_close_position(current_price, self.last_qty)
                        time.sleep(1)
                    self._enter_position("LONG" if now_signal == 1 else "SHORT", current_price, qty)
                    self.entry_time = now
                    self.position = now_signal
                    self.last_qty = qty
                else:
                    msg = f"[진입불가] 최소 notional 미만 (price*qty={current_price*qty:.2f} < {self.MIN_NOTIONAL})"
                    self.trade_logs.append(msg)
                    print(msg)

            if self.position != 0 and self.last_qty > 0 and self.entry_price is not None:
                if self.position == 1:  # LONG
                    tp_hit = current_price >= self.entry_price * (1 + self.TP)
                    sl_hit = current_price <= self.entry_price * (1 + self.SL)
                elif self.position == -1:  # SHORT
                    tp_hit = current_price <= self.entry_price * (1 - self.TP)
                    sl_hit = current_price >= self.entry_price * (1 - self.SL)
                else:
                    tp_hit = False
                    sl_hit = False
                if tp_hit or sl_hit:
                    self._forcibly_close_position(current_price, self.last_qty)

            self._log_position_status(current_price)
            position_status = {1: "LONG", -1: "SHORT", 0: "NO POSITION"}
            status_msg = f"[대기] {position_status[self.position]} 상태, Willr={willr:.1f}, RSI={rsi:.1f}, Vol/MA5={vol:.2f}/{vol_ma:.2f} 현가:{current_price:.2f}"
            if len(self.trade_logs) == 0 or self.trade_logs[-1] != status_msg:
                self.trade_logs.append(status_msg)
                print(status_msg)

            if self.balance <= 3.0:
                self.running = False
                msg = "[종료] 💀 잔고 소진 - 봇 자동 종료"
                self.trade_logs.append(msg)
                print(msg)
                break
            time.sleep(5)
        msg = "[종료] 봇 정지 끝"
        self.trade_logs.append(msg)
        print(msg)

    def stop(self):
        self.running = False
        msg = "[수동정지] 사용자 요청 봇 중지"
        self.trade_logs.append(msg)
        print(msg)

    def _enter_position(self, side, price, qty):
        try:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side="BUY" if side == "LONG" else "SELL",
                type="MARKET",
                quantity=qty
            )
            self.entry_price = price
            self.position = 1 if side == "LONG" else -1
            self.last_qty = qty
            msg1 = f"[진입] {side} @ {price:.2f} / 수량: {qty:.4f}"
            msg2 = f"잔고: {self.balance:.2f} USDT"
            self.trade_logs.append(msg1)
            self.trade_logs.append(msg2)
            print(msg1)
            print(msg2)
        except Exception as e:
            msg = f"[진입실패] {side} @ {price:.2f}: {e}"
            self.trade_logs.append(msg)
            print(msg)

    def _forcibly_close_position(self, price, qty):
        """
        모든 수단으로 무조건 포지션 종료!
        """
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
            msg1 = f"[청산] {side} MARKET @ {price:.2f} / 원금기준손익:{pnl_pct:.2f}% / 수량: {qty:.4f}"
            msg2 = f"[손익] 실손익:{realised_pnl:.4f} USDT (수수료:{commission:.4f}), 잔고:{self.balance:.2f} USDT"
            self.trade_logs.append(msg1)
            self.trade_logs.append(msg2)
            print(msg1)
            print(msg2)
            self._clear_position_state()
            return True
        except Exception as e1:
            msg = f"[청산실패] MARKET @ {price:.2f}: {e1}"
            self.trade_logs.append(msg)
            print(msg)
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
            self.trade_logs.append(msg)
            print(msg)
            self._clear_position_state()
            return True
        except Exception as e2:
            msg = f"[청산실패] LIMIT @ {price:.2f}: {e2}"
            self.trade_logs.append(msg)
            print(msg)
        self._clear_position_state()
        return False

    def _clear_position_state(self):
        self.position = 0
        self.entry_price = None
        self.last_qty = 0
        self.entry_time = 0
