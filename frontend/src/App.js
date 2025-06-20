import React from 'react';
import BotControl from './components/BotControl';
import { AdvancedChart } from 'react-tradingview-embed';
import TradeLogs from './components/TradeLogs';

function App() {
  return (
    <div style={{ textAlign: 'center' }}>
      <h1>🚀 Binance Futures Trading Bot 🚀</h1>

      {/* 바이낸스 실시간 그래프 */}
      <div style={{ width: '100%', maxWidth: '1000px', height: '480px', margin: '30px auto' }}>
        <AdvancedChart
          widgetProps={{
            symbol: "BINANCE:BTCUSDT",
            interval: "1",
            timezone: "Asia/Seoul",
            theme: "dark",
            width: "1000",
            height: "480"
          }}
        />
      </div>

      {/* 봇 제어 버튼 */}
      <BotControl />

      {/* 거래로그 */}
      <TradeLogs/>
    </div>
  );
}

export default App;
