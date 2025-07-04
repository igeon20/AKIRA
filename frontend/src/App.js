// src/App.js
import React, { useState, useEffect, useRef } from "react";
// components 폴더로 경로를 정확히 지정
import BotControl from "./components/BotControl";
import BotStatus from "./components/BotStatus";
import BalanceStatus from "./components/BalanceStatus";
import TradeLogs from "./components/TradeLogs";
import Gear from "./components/Gear";

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
    // 1) 초기 상태
    fetch(`${window.location.protocol}//${HOST}/bot/status`)
      .then((r) => r.json())
      .then((d) => {
        setIsRunning(d.running);
        setMetrics({
          balance: d.balance,
          position: d.position,
          entry_price: d.entry_price,
        });
      });

    // 2) 초기 로그
    fetch(`${window.location.protocol}//${HOST}/bot/logs`)
      .then((r) => r.json())
      .then((d) => setLogs(d.logs));

    // 3) WebSocket 설정
    wsRef.current = new WebSocket(`${PROTO}://${HOST}/ws/logs`);
    wsRef.current.onmessage = (e) => {
      const d = JSON.parse(e.data);
      setLogs((prev) => [...prev, d.log].slice(-100));
      setMetrics({
        balance: d.balance,
        position: d.position,
        entry_price: d.entry_price,
      });
    };
    return () => wsRef.current.close();
  }, []);

  const controlBot = (action) => {
    fetch(`${window.location.protocol}//${HOST}/bot/control`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    }).then(() => setIsRunning(action === "start"));
  };

  return (
    <div className="app-container">
      <h1>Trading Bot Dashboard</h1>

      {/* 기어 애니메이션 + 상태 */}
      <div>
        <Gear spinning={isRunning} />{" "}
        <span style={{ verticalAlign: "middle", fontSize: "1.1em" }}>
          봇 {isRunning ? "운영 중" : "정지 중"}
        </span>
      </div>

      {/* 시작·정지 버튼 */}
      <BotControl
        onStart={() => controlBot("start")}
        onStop={() => controlBot("stop")}
      />

      {/* 봇 상태(잔고·포지션) */}
      <BalanceStatus
        initBalance={INIT_BALANCE}
        balance={metrics.balance}
        position={metrics.position}
        entryPrice={metrics.entry_price}
      />

      {/* 최근 로그 */}
      <section className="log-section">
        <h2>Recent Logs</h2>
        <ul>
          {logs.map((log, idx) => (
            <li key={idx}>{log}</li>
          ))}
        </ul>
      </section>

      {/* 차트 자리 (추후 컴포넌트 삽입) */}
      <section className="chart-section">
        {/* <YourChartComponent /> */}
      </section>
    </div>
  );
}

export default App;
