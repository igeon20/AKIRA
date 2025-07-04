import React, { useState, useEffect, useRef } from "react";

// 반드시 components 폴더 아래에서 불러옵니다
import BotControl    from "./components/BotControl";
import BotStatus     from "./components/BotStatus";
import BalanceStatus from "./components/BalanceStatus";
import TradeLogs     from "./components/TradeLogs";
import Gear          from "./components/Gear";

import "./App.css";

const INIT_BALANCE = parseFloat(process.env.REACT_APP_INIT_BALANCE) || 50;
const HOST = process.env.REACT_APP_API_HOST || window.location.host;
const PROTO = window.location.protocol === "https:" ? "wss" : "ws";

function App() {
  const [logs, setLogs] = useState([]);
  const [metrics, setMetrics] = useState({
    balance: INIT_BALANCE,
    position: 0,
    entry_price: null,
  });
  const [isRunning, setIsRunning] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    // 초기 상태 & 로그 로드
    fetch(`${window.location.protocol}//${HOST}/bot/status`)
      .then(res => res.json())
      .then(d => {
        setIsRunning(d.running);
        setMetrics({
          balance: d.balance,
          position: d.position,
          entry_price: d.entry_price,
        });
      })
      .catch(console.error);

    fetch(`${window.location.protocol}//${HOST}/bot/logs`)
      .then(res => res.json())
      .then(d => setLogs(d.logs))
      .catch(console.error);

    // WebSocket 연결 (새 로그 수신)
    wsRef.current = new WebSocket(`${PROTO}://${HOST}/ws/logs`);
    wsRef.current.onmessage = e => {
      const d = JSON.parse(e.data);
      setLogs(prev => [...prev, d.log].slice(-100));
      setMetrics({
        balance: d.balance,
        position: d.position,
        entry_price: d.entry_price,
      });
    };
    wsRef.current.onerror = console.error;
    return () => wsRef.current.close();
  }, []);

  const controlBot = action => {
    fetch(`${window.location.protocol}//${HOST}/bot/control`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    })
      .then(res => {
        if (!res.ok) throw new Error("control failed");
        setIsRunning(action === "start");
      })
      .catch(console.error);
  };

  return (
    <div className="app-container">
      <h1>Trading Bot Dashboard</h1>

      <div>
        <Gear spinning={isRunning} />{" "}
        <span style={{ verticalAlign: "middle", fontSize: "1.1em" }}>
          봇 {isRunning ? "운영 중" : "정지 중"}
        </span>
      </div>

      <BotControl
        onStart={() => controlBot("start")}
        onStop={() => controlBot("stop")}
      />

      <BalanceStatus
        initBalance={INIT_BALANCE}
        balance={metrics.balance}
        position={metrics.position}
        entryPrice={metrics.entry_price}
      />

      <TradeLogs logs={logs} />

      <section className="chart-section">
        {/* 차트 컴포넌트 추가 예정 */}
      </section>
    </div>
  );
}

export default App;
