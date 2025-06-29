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
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: 40 }}>
          {/* 봇 상태 및 기어 */}
          <BotStatus isRunning={isRunning} />

          {/* 봇 제어 버튼 */}
          <div style={{ display: 'flex', gap: 16, justifyContent: 'center', marginTop: 24 }}>
            <button onClick={() => setIsRunning(true)} style={{ padding: '10px 24px', fontSize: 18, borderRadius: 10, border: 'none', background: '#2d333b', color: '#fff', cursor: 'pointer' }}>
              Start ▶️
            </button>
            <button onClick={() => setIsRunning(false)} style={{ padding: '10px 24px', fontSize: 18, borderRadius: 10, border: 'none', background: '#555', color: '#fff', cursor: 'pointer' }}>
              Stop ⏹️
            </button>
          </div>
        </div>

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

        <section className="bot-control-section">
          <BotControl />
        </section>

        <section className="logs-section">
          <TradeLogs />
        </section>
      </main>
    </div>
  );
}

export default App;
