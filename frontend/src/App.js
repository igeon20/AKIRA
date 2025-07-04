import React, { useState, useEffect, useRef } from "react";
import BalanceStatus from "./components/BalanceStatus";
import BotStatus from "./components/BotStatus";
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
    // 1) 초기 상태 + 초기 로그 로드
    fetch(`${window.location.protocol}//${HOST}/bot/status`)
      .then((r) => r.json())
      .then((d) => {
        setIsRunning(d.running);
        setMetrics({ balance: d.balance, position: d.position, entry_price: d.entry_price });
      });

    fetch(`${window.location.protocol}//${HOST}/bot/logs`)
      .then((r) => r.json())
      .then((d) => {
        // 오래된 순서 그대로 보여줌
        setLogs(d.logs);
      });

    // 2) WebSocket 연결 — 새 로그만 추가
    wsRef.current = new WebSocket(`${PROTO}://${HOST}/ws/logs`);
    wsRef.current.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data);
        // 가장 뒤(최신)에 붙이기
        setLogs((prev) => [...prev, d.log].slice(-100));
        setMetrics({ balance: d.balance, position: d.position, entry_price: d.entry_price });
      } catch (err) {
        console.error("WS message parse error", err);
      }
    };
    wsRef.current.onclose = () => console.warn("WS closed");
    wsRef.current.onerror = (err) => console.error("WS error", err);

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
    <div className="App">
      <header className="App-header">
        <h1>Trading Bot Dashboard</h1>
      </header>
      <main>
        <BotStatus
          isRunning={isRunning}
          onStart={() => controlBot("start")}
          onStop={() => controlBot("stop")}
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
