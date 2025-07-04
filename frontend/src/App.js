// src/App.js
import React, { useState, useEffect, useRef } from "react";
import BalanceStatus from "./BalanceStatus";
import "./App.css";

// 초기 자본을 .env 파일에서 받거나 기본값 50 설정
const INIT_BALANCE = parseFloat(process.env.REACT_APP_INIT_BALANCE) || 50;

function App() {
  const [logs, setLogs] = useState([]);
  const [metrics, setMetrics] = useState({
    balance: INIT_BALANCE,
    position: 0,
    entry_price: null,
  });
  const wsRef = useRef(null);

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const host = process.env.REACT_APP_API_HOST || window.location.host;
    wsRef.current = new WebSocket(`${protocol}://${host}/ws/logs`);

    wsRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // 최근 100개 로그만 보관
        setLogs((prev) => [data.log, ...prev].slice(0, 100));
        // balance, position, entry_price 업데이트
        setMetrics({
          balance: data.balance,
          position: data.position,
          entry_price: data.entry_price,
        });
      } catch (e) {
        console.error("Invalid message format", e);
      }
    };

    wsRef.current.onclose = () => console.warn("WebSocket connection closed");
    wsRef.current.onerror = (err) => console.error("WebSocket error", err);

    return () => {
      wsRef.current.close();
    };
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <h1>Trading Bot Dashboard</h1>
      </header>
      <main>
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
