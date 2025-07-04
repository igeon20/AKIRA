import React, { useState, useEffect } from 'react';

const BalanceStatus = () => {
  const [balance, setBalance] = useState(0);

  const fetchBalance = async () => {
    try {
      const res = await fetch('/bot/status');
      if (!res.ok) throw new Error('잔고 조회 실패');
      const { balance } = await res.json();
      setBalance(balance);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchBalance();
    const id = setInterval(fetchBalance, 5000);
    return () => clearInterval(id);
  }, []);

  return <div className="balance-status">잔고: {balance.toFixed(2)} USDT</div>;
};

export default BalanceStatus;
