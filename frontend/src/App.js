// src/App.js
import React, { useState, useEffect, useRef } from "react";
import BalanceStatus from "./components/BalanceStatus";
import BotStatus from "./components/BotStatus";
import "./App.css";

const INIT_BALANCE = parseFloat(process.env.REACT_APP_INIT_BALANCE) || 50;

function App() {
  const [logs, setLogs] = useState([]);
  const [metrics, setMetrics] = useState({
    balance: INIT_BALANCE,
    position: 0,
    entry_price: null,
  });
  const [isRunning, setIsRunning] = useState(false);
  const wsRef = useRef(null);
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const host = process.env.REACT_APP_API_HOST || window.location.host;

  useEffect(() => {
    // 초기 상태 조회
    fetch(`${window.location.protocol}//${host}/bot/status`)
      .then((res) => res.json())
      .then((data) => {
        setIsRunning(data.running);
        setMetrics({
          balance: data.balance,
          position: data.position,
          entry_price: data.entry_price,
        });
      });

    // WebSocket 연결 (로그 & 지표 자동 업데이트)
    wsRef.current = new WebSocket(`${protocol}://${host}/ws/logs`);
    wsRef.current.onmessage = (event) => {
      try {
        const d = JSON.parse(event.data);
        setLogs((prev) => [d.log, ...prev].slice(0, 100));
        setMetrics({
          balance: d.balance,
          position: d.position,
          entry_price: d.entry_price,
        });
      } catch (e) {
        console.error("Invalid WS message", e);
      }
    };
    wsRef.current.onclose = () => console.warn("WS closed");
    wsRef.current.onerror = (e) => console.error("WS error", e);

    return () => wsRef.current && wsRef.current.close();
  }, [host, protocol]);

  const handleStart = () => {
    fetch(`${window.location.protocol}//${host}/bot/control`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "start" }),
    }).then(() => setIsRunning(true));
  };
  const handleStop = () => {
    fetch(`${window.location.protocol}//${host}/bot/control`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "stop" }),
    }).then(() => setIsRunning(false));
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Trading Bot Dashboard</h1>
      </header>
      <main>
        <BotStatus
          isRunning={isRunning}
          onStart={handleStart}
          onStop={handleStop}
        />
        <BalanceStatus
          initBalance={INIT_BALANCE}
          balance={metrics.balance}
          position={metrics.position}
          entryPrice={metrics.entry_price}
        />
        <section className="log-section">
          <h2>Recent Logs</h2>
          <ul className="log-list">
            {logs.map((log, idx) => (
              <li key={idx}>{log}</li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  );
}

export default App;
