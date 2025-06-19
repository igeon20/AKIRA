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
    <div style={{margin: '30px auto', width: '80%'}}>
      <h2>📊 최근 거래 로그</h2>
      <pre style={{textAlign: 'left', border: '1px solid #ccc', height: '300px', overflowY: 'auto', padding: '20px', background:'#f4f4f4'}}>
        {logs.map((log, index) => (
            <div key={index}>{log}</div>
        ))}
      </pre>
    </div>
  );
}

export default TradeLogs;
