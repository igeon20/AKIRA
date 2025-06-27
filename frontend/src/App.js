import React, { useEffect, useState } from 'react';
import BotControl from './components/BotControl';
import { AdvancedChart } from 'react-tradingview-embed';
import TradeLogs from './components/TradeLogs';
import BalanceStatus from './components/BalanceStatus';
import axios from 'axios';
import './App.css';  // 다크모드 전역 스타일 (꼭 import!)

const API_BASE_URL = process.env.REACT_APP_API_URL;
const INIT_BALANCE = 50.0;

function App() {
  const [balance, setBalance] = useState(INIT_BALANCE);

  useEffect(() => {
    const fetchBalance = () => {
      axios.get(`${API_BASE_URL}/bot/status`).then(res => setBalance(res.data.balance));
    };
    fetchBalance();
    const interval = setInterval(fetchBalance, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="app-root">
      <header>
        <h1>🚀 EVEELEN TRADE BOT 🚀</h1>
      </header>
      <main>
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
        {/* 워작의 현재 잔고 */}
        <section className="balance-section">
          <BalanceStatus initBalance={INIT_BALANCE} balance={balance} />
        </section>
        {/* 봇 제어 버튼 */}
        <section className="bot-control-section">
          <BotControl />
        </section>
        {/* 거래로그 */}
        <section className="logs-section">
          <TradeLogs />
        </section>
      </main>
    </div>
  );
}

export default App;
