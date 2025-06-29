import React from 'react';
import Gear from './Gear';
import './BotStatus.css'; // 이 파일이 없어도 App.css에 다 넣었으니 import만 있으면 됨

export default function BotStatus({ isRunning }) {
  // 애니메이션 클래스 조합
  const running = isRunning ? "" : "gear-paused";
  return (
    <div className="bot-status">
      <span style={{ fontWeight: 700, fontSize: "1.3em" }}>
        봇 상태:
      </span>
      <span style={{
        fontWeight: 800,
        color: isRunning ? "#36c37a" : "#f44",
        marginLeft: 10,
        fontSize: "1.15em",
        display: "flex",
        alignItems: "center",
        gap: 8
      }}>
        {isRunning ? "✅ Bot Running" : "⏸️ Bot Stopped"}
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
      </span>
    </div>
  );
}
