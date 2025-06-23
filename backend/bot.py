import os
import time
from dotenv import load_dotenv
from binance.client import Client
import pandas as pd
import ta

load_dotenv()

class BinanceBot:
    MIN_NOTIONAL = 100  # BTCUSDT 기준, 바이낸스 상품마다 다름! (다른 코인 쓸땐 반드시 확인/수정!)

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

        self.TP_initial = 0.04     # +4%
        self.TP_adjusted = 0.02    # +2%
        self.SL = -0.02            # -2% (TP, SL - 곱연산/점진적 조정 완전 제거)

        self.running = False
        self.trade_logs = ["🤖[봇초기화]🤖 리스크 관리 + 진입 신호 상세 기록"]

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
                'close_time','quote_vol','trades',
                'taker_base_vol','taker_quote_vol','ignore'
            ])
            df[['Open','High','Low','Close','Volume']] = df[['Open','High','Low','Close','Volume']].astype(float)
            return df
        except Exception as e:
            self.trade_logs.append(f"[가격수집실패] {e}")
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
        # 진입 신호 (예제 신호, 필요하다면 조정하세요)
        if (willr < -80) and (rsi < 43) and (vol > vol_ma * 1.05):
            return 1  # 롱
        elif (willr > -20) and (rsi > 57) and (vol > vol_ma * 1.05):
            return -1  # 숏
        else:
            return 0   # 진입 없음

    def adjust_tp(self):
        if self.position == 0 or self.entry_time == 0:
            return self.TP_initial
        elapsed = time.time() - self.entry_time
        return self.TP_initial if elapsed < 3*60 else self.TP_adjusted

    def _can_trade(self, price, qty):
        # 최소 주문 금액(Notional) 체크
        return price * qty >= self.MIN_NOTIONAL

    def _log_position_status(self, cur_price):
        if self.position != 0 and self.last_qty > 0 and self.entry_price is not None:
            pnl = ((cur_price - self.entry_price) / self.entry_price) \
                if self.position == 1 else ((self.entry_price - cur_price) / self.entry_price)
            pnl_pct = pnl * self.leverage * 100

            commission = abs(self.last_qty) * cur_price * 0.0004  # 왕복 0.04%
            profit = self.balance * (pnl * self.leverage) - commission
            expected_balance = self.balance + profit
            status = "[포지션상태] {side} / 진입가 {entry} / 현시가 {cur} / 수량 {qty} / 손익:{pnl:.2f}% / 잔고 {bal:.2f} USDT / 예상잔고 {exp_bal:.2f} USDT".format(
                side=("LONG" if self.position == 1 else "SHORT"),
                entry=round(self.entry_price,2),
                cur=round(cur_price,2),
                qty=round(self.last_qty,4),
                pnl=pnl_pct,
                bal=self.balance,
                exp_bal=expected_balance
            )
            if len(self.trade_logs) == 0 or self.trade_logs[-1] != status:
                self.trade_logs.append(status)

    def start(self):
        self.running = True
        self.trade_logs.append("[시작] 전략 봇 가동 (상태/진입불가 사유/에러 모두 기록)")
        while self.running:
            df = self.fetch_ohlcv()
            if df is None:
                time.sleep(5)
                continue
            df['Willr'] = ta.momentum.williams_r(df['High'], df['Low'], df['Close'], lbp=14)
            df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
            df['Vol_MA5'] = df['Volume'].rolling(5).mean()

            current_price = float(df['Close'].iloc[-1])
            willr = float(df['Willr'].iloc[-1])
            rsi = float(df['RSI'].iloc[-1])
            vol = float(df['Volume'].iloc[-1])
            vol_ma = float(df['Vol_MA5'].iloc[-1])

            now_signal = self.check_entry_signal(df)
            now = time.time()
            tp = self.adjust_tp()
            sl = self.SL

            # 진입/중복진입 로직 (TP/SL 조건만, 추가 진입은 비활성화)
            if now_signal != 0 and (self.position == 0 or now_signal != self.position):
                qty = self._calc_qty(current_price, 1.0)
                if self._can_trade(current_price, qty):
                    if self.position != 0:
                        pnl = ((current_price - self.entry_price) / self.entry_price) if self.position == 1 \
                            else ((self.entry_price - current_price) / self.entry_price)
                        if self._can_trade(current_price, self.last_qty):
                            self._close_position(current_price, pnl, self.last_qty)
                        else:
                            self.trade_logs.append(
                                f"[청산불가] 최소 notional 미만 (price*qty={current_price*self.last_qty:.2f} < {self.MIN_NOTIONAL}), 포지션 강제 종료 없이 감시중."
                            )
                        time.sleep(1)
                    self._enter_position("LONG" if now_signal == 1 else "SHORT", current_price, qty)
                    self.entry_time = now
                    self.position = now_signal
                    self.last_qty = qty
                else:
                    self.trade_logs.append(
                        f"[진입불가] 최소 notional 미만 (price*qty={current_price*qty:.2f} < {self.MIN_NOTIONAL}), 주문안함."
                    )

            # 청산 조건 (TP, SL)
            if self.position != 0 and self.last_qty > 0:
                tp = self.adjust_tp()
                pnl = ((current_price - self.entry_price) / self.entry_price) if self.position == 1 \
                    else ((self.entry_price - current_price) / self.entry_price)
                take_profit_hit = pnl >= tp
                stop_loss_hit = pnl <= sl

                if take_profit_hit or stop_loss_hit:
                    if self._can_trade(current_price, self.last_qty):
                        self._close_position(current_price, pnl, self.last_qty)
                    else:
                        self.trade_logs.append(
                            f"[청산불가] 최소 notional 미만 (price*qty={current_price*self.last_qty:.2f} < {self.MIN_NOTIONAL}), 포지션 강제 종료 없이 감시중."
                        )
                    self.position = 0
                    self.entry_price = None
                    self.last_qty = 0
                    self.entry_time = 0

            self._log_position_status(current_price)
            position_status = {1: "LONG", -1: "SHORT", 0: "NO POSITION"}
            status_msg = f"[대기] {position_status[self.position]} 상태, Willr={willr:.1f}, RSI={rsi:.1f}, Vol/MA5={vol:.2f}/{vol_ma:.2f} 현가:{current_price:.2f}"
            if len(self.trade_logs) == 0 or self.trade_logs[-1] != status_msg:
                self.trade_logs.append(status_msg)

            if self.balance <= 3.0:
                self.running = False
                self.trade_logs.append("[종료] 💀 잔고 소진 - 봇 자동 종료")
                break

            time.sleep(5)

        self.trade_logs.append("[종료] 봇 정지 끝")

    def stop(self):
        self.running = False
        self.trade_logs.append("[수동정지] 사용자 요청 봇 중지")

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
            self.trade_logs.append(f"[진입] {side} @ {price:.2f} / 수량: {qty:.4f}")
            self.trade_logs.append(f"잔고: {self.balance:.2f} USDT")
        except Exception as e:
            self.trade_logs.append(f"[진입실패] {side} @ {price:.2f}: {e}")

    def _close_position(self, price, pnl, qty):
        side = "SELL" if self.position == 1 else "BUY"
        try:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side=side,
                type="MARKET",
                quantity=qty
            )
            commission = abs(qty) * price * 0.0004  # 왕복 0.04%
            profit = self.balance * (pnl * self.leverage) - commission
            self.balance += profit
            pnl_pct = pnl * self.leverage * 100
            self.trade_logs.append(f"[청산] {'LONG' if self.position == 1 else 'SHORT'} CLOSE @ {price:.2f} / 손익: {pnl_pct:.2f}% / 수량: {qty:.4f}")
            self.trade_logs.append(f"[손익] {pnl*100:.2f}% (레버리지:{self.leverage}배), {profit:.2f} → 잔고:{self.balance:.2f} USDT")
        except Exception as e:
            self.trade_logs.append(f"[청산실패] @ {price:.2f}: {e}")
        self.position = 0
        self.entry_price = None
        self.last_qty = 0
        self.entry_time = 0
