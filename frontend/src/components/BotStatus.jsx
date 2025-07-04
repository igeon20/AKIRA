import React, { useState, useEffect } from 'react';

const BotStatus = () => {
  const [status, setStatus] = useState({ running: false, position: 0, entry_price: null, balance: 0 });

  const fetchStatus = async () => {
    try {
      const res = await fetch('/bot/status');
      if (!res.ok) throw new Error('상태 조회 실패');
      const data = await res.json();
      setStatus(data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="bot-status">
      <p>봇 상태: {status.running ? '운영 중' : '정지 중'}</p>
      <p>포지션: {status.position}</p>
      <p>진입가: {status.entry_price ?? '-'} </p>
      <p>잔고(USDT): {status.balance.toFixed(2)}</p>
    </div>
  );
};

export default BotStatus;

