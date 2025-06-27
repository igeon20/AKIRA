import React, { useEffect, useState } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL;

function TradeLogs() {
  const [logs, setLogs] = useState([]);

  const fetchLogs = () => {
    axios.get(`${API_URL}/bot/logs`).then(res => setLogs(res.data.logs));
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{
      margin: '30px auto',
      width: '90%',
      background: '#181d27',
      borderRadius: '12px 12px 0 0',
      boxShadow: '0 2px 8px #0006',
      overflow: 'hidden'
    }}>
      <div style={{
        fontWeight: 'bold',
        fontSize: 24,
        padding: '12px 24px',
        background: '#181d27',
        color: '#f7f7f7',
        display: 'flex',
        alignItems: 'center',
        borderBottom: '1px solid #23272f'
      }}>
        <span role="img" aria-label="log" style={{marginRight:10}}>📊</span>
        최근 거래 로그
      </div>
      <pre style={{
        textAlign: 'left',
        background: '#222631',
        color: '#f7f7f7',
        height: '300px',
        overflowY: 'auto',
        margin: 0,
        padding: '20px',
        fontSize: 16,
        borderRadius: '0 0 12px 12px'
      }}>
        {logs && logs.length > 0
          ? logs.map((log, i) => <div key={i}>{log}</div>)
          : <span style={{opacity:0.7}}>로그 기록이 없습니다.</span>}
      </pre>
    </div>
  );
}

export default TradeLogs;
