import React from 'react';

const BotControl = ({ onStatusChange }) => {
  // 봇 시작
  const startBot = async () => {
    try {
      const res = await fetch('/bot/start', { method: 'POST' });
      if (!res.ok) throw new Error('시작 요청 실패');
      onStatusChange();
    } catch (e) {
      console.error(e);
      alert('봇 시작 중 오류 발생');
    }
  };

  // 봇 정지
  const stopBot = async () => {
    try {
      const res = await fetch('/bot/stop', { method: 'POST' });
      if (!res.ok) throw new Error('정지 요청 실패');
      onStatusChange();
    } catch (e) {
      console.error(e);
      alert('봇 정지 중 오류 발생');
    }
  };

  return (
    <div className="bot-control">
      <button onClick={startBot}>봇 시작</button>
      <button onClick={stopBot}>봇 정지</button>
    </div>
  );
};

export default BotControl;
