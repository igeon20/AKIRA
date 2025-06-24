import os
import time
from dotenv import load_dotenv
from binance.client import Client
import pandas as pd
import numpy as np
import ta

# Load environment variables from .env file
load_dotenv()

class BinanceBot:
    # --- Configuration Constants ---
    SYMBOL = "BTCUSDT"          # Trading pair
    QTY_PRECISION = 3           # Quantity decimal precision
    PRICE_PRECISION = 2         # Price decimal precision
    MIN_QTY = 0.001             # Minimum order quantity
    LEVERAGE = 125              # Desired leverage
    INIT_BALANCE = 50.0         # Initial virtual balance for PnL tracking

    TP = 0.04                   # Take-Profit percentage (4%)
    SL = -0.02                  # Stop-Loss percentage (-2%)

    def __init__(self):
        """
        Initializes the BinanceBot with API client, sets up trading parameters,
        and attempts to set leverage on Binance Futures.
        """
        # Initialize Binance Client using API key and secret from environment variables
        self.client = Client(
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_SECRET_KEY"),
            testnet=True  # Use testnet for safer development and testing
        )
        # Set the API URL based on environment variable (e.g., for testnet)
        self.client.API_URL = os.getenv("BINANCE_BASE_URL")

        # Trading parameters
        self.symbol = self.SYMBOL
        self.qty_precision = self.QTY_PRECISION
        self.price_precision = self.PRICE_PRECISION
        self.min_qty = self.MIN_QTY
        self.leverage = self.LEVERAGE
        self.balance = self.INIT_BALANCE # Current balance, updated after each trade

        # Position tracking variables
        self.position = 0          # Current position: 1 for long, -1 for short, 0 for no position
        self.entry_price = None    # Price at which the current position was entered
        self.last_qty = 0          # Quantity of the last executed trade
        self.entry_time = 0        # Timestamp of the last entry (currently unused but good to have)

        self.running = False       # Bot running status
        self.trade_logs = []       # List to store trade logs

        # Attempt to set leverage on Binance Futures account
        try:
            # Note: This sets the leverage for the symbol on the account.
            # It's a one-time setting per symbol per account.
            self.client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)
            self._log(f"[설정] 레버리지 {self.leverage}x 설정 완료.")
        except Exception as e:
            self._log(f"[오류] 레버리지 설정 실패: {e}")

    def _log(self, message):
        """
        Logs messages with a timestamp to the console and stores them in trade_logs.
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        self.trade_logs.append(log_entry)

    def start_bot(self):
        """
        Starts the trading bot. The bot continuously fetches data,
        gets signals, and manages positions.
        """
        self.running = True
        self._log("[봇 시작] 트레이딩 루프 시작.")

        while self.running:
            df = self.fetch_data()
            if df is None:
                self._log("[경고] 데이터프레임 없음. 5초 후 재시도.")
                time.sleep(5) # Wait before retrying data fetch
                continue

            signal = self.get_signal(df)
            current_price = self.get_price()

            if current_price is None:
                self._log("[경고] 현재가 조회 실패. 5초 후 재시도.")
                time.sleep(5)
                continue

            # Log current status concisely
            self._log(f"[상태] 신호: {signal}, 현재가: {current_price:.{self.PRICE_PRECISION}f}, 포지션: {self.position}")

            # --- Trading Logic: Enter Position ---
            if signal == 1: # Long signal
                if self.position <= 0: # Not in a long position or in a short position
                    self._log(f"[진입 시도] 롱 (이전 포지션: {'숏' if self.position == -1 else '없음'})")
                    # Close existing short position before opening a long one
                    if self.position == -1:
                        self.close_position(current_price, "신호 전환")
                    
                    qty = self.calc_max_qty(current_price)
                    if qty > self.min_qty: # Ensure calculated quantity is tradeable
                        self.enter_position("BUY", qty, current_price)
                    else:
                        self._log(f"[진입 실패] 계산된 수량 ({qty})이 최소 수량 ({self.min_qty})보다 작습니다.")
                else:
                    self._log("[정보] 롱 신호 발생, 이미 롱 포지션 중.")
            elif signal == -1: # Short signal
                if self.position >= 0: # Not in a short position or in a long position
                    self._log(f"[진입 시도] 숏 (이전 포지션: {'롱' if self.position == 1 else '없음'})")
                    # Close existing long position before opening a short one
                    if self.position == 1:
                        self.close_position(current_price, "신호 전환")

                    qty = self.calc_max_qty(current_price)
                    if qty > self.min_qty: # Ensure calculated quantity is tradeable
                        self.enter_position("SELL", qty, current_price)
                    else:
                        self._log(f"[진입 실패] 계산된 수량 ({qty})이 최소 수량 ({self.min_qty})보다 작습니다.")
                else:
                    self._log("[정보] 숏 신호 발생, 이미 숏 포지션 중.")
            else: # No signal or neutral
                self._log("[정보] 신호 없음.")

            # --- Position Management (TP/SL) ---
            self.manage_position(current_price)
            
            time.sleep(5) # Wait for 5 seconds before the next loop iteration

    def stop(self):
        """
        Stops the trading bot gracefully.
        """
        self.running = False
        self._log("[봇 정지] 트레이딩 루프 종료.")

    def fetch_data(self):
        """
        Fetches 1-minute klines data from Binance, calculates indicators, and returns a DataFrame.
        """
        try:
            # Fetch 100 historical 1-minute klines
            klines = self.client.futures_klines(symbol=self.symbol, interval="1m", limit=100)
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'Open', 'High', 'Low', 'Close', 'Volume',
                'close_time', 'quote_vol', 'trades',
                'taker_base_vol', 'taker_quote_vol', 'ignore'
            ])
            # Convert necessary columns to float for calculations
            df[['Open', 'High', 'Low', 'Close', 'Volume']] = df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)
            
            # Calculate technical indicators
            df['Willr'] = ta.momentum.williams_r(df['High'], df['Low'], df['Close'], lbp=14)
            df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
            df['Vol_MA5'] = df['Volume'].rolling(5).mean() # 5-period Simple Moving Average of Volume
            
            # Drop any rows with NaN values that might result from indicator calculation (e.g., first few rows)
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
        """
        if df is None or df.empty:
            return 0

        # Get the latest indicator values
        willr = df['Willr'].iloc[-1]
        rsi = df['RSI'].iloc[-1]
        vol = df['Volume'].iloc[-1]
        vol_ma = df['Vol_MA5'].iloc[-1]

        # Check for NaN values in indicators, return neutral if any are NaN
        if np.isnan(willr) or np.isnan(rsi) or np.isnan(vol_ma):
            self._log(f"[정보] 지표에 NaN 값 포함: Willr={willr:.2f}, RSI={rsi:.2f}, Vol_MA={vol_ma:.2f}. 신호 없음.")
            return 0

        # --- Signal Logic ---
        # Long signal: Williams %R indicates oversold, RSI indicates oversold, and volume confirms
        if willr < -85 and rsi < 38 and vol > vol_ma * 1.05:
            self._log(f"[신호 발생] 롱 (Willr:{willr:.2f} < -85, RSI:{rsi:.2f} < 38, Vol:{vol:.2f} > Vol_MA:{vol_ma:.2f}*1.05)")
            return 1
        # Short signal: Williams %R indicates overbought, RSI indicates overbought, and volume confirms
        elif willr > -15 and rsi > 62 and vol > vol_ma * 1.05:
            self._log(f"[신호 발생] 숏 (Willr:{willr:.2f} > -15, RSI:{rsi:.2f} > 62, Vol:{vol:.2f} > Vol_MA:{vol_ma:.2f}*1.05)")
            return -1
        # Neutral signal if no strong signal is generated
        return 0

    def get_price(self):
        """
        Fetches the current ticker price for the trading symbol.
        """
        try:
            price = float(self.client.futures_symbol_ticker(symbol=self.symbol)['price'])
            return price
        except Exception as e:
            self._log(f"[오류] 현재가 조회 실패: {e}")
            return None

    def calc_max_qty(self, price):
        """
        Calculates the maximum tradeable quantity based on current balance, leverage, and current price.
        Ensures the quantity is above the minimum and respects precision.
        """
        if price is None or price == 0:
            self._log("[오류] 유효하지 않은 가격으로 수량 계산 불가.")
            return 0
        
        # Calculate notional value (capital * leverage)
        notional = self.balance * self.leverage
        # Calculate raw quantity
        raw_qty = notional / price
        # Round quantity to precision and ensure it's at least MIN_QTY
        qty = round(max(raw_qty, self.min_qty), self.qty_precision)
        self._log(f"[계산] 최대 진입 수량: {qty} {self.symbol} (자산: {self.balance:.2f} USDT, 레버리지: {self.leverage}x)")
        return qty

    def enter_position(self, side, qty, price):
        """
        Executes a market order to enter a position (BUY for long, SELL for short).
        Updates internal position tracking variables upon successful order.
        """
        try:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side=side,
                type="MARKET",
                quantity=qty
            )
            # Update internal position state after successful order
            self.position = 1 if side == "BUY" else -1
            self.entry_price = price # Use the current market price as entry price
            self.last_qty = qty
            
            pos_type = "롱" if self.position == 1 else "숏"
            self._log(f"[진입 성공] {pos_type} 포지션. 수량: {qty} {self.symbol}, 진입 가격: {price:.{self.PRICE_PRECISION}f} USDT.")
            # Optionally log the full order response for detailed debugging
            # self._log(f"[DEBUG] Order response: {order}") 
        except Exception as e:
            self._log(f"[진입 실패] {side} 주문 실패: {e}. 수량: {qty}, 가격: {price}")
            # Ensure position is reset if entry fails to avoid false positive position state
            self.position = 0 
            self.entry_price = None
            self.last_qty = 0

    def close_position(self, price, reason=""):
        """
        Closes the current open position. Calculates PnL and updates the balance.
        """
        if self.position == 0:
            return # No position to close

        # Determine the opposite side to close the current position
        side_to_close = "SELL" if self.position == 1 else "BUY"
        current_pos_type = "롱" if self.position == 1 else "숏"
        
        try:
            # Execute a market order to close the position
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side=side_to_close,
                type="MARKET",
                quantity=round(self.last_qty, self.qty_precision) # Ensure precision for closing order
            )
            
            # --- PnL Calculation (Simplified for virtual balance tracking) ---
            # PnL for long position: (exit_price - entry_price) * quantity
            # PnL for short position: (entry_price - exit_price) * quantity
            pnl_raw = ((price - self.entry_price) if self.position == 1 else (self.entry_price - price)) * self.last_qty
            
            # Simple commission calculation (0.04% for taker on Binance Futures)
            commission = price * self.last_qty * 0.0004
            
            # Update balance
            self.balance += (pnl_raw - commission)
            
            self._log(
                f"[청산 성공] {current_pos_type} 포지션 청산 ({side_to_close} 주문). "
                f"수량: {self.last_qty} {self.symbol}, 청산 가격: {price:.{self.PRICE_PRECISION}f} USDT. "
                f"원인: {reason}. "
                f"수익(PnL): {pnl_raw:.4f} USDT, 수수료: {commission:.4f} USDT, "
                f"순수익: {(pnl_raw - commission):.4f} USDT. "
                f"현재 잔고: {self.balance:.2f} USDT."
            )
            # Optionally log the full order response
            # self._log(f"[DEBUG] Close order response: {order}")

        except Exception as e:
            self._log(f"[청산 실패] {current_pos_type} 포지션 {side_to_close} 주문 실패: {e}. "
                      f"수량: {self.last_qty}, 가격: {price}. 원인: {reason}")
        finally:
            # Always reset position state regardless of success/failure to avoid stale states
            self.position = 0
            self.entry_price = None
            self.last_qty = 0

    def manage_position(self, current_price):
        """
        Manages an open position by checking for Take-Profit (TP) or Stop-Loss (SL) conditions.
        """
        if self.position == 0 or current_price is None:
            return # No open position or invalid price

        # Calculate TP and SL prices based on entry price and defined percentages
        if self.position == 1: # Long position
            tp_price = self.entry_price * (1 + self.TP)
            sl_price = self.entry_price * (1 + self.SL)
            
            # Check if current price hits TP or SL
            if current_price >= tp_price:
                self._log(f"[TP 도달] 롱 포지션 청산 (TP: {tp_price:.{self.PRICE_PRECISION}f}, 현재가: {current_price:.{self.PRICE_PRECISION}f})")
                self.close_position(current_price, "TP 도달")
            elif current_price <= sl_price:
                self._log(f"[SL 도달] 롱 포지션 청산 (SL: {sl_price:.{self.PRICE_PRECISION}f}, 현재가: {current_price:.{self.PRICE_PRECISION}f})")
                self.close_position(current_price, "SL 도달")
            else:
                self._log(f"[포지션 관리] 롱 포지션 유지. 진입: {self.entry_price:.{self.PRICE_PRECISION}f}, 현재: {current_price:.{self.PRICE_PRECISION}f}, TP: {tp_price:.{self.PRICE_PRECISION}f}, SL: {sl_price:.{self.PRICE_PRECISION}f}")

        elif self.position == -1: # Short position
            tp_price = self.entry_price * (1 - self.TP) # For short, TP is below entry
            sl_price = self.entry_price * (1 - self.SL) # For short, SL is above entry

            # Check if current price hits TP or SL
            if current_price <= tp_price:
                self._log(f"[TP 도달] 숏 포지션 청산 (TP: {tp_price:.{self.PRICE_PRECISION}f}, 현재가: {current_price:.{self.PRICE_PRECISION}f})")
                self.close_position(current_price, "TP 도달")
            elif current_price >= sl_price:
                self._log(f"[SL 도달] 숏 포지션 청산 (SL: {sl_price:.{self.PRICE_PRECISION}f}, 현재가: {current_price:.{self.PRICE_PRECISION}f})")
                self.close_position(current_price, "SL 도달")
            else:
                self._log(f"[포지션 관리] 숏 포지션 유지. 진입: {self.entry_price:.{self.PRICE_PRECISION}f}, 현재: {current_price:.{self.PRICE_PRECISION}f}, TP: {tp_price:.{self.PRICE_PRECISION}f}, SL: {sl_price:.{self.PRICE_PRECISION}f}")

# Example usage (for local testing, not used by api.py directly)
# if __name__ == "__main__":
#     bot = BinanceBot()
#     bot.start_bot()
