import React, { useEffect, useState } from 'react';
import BotControl from './components/BotControl';
import { AdvancedChart } from 'react-tradingview-embed';
import TradeLogs from './components/TradeLogs';
import BalanceStatus from './components/BalanceStatus';
import axios from 'axios';

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
    <div style={{
      minHeight: "100vh",
      background: "#12151b",
      color: "#f7f7f7",
      fontFamily: "Segoe UI, Arial",
      padding: 0,
      margin: 0
    }}>
      <h1 style={{padding:30, margin:0, fontSize:38}}>🚀 Binance Futures Trading Bot 🚀</h1>
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
      {/* Wojak 잔고 */}
      <BalanceStatus initBalance={INIT_BALANCE} balance={balance} />
      {/* 봇 제어 버튼 */}
      <BotControl />
      {/* 거래로그 */}
      <TradeLogs />
    </div>
  );
}
export default App;
