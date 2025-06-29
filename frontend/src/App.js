// App.js
import React, { useEffect, useState } from 'react';
import BotControl from './components/BotControl';
import { AdvancedChart } from 'react-tradingview-embed';
import TradeLogs from './components/TradeLogs';
import BalanceStatus from './components/BalanceStatus';
import axios from 'axios';
import './App.css';  // 다크모드 전역 스타일 (꼭 import!)

// BotStatus 컴포넌트 정의
function BotStatus({ isRunning }) {
  return (
    <div className="bot-status" style={{ display: 'flex', alignItems: 'center', gap: 12, color: '#ccc', fontWeight: 600, fontSize: 18, fontFamily: 'Segoe UI, Tahoma, Geneva, Verdana, sans-serif', marginBottom: 20 }}>
      <span className="status-text" style={{ userSelect: 'none' }}>
        {isRunning ? 'Bot Running' : 'Bot Stopped'}
      </span>
      <div className={`gears ${isRunning ? 'running' : 'stopped'}`}>
        <div className="gear gear1"></div>
        <div className="gear gear2"></div>
        <div className="gear gear3"></div>
      </div>
    </div>
  );
}

const API_BASE_URL = process.env.REACT_APP_API_URL;
const INIT_BALANCE = 50.0;

function App() {
  const [balance, setBalance] = useState(INIT_BALANCE);
  const [botRunning, setBotRunning] = useState(true); // 봇 실행 상태 초기값 true

  useEffect(() => {
    const fetchBalanceAndStatus = () => {
      axios.get(`${API_BASE_URL}/bot/status`)
        .then(res => {
          setBalance(res.data.balance);
          // 만약 API에서 isRunning 정보 받는다면 아래 주석 해제
          // setBotRunning(res.data.isRunning);
        })
        .catch(() => {
          setBotRunning(false); // API 실패 시 봇 정지 상태로 처리
        });
    };
    fetchBalanceAndStatus();
    const interval = setInterval(fetchBalanceAndStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="app-root">
      <header>
        <h1
          style={{
            textAlign: "center",
            padding: 30,
            margin: 0,
            fontSize: 38,
            color: '#ececec'
          }}
        >
          🚀 EVEELEN TRADE BOT 🚀
        </h1>
      </header>
      <main style={{ padding: '0 20px' }}>
        {/* Bot Running 상태 및 기어 애니메이션 */}
        <BotStatus isRunning={botRunning} />

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
