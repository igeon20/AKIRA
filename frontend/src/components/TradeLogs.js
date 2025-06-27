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
      maxWidth: '1200px',
      background: '#1c1e23',
      borderRadius: '20px',
      padding: '32px 0 32px 0',
      boxShadow: '0 8px 24px #00000044'
    }}>
      <h2 style={{color: '#ececec', paddingLeft: '24px', marginBottom: '8px'}}>
        <span role="img" aria-label="log">📊</span> 최근 거래 로그
      </h2>
      <pre style={{
        textAlign: 'left',
        border: '1px solid #23242a',
        height: '300px',
        overflowY: 'auto',
        padding: '20px',
        background: '#23242a',
        color: '#ececec',
        borderRadius: '16px',
        margin: '0 24px'
      }}>
        {logs.length === 0
          ? <span style={{color: "#aaa"}}>로그 없음</span>
          : logs.map((log, index) => (
              <div key={index}>{log}</div>
            ))
        }
      </pre>
    </div>
  );
}

export default TradeLogs;
