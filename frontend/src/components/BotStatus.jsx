import React from 'react';
import Gear from './Gear';
import '../App.css';

export default function BotStatus({ isRunning, onStart, onStop }) {
  const running = isRunning ? "" : "gear-paused";
  return (
    <div className="bot-status" style={{ margin: 0, marginBottom: 0, flexDirection: 'column', alignItems: 'center', display: 'flex', gap: 10 }}>
      <div style={{
        fontWeight: 800,
        color: isRunning ? "#36c37a" : "#f44",
        fontSize: "1.25em",
        display: "flex",
        alignItems: "center",
        gap: 10,
        marginBottom: 8
      }}>
        {isRunning ? "✅ 봇 작동 중" : "⏸️ 봇 정지"}
        <span className="gear-set">
          <span className={`gear-spin clockwise ${running}`}>
            <Gear size={42} teeth={13}/>
          </span>
          <span className={`gear-spin counter ${running}`} style={{ marginLeft: -12, marginTop: 18 }}>
            <Gear size={28} teeth={9}/>
          </span>
          <span className={`gear-spin clockwise ${running}`} style={{ marginLeft: -10, marginTop: -8 }}>
            <Gear size={32} teeth={11}/>
          </span>
        </span>
      </div>
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 2 }}>
        <button onClick={onStart} style={{ padding: '8px 22px', fontSize: 16, borderRadius: 10, border: 'none', background: '#2d333b', color: '#fff', cursor: 'pointer' }}>
          시작 ▶️
        </button>
        <button onClick={onStop} style={{ padding: '8px 22px', fontSize: 16, borderRadius: 10, border: 'none', background: '#555', color: '#fff', cursor: 'pointer' }}>
          정지 ⏹️
        </button>
      </div>
    </div>
  );
}
