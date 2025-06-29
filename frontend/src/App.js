import React, { useState, useEffect } from 'react';
import axios from 'axios';
import BotStatus from './components/BotStatus';
import { AdvancedChart } from 'react-tradingview-embed';
import TradeLogs from './components/TradeLogs';
import BalanceStatus from './components/BalanceStatus';
import BotControl from './components/BotControl';
import './App.css';

const INIT_BALANCE = 50.0;
const API_BASE_URL = process.env.REACT_APP_API_URL || ''; // 환경변수로 API 주소 지정

function App() {
  const [balance, setBalance] = useState(INIT_BALANCE);
  const [isRunning, setIsRunning] = useState(true);

  // 주기적으로 백엔드에서 상태를 가져옴 (5초마다)
  useEffect(() => {
    const fetchStatus = () => {
      axios.get(`${API_BASE_URL}/bot/status`)
        .then(res => {
          setIsRunning(res.data.running);
          setBalance(res.data.balance);
        })
        .catch(() => {
          // 에러 시, 동작안함
        });
    };
    fetchStatus();
    const timer = setInterval(fetchStatus, 5000);
    return () => clearInterval(timer);
  }, []);

  // Start/Stop 시 실제 API로 명령 보내기
  const handleStart = async () => {
    try {
      await axios.post(`${API_BASE_URL}/bot/start`);
      // 바로 status 갱신
      const res = await axios.get(`${API_BASE_URL}/bot/status`);
      setIsRunning(res.data.running);
      setBalance(res.data.balance);
    } catch (e) {}
  };

  const handleStop = async () => {
    try {
      await axios.post(`${API_BASE_URL}/bot/stop`);
      const res = await axios.get(`${API_BASE_URL}/bot/status`);
      setIsRunning(res.data.running);
      setBalance(res.data.balance);
    } catch (e) {}
  };

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

        {/* 거래 로그 위, 월렛 아래에만 상태+버튼 표시 */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: 32, marginTop: 10 }}>
          <BotStatus
            isRunning={isRunning}
            onStart={handleStart}
            onStop={handleStop}
          />
        </div>

        <section className="logs-section">
          <TradeLogs />
        </section>
      </main>
    </div>
  );
}

export default App;
