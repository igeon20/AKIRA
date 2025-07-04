import React from 'react';

const BotControl = ({ onStart, onStop }) => {
  // 봇 시작
  const startBot = async () => {
    try {
      const res = await fetch('/bot/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'start' }),
      });
      if (!res.ok) throw new Error('봇 시작 실패');
      onStart();
    } catch (e) {
      console.error(e);
      alert('봇 시작 중 오류 발생');
    }
  };

  // 봇 정지
  const stopBot = async () => {
    try {
      const res = await fetch('/bot/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'stop' }),
      });
      if (!res.ok) throw new Error('봇 정지 실패');
      onStop();
    } catch (e) {
      console.error(e);
      alert('봇 정지 중 오류 발생');
    }
  };

  return (
    <div className="bot-control">
      <button onClick={startBot}>봇 시작 ▶️</button>
      <button onClick={stopBot}>봇 정지 ⏹️</button>
    </div>
  );
};

export default BotControl;
