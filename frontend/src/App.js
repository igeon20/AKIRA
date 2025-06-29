import React, { useState } from 'react';
import BotStatus from './components/BotStatus';
import { AdvancedChart } from 'react-tradingview-embed';
import TradeLogs from './components/TradeLogs';
import BalanceStatus from './components/BalanceStatus';
import BotControl from './components/BotControl';
import './App.css';

const INIT_BALANCE = 50.0;

function App() {
  const [balance, setBalance] = useState(INIT_BALANCE);
  const [isRunning, setIsRunning] = useState(true);

  return (
    <div className="app-root">
      <header>
        <h1 style={{
          textAlign: 'center',
          padding: 30,
          margin: 0,
          fontSize: 38,
          color: '#ececec'
        }}>
          🚀 EVEELEN TRADE BOT 🚀
        </h1>
      </header>
      <main style={{ padding: '0 20px' }}>
        <section className="chart-section">
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
        </section>

        <section className="balance-section">
          <BalanceStatus initBalance={INIT_BALANCE} balance={balance} />
        </section>

        {/* 이 위치에만 봇 상태(기어, 버튼, 텍스트) */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: 32, marginTop: 10 }}>
          <BotStatus isRunning={isRunning} setIsRunning={setIsRunning} />
        </div>

        <section className="logs-section">
          <TradeLogs />
        </section>
      </main>
    </div>
  );
}

export default App;
