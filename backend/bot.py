# app/bot/trader.py
import time
import pandas as pd
from app.core.config import settings
from app.bot.exchange import Exchange
from app.bot.indicators import (
    calculate_rsi, calculate_bollinger_bands, calculate_bb_width, calculate_atr
)

class Trader:
    def __init__(self):
        self.exchange = Exchange()
        self.trade_logs = []
        self.bb_width_history = pd.Series(dtype=float)

    def log_trade(self, message):
        log_message = f"[{pd.Timestamp.now(tz='Asia/Seoul').strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        print(log_message)
        self.trade_logs.append(log_message)
        if len(self.trade_logs) > 200:
            self.trade_logs.pop(0)

    def run_trading_cycle(self):
        self.log_trade("="*40)
        self.log_trade("🚀 새로운 사이클 시작...")

        if self.exchange.get_current_position():
            self.log_trade("📊 포지션 보유 중... TP/SL 대기.")
            return

        self.log_trade("🧐 신규 진입 기회를 탐색합니다.")
        df = self.exchange.get_ohlcv(limit=200)
        
        # --- 1차 지표 계산 (지난 캔들 기준) ---
        rsi = calculate_rsi(df['close'], settings.RSI_PERIOD)
        upper_band, middle_band, lower_band = calculate_bollinger_bands(df['close'], settings.BB_PERIOD, settings.BB_STD_DEV)
        atr = calculate_atr(df['high'], df['low'], df['close'], settings.ATR_PERIOD)
        
        side = None
        strategy_used = ""

        # --- 전략 탐색 ---
        if settings.USE_BB_BREAKOUT_STRATEGY:
            # ... (BB Breakout 로직은 생략, 필요시 이전 코드 참조) ...
            pass

        if side is None and settings.USE_RSI_REVERSAL_STRATEGY:
            self.log_trade(f"📈 RSI 상태 - 현재: {rsi:.2f} (진입 기준: <{settings.RSI_OVERSOLD} or >{settings.RSI_OVERBOUGHT})")
            if rsi < settings.RSI_OVERSOLD:
                side = 'buy'
                strategy_used = "RSI Reversal Long"
            elif rsi > settings.RSI_OVERBOUGHT:
                side = 'sell'
                strategy_used = "RSI Reversal Short"
        
        # --- 진입 실행 로직 (핵심 수정 부분) ---
        if side:
            self.log_trade(f"🎯 진입 조건 충족! ({strategy_used})")
            try:
                # 1. 가장 최신 실시간 가격을 다시 조회
                live_price = self.exchange.get_current_price()
                self.log_trade(f"   > 실시간 가격 확인: ${live_price:.2f}")

                # 2. 실시간 가격 기준으로 수량 재계산 (더 정확한 리스크 관리)
                balance = self.exchange.get_balance()
                risk_amount_usdt = balance * settings.RISK_PER_TRADE
                trade_amount = risk_amount_usdt / atr
                
                if trade_amount <= 0:
                    self.log_trade("⚠️ 계산된 주문 수량이 0보다 작거나 같아 주문을 실행하지 않습니다.")
                    return
                
                formatted_amount = self.exchange.format_amount(trade_amount)

                # 3. 실시간 가격 기준으로 TP/SL 재계산
                if settings.USE_BOLLINGER_BANDS_TP:
                    # BB 밴드 값은 지난 캔들 기준이므로 그대로 사용
                    take_profit_price = upper_band if side == 'buy' else lower_band
                else:
                    tp_pct = settings.TARGET_TAKE_PROFIT_PNL / settings.LEVERAGE
                    take_profit_price = live_price * (1 + tp_pct) if side == 'buy' else live_price * (1 - tp_pct)

                sl_pct = settings.TARGET_STOP_LOSS_PNL / settings.LEVERAGE
                stop_loss_price = live_price * (1 - sl_pct) if side == 'buy' else live_price * (1 + sl_pct)
                
                self.log_trade(f"   > 최종 주문 정보 - TP: ${take_profit_price:.2f}, SL: ${stop_loss_price:.2f}")
                
                # 4. 주문 실행
                order = self.exchange.create_market_order_with_tp_sl(
                    side, formatted_amount, take_profit_price, stop_loss_price
                )

                if order:
                    self.log_trade("✅ 주문이 성공적으로 접수되었습니다. 포지션 반영을 위해 5초간 대기합니다.")
                    time.sleep(5)
                else:
                    self.log_trade("🔥 주문 접수가 최종적으로 실패했습니다. 다음 사이클에서 재시도합니다.")

            except Exception as e:
                self.log_trade(f"🔥 주문 실행 중 심각한 오류 발생: {e}")
        else:
            self.log_trade("😴 진입 조건 불충분. 관망합니다.")
