import React, { useState, useEffect } from 'react';
import axios from 'axios';

// ⚠️ 로컬 개발 환경에서 사용하는 API 주소
const API_BASE_URL = process.env.REACT_APP_API_URL;

function BotControl() {
  const [status, setStatus] = useState(false);

  // 상태를 가져오는 함수
  const fetchStatus = () => {
    axios.get(`${API_BASE_URL}/bot/status`)
      .then(res => setStatus(res.data.running))
      .catch(err => {
        console.error("Error fetching bot status:", err);
        setStatus(false);
      });
  };

  useEffect(() => {
    // 페이지 로딩 시 최초 상태 확인
    fetchStatus();

    // 10초마다 상태 갱신
    const interval = setInterval(fetchStatus, 10000);

    return () => clearInterval(interval);
  }, []);

  // 봇 시작 함수
  const startBot = () => {
    axios.post(`${API_BASE_URL}/bot/start`)
      .then(() => {
        console.log("Bot started successfully");
        fetchStatus(); // 상태 즉시 업데이트
      })
      .catch((err) => {
        console.error("Error starting bot:", err);
        fetchStatus();
      });
  };

  // 봇 정지 함수
  const stopBot = () => {
    axios.post(`${API_BASE_URL}/bot/stop`)
      .then(() => {
        console.log("Bot stopped successfully");
        fetchStatus();
      })
      .catch((err) => {
        console.error("Error stopping bot:", err);
        fetchStatus();
      });
  };

  return (
    <div style={{textAlign: 'center', padding: '20px'}}>
      <h2>봇 상태:</h2>
      <h1>{status ? "✅ Bot Running" : "❌ Bot Stopped" }</h1>

      <button 
        onClick={startBot} 
        style={{marginRight: '10px', padding: '10px 20px', fontSize: '16px'}}>
        Start ▶️
      </button>

      <button 
        onClick={stopBot} 
        style={{padding: '10px 20px', fontSize: '16px'}}>
        Stop ⏹️
      </button>
    </div>
  );
}

export default BotControl;
