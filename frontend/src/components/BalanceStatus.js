import React from "react";

const emotionTable = [
  { threshold: 0.5,   name: "ecstatic", label: "매우 신남" },
  { threshold: 0.2,   name: "happy",    label: "행복" },
  { threshold: 0.05,  name: "manic",    label: "기쁨" },
  { threshold: -0.05, name: "neutral",  label: "그저 그럼" },
  { threshold: -0.2,  name: "sad",      label: "슬픔" },
  { threshold: -0.5,  name: "depressed",label: "매우 실망" },
  { threshold: -999,  name: "miserable",label: "자살 직전" }
];

// 초기 자본 대비 감정 상태 판단
export function getEmotionByBalance(initBalance, balance) {
  const pct = (balance - initBalance) / initBalance;
  for (const e of emotionTable) {
    if (pct >= e.threshold) return e;
  }
  return emotionTable[emotionTable.length - 1];
}

export default function BalanceStatus({ initBalance, balance, position, entryPrice }) {
  const emotion = getEmotionByBalance(initBalance, balance);

  return (
    <div
      style={{
        background: "#181d27",
        borderRadius: "16px",
        padding: "30px 20px",
        margin: "30px auto 10px",
        display: "flex",
        alignItems: "center",
        boxShadow: "0 2px 12px #0006",
        maxWidth: 480,
        flexDirection: "column",
        gap: 12
      }}>
      <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
        <img
          src={`/wojak_emotion/${emotion.name}.png`}
          alt={emotion.label}
          width={90}
          height={90}
          style={{ borderRadius: "12px", border: "2px solid #444" }}
        />
        <div style={{ color: "#f7f7f7", textAlign: "left" }}>
          <div style={{ fontSize: 22, fontWeight: "bold", letterSpacing: 1 }}>
            💵 계좌: {balance.toFixed(2)} USDT
          </div>
          <div style={{ fontSize: 18, opacity: 0.8 }}>
            상태: <span>{emotion.label}</span>
          </div>
        </div>
      </div>
      <div style={{ color: "#f7f7f7", textAlign: "center" }}>
        <div style={{ fontSize: 16 }}>
          포지션: {position === 0 ? '없음' : position === 1 ? '롱' : '숏'}
        </div>
        {entryPrice != null && (
          <div style={{ fontSize: 16 }}>
            진입가: {entryPrice.toFixed(2)}
          </div>
        )}
      </div>
    </div>
  );
}
