import React, { useState, useEffect, useCallback } from 'react';

const TradeLogs = () => {
  const [logs, setLogs] = useState([]);

  const fetchLogs = useCallback(async () => {
    try {
      const res = await fetch('/bot/logs');
      if (!res.ok) throw new Error('로그 조회 실패');
      const { logs } = await res.json();
      setLogs(logs);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    fetchLogs();
    const id = setInterval(fetchLogs, 2000);
    return () => clearInterval(id);
  }, [fetchLogs]);

  return (
    <div className="trade-logs">
      <h3>거래 로그</h3>
      <ul>
        {logs.map((log, i) => (
          <li key={i}>{log}</li>
        ))}
      </ul>
    </div>
  );
};

export default TradeLogs;
