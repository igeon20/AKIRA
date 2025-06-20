import React from 'react';
import BotControl from './components/BotControl';
import { AdvancedChart } from 'react-tradingview-embed';
import TradeLogs from './components/TradeLogs';

function App() {
  return (
    <div style={{textAlign: 'center'}}>
      <h1>🚀 Binance Futures Trading Bot 🚀</h1>

      {/* 바이낸스 실시간 그래프 */}
      <div style={{width: '80%', height: '420px', margin: '30px auto'}}>
        <AdvancedChart 
          widgetProps={{
            symbol: "BINANCE:BTCUSDT",
            interval: "1",
            timezone: "Asia/Seoul",
            theme: "dark",
            autosize: true
            // width: "100%",
            // height: 420,
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
