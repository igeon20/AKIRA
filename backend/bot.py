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
    INIT_BALANCE = 50.0

    # TP 값을 0.04 (4%)에서 0.03 (3%)로 조정하여 더 빠른 익절 유도
    TP = 0.02 
    SL = -0.01

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
        self.last_qty = 0
        self.entry_time = 0

        self.running = False
        self.trade_logs = []

        try:
            self.client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)
            self._log(f"[설정] 레버리지 {self.leverage}x 설정 완료.")
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

        while self.running:
            df = self.fetch_data()
            if df is None:
                self._log("[경고] 데이터프레임 없음. 5초 후 재시도.")
                time.sleep(5)
                continue

            signal = self.get_signal(df)
            current_price = self.get_price()

            if current_price is None:
                self._log("[경고] 현재가 조회 실패. 5초 후 재시도.")
                time.sleep(5)
                continue

            self._log(f"[상태] 신호: {signal}, 현재가: {current_price:.{self.PRICE_PRECISION}f}, 포지션: {self.position}")

            if signal == 1: # Long signal
                if self.position <= 0:
                    self._log(f"[진입 시도] 롱 (이전 포지션: {'숏' if self.position == -1 else '없음'})")
                    if self.position == -1:
                        self.close_position(current_price, "신호 전환")
                    
                    qty = self.calc_max_qty(current_price)
                    if qty > self.min_qty:
                        self.enter_position("BUY", qty, current_price)
                    else:
                        self._log(f"[진입 실패] 계산된 수량 ({qty})이 최소 수량 ({self.min_qty})보다 작습니다.")
                else:
                    self._log("[정보] 롱 신호 발생, 이미 롱 포지션 중.")
            elif signal == -1: # Short signal
                if self.position >= 0:
                    self._log(f"[진입 시도] 숏 (이전 포지션: {'롱' if self.position == 1 else '없음'})")
                    if self.position == 1:
                        self.close_position(current_price, "신호 전환")

                    qty = self.calc_max_qty(current_price)
                    if qty > self.min_qty:
                        self.enter_position("SELL", qty, current_price)
                    else:
                        self._log(f"[진입 실패] 계산된 수량 ({qty})이 최소 수량 ({self.min_qty})보다 작습니다.")
                else:
                    self._log("[정보] 숏 신호 발생, 이미 숏 포지션 중.")
            else:
                self._log("[정보] 신호 없음.")

            self.manage_position(current_price)
            time.sleep(5)

    def stop(self):
        self.running = False
        self._log("[봇 정지] 트레이딩 루프 종료.")

    def fetch_data(self):
        try:
            klines = self.client.futures_klines(symbol=self.symbol, interval="1m", limit=100)
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'Open', 'High', 'Low', 'Close', 'Volume',
                'close_time', 'quote_vol', 'trades',
                'taker_base_vol', 'taker_quote_vol', 'ignore'
            ])
            df[['Open','High','Low','Close','Volume']] = df[['Open','High','Low','Close','Volume']].astype(float)
            
            df['Willr'] = ta.momentum.williams_r(df['High'], df['Low'], df['Close'], lbp=14)
            df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
            df['Vol_MA5'] = df['Volume'].rolling(5).mean()
            
            df.dropna(inplace=True) 
            
            if df.empty:
                self._log("[경고] 데이터프레임이 비어있습니다. 지표 계산에 필요한 데이터가 부족할 수 있습니다.")
                return None
            return df
        except Exception as e:
            self._log(f"[오류] 데이터 수집 실패: {e}")
            return None

    def get_signal(self, df):
        """
        Generates a trading signal (1 for long, -1 for short, 0 for neutral)
        based on Williams %R, RSI, and Volume confirmation.
        Adjusted conditions for potentially more frequent signals.
        """
        if df is None or df.empty:
            return 0

        willr = df['Willr'].iloc[-1]
        rsi = df['RSI'].iloc[-1]
        vol = df['Volume'].iloc[-1]
        vol_ma = df['Vol_MA5'].iloc[-1]

        if np.isnan(willr) or np.isnan(rsi) or np.isnan(vol_ma):
            self._log(f"[정보] 지표에 NaN 값 포함: Willr={willr:.2f}, RSI={rsi:.2f}, Vol_MA={vol_ma:.2f}. 신호 없음.")
            return 0

        # --- ADJUSTED SIGNAL LOGIC ---
        # Long signal: Williams %R indicates oversold, RSI indicates oversold, and volume confirms
        # Adjusted: Willr < -75 (from -85), RSI < 40 (from 38), Vol > Vol_MA * 1.02 (from 1.05)
        if willr < -70 and rsi < 40 and vol > vol_ma * 1.02:
            self._log(f"[신호 발생] 롱 (Willr:{willr:.2f} < -70, RSI:{rsi:.2f} < 40, Vol:{vol:.2f} > Vol_MA:{vol_ma:.2f}*1.02)")
            return 1
        # Short signal: Williams %R indicates overbought, RSI indicates overbought, and volume confirms
        # Adjusted: Willr > -25 (from -15), RSI > 60 (from 62), Vol > Vol_MA * 1.02 (from 1.05)
        elif willr > -30 and rsi > 60 and vol > vol_ma * 1.02:
            self._log(f"[신호 발생] 숏 (Willr:{willr:.2f} > -30, RSI:{rsi:.2f} > 60, Vol:{vol:.2f} > Vol_MA:{vol_ma:.2f}*1.02)")
            return -1
        
        return 0

    def get_price(self):
        try:
            price = float(self.client.futures_symbol_ticker(symbol=self.symbol)['price'])
            return price
        except Exception as e:
            self._log(f"[오류] 현재가 조회 실패: {e}")
            return None

    def calc_max_qty(self, price):
        if price is None or price == 0:
            self._log("[오류] 유효하지 않은 가격으로 수량 계산 불가.")
            return 0
        
        notional = self.balance * self.leverage
        raw_qty = notional / price
        qty = round(max(raw_qty, self.min_qty), self.qty_precision)
        self._log(f"[계산] 최대 진입 수량: {qty} {self.symbol} (자산: {self.balance:.2f} USDT, 레버리지: {self.leverage}x)")
        return qty

    def enter_position(self, side, qty, price):
        try:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side=side,
                type="MARKET",
                quantity=qty
            )
            self.position = 1 if side == "BUY" else -1
            self.entry_price = price
            self.last_qty = qty
            
            pos_type = "롱" if self.position == 1 else "숏"
            self._log(f"[진입 성공] {pos_type} 포지션. 수량: {qty} {self.symbol}, 진입 가격: {price:.{self.PRICE_PRECISION}f} USDT.")
        except Exception as e:
            self._log(f"[진입 실패] {side} 주문 실패: {e}. 수량: {qty}, 가격: {price}")
            self.position = 0 
            self.entry_price = None
            self.last_qty = 0

    def close_position(self, price, reason=""):
        if self.position == 0:
            return

        side_to_close = "SELL" if self.position == 1 else "BUY"
        current_pos_type = "롱" if self.position == 1 else "숏"
        
        try:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side=side_to_close,
                type="MARKET",
                quantity=round(self.last_qty, self.qty_precision)
            )
            
            # PnL 계산 (수수료 포함)
            pnl_raw = ((price - self.entry_price) if self.position == 1 else (self.entry_price - price)) * self.last_qty
            commission = price * self.last_qty * 0.0004 # Binance Futures taker fee
            
            self.balance += (pnl_raw - commission) # 잔고 업데이트
            
            self._log(
                f"[청산 성공] {current_pos_type} 포지션 청산 ({side_to_close} 주문). "
                f"수량: {self.last_qty} {self.symbol}, 청산 가격: {price:.{self.PRICE_PRECISION}f} USDT. "
                f"원인: {reason}. "
                f"수익(PnL): {pnl_raw:.4f} USDT, 수수료: {commission:.4f} USDT, "
                f"순수익: {(pnl_raw - commission):.4f} USDT. "
                f"현재 잔고: {self.balance:.2f} USDT."
            )
        except Exception as e:
            self._log(f"[청산 실패] {current_pos_type} 포지션 {side_to_close} 주문 실패: {e}. "
                      f"수량: {self.last_qty}, 가격: {price}. 원인: {reason}")
        finally:
            self.position = 0
            self.entry_price = None
            self.last_qty = 0

    def manage_position(self, current_price):
        if self.position == 0 or current_price is None:
            return

        # 현재 포지션 손익 계산
        # 롱 포지션: (현재가 - 진입가) * 수량
        # 숏 포지션: (진입가 - 현재가) * 수량
        current_pnl = ((current_price - self.entry_price) if self.position == 1 else \
                       (self.entry_price - current_price)) * self.last_qty
        
        # 레버리지를 고려한 현재 예상 자산
        # 초기 자산 + 미실현 손익
        estimated_balance = self.balance + current_pnl

        if self.position == 1: # Long position
            tp_price = self.entry_price * (1 + self.TP)
            sl_price = self.entry_price * (1 + self.SL)
            
            # 포지션 유지 중 로그에 손익과 자산 정보 추가
            self._log(
                f"[포지션 관리] 롱 포지션 유지. "
                f"진입: {self.entry_price:.{self.PRICE_PRECISION}f}, 현재: {current_price:.{self.PRICE_PRECISION}f}, "
                f"TP: {tp_price:.{self.PRICE_PRECISION}f}, SL: {sl_price:.{self.PRICE_PRECISION}f}. "
                f"예상 손익: {current_pnl:.4f} USDT, 예상 총 자산: {estimated_balance:.2f} USDT."
            )

            if current_price >= tp_price:
                self._log(f"[TP 도달] 롱 포지션 청산 (TP: {tp_price:.{self.PRICE_PRECISION}f}, 현재가: {current_price:.{self.PRICE_PRECISION}f})")
                self.close_position(current_price, "TP 도달")
            elif current_price <= sl_price:
                self._log(f"[SL 도달] 롱 포지션 청산 (SL: {sl_price:.{self.PRICE_PRECISION}f}, 현재가: {current_price:.{self.PRICE_PRECISION}f})")
                self.close_position(current_price, "SL 도달")

        elif self.position == -1: # Short position
            tp_price = self.entry_price * (1 - self.TP)
            sl_price = self.entry_price * (1 - self.SL)

            # 포지션 유지 중 로그에 손익과 자산 정보 추가
            self._log(
                f"[포지션 관리] 숏 포지션 유지. "
                f"진입: {self.entry_price:.{self.PRICE_PRECISION}f}, 현재: {current_price:.{self.PRICE_PRECISION}f}, "
                f"TP: {tp_price:.{self.PRICE_PRECISION}f}, SL: {sl_price:.{self.PRICE_PRECISION}f}. "
                f"예상 손익: {current_pnl:.4f} USDT, 예상 총 자산: {estimated_balance:.2f} USDT."
            )

            if current_price <= tp_price:
                self._log(f"[TP 도달] 숏 포지션 청산 (TP: {tp_price:.{self.PRICE_PRECISION}f}, 현재가: {current_price:.{self.PRICE_PRECISION}f})")
                self.close_position(current_price, "TP 도달")
            elif current_price >= sl_price:
                self._log(f"[SL 도달] 숏 포지션 청산 (SL: {sl_price:.{self.PRICE_PRECISION}f}, 현재가: {current_price:.{self.PRICE_PRECISION}f})")
                self.close_position(current_price, "SL 도달")
