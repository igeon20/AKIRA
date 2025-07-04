// src/App.js
import React, { useState, useEffect, useRef } from "react";

// ← 꼭 "./components/…" 경로로 수정하세요
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
    // 봇 상태 가져오기
    fetch(`${window.location.protocol}//${HOST}/bot/status`)
      .then((r) => r.json())
      .then((d) => {
        setIsRunning(d.running);
        setMetrics({
          balance: d.balance,
          position: d.position,
          entry_price: d.entry_price,
        });
      })
      .catch(console.error);

    // 초기 로그 불러오기
    fetch(`${window.location.protocol}//${HOST}/bot/logs`)
      .then((r) => r.json())
      .then((d) => setLogs(d.logs))
      .catch(console.error);

    // WebSocket 연결
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
    wsRef.current.onerror = console.error;
    return () => wsRef.current.close();
  }, []);

  const controlBot = (action) => {
    fetch(`${window.location.protocol}//${HOST}/bot/control`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    })
      .then(() => setIsRunning(action === "start"))
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

      <BotControl onStart={() => controlBot("start")} onStop={() => controlBot("stop")} />

      <BalanceStatus
        initBalance={INIT_BALANCE}
        balance={metrics.balance}
        position={metrics.position}
        entryPrice={metrics.entry_price}
      />

      <TradeLogs logs={logs} />

      <section className="chart-section">
        {/* 차트 컴포넌트 삽입 예정 구역 */}
      </section>
    </div>
  );
}

export default App;
