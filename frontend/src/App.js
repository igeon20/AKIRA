// src/App.js
import React, { useState, useEffect, useRef } from "react";

// components 폴더 내부 파일을 정확히 가리키도록 확장자까지 명시
import BotControl    from "./components/BotControl.js";
import BotStatus     from "./components/BotStatus.jsx";
import BalanceStatus from "./components/BalanceStatus.js";
import TradeLogs     from "./components/TradeLogs.js";
import Gear          from "./components/Gear.jsx";

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
    // 1) 봇 상태 초기 로드
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

    // 2) 초기 로그 로드
    fetch(`${window.location.protocol}//${HOST}/bot/logs`)
      .then((r) => r.json())
      .then((d) => setLogs(d.logs))
      .catch(console.error);

    // 3) WebSocket 연결
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

      {/* 기어 + 상태 */}
      <div>
        <Gear spinning={isRunning} />{" "}
        <span style={{ verticalAlign: "middle", fontSize: "1.1em" }}>
          봇 {isRunning ? "운영 중" : "정지 중"}
        </span>
      </div>

      {/* 시작/정지 컨트롤 */}
      <BotControl
        onStart={() => controlBot("start")}
        onStop={() => controlBot("stop")}
      />

      {/* 잔고·포지션 상태 */}
      <BalanceStatus
        initBalance={INIT_BALANCE}
        balance={metrics.balance}
        position={metrics.position}
        entryPrice={metrics.entry_price}
      />

      {/* 최근 로그 */}
      <TradeLogs logs={logs} />

      {/* (추후) 차트 삽입 공간 */}
      <section className="chart-section">
        {/* <YourChartComponent /> */}
      </section>
    </div>
  );
}

export default App;
