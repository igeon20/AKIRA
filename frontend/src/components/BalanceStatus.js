// frontend/src/components/BalanceStatus.js
import React from "react";

const emotionTable = [
  { threshold: 0.5,   name: "ecstatic", label: "ECSTATIC" },
  { threshold: 0.2,   name: "happy",    label: "HAPPY" },
  { threshold: 0.05,  name: "manic",    label: "MANIC" },
  { threshold: -0.05, name: "neutral",  label: "NEUTRAL" },
  { threshold: -0.2,  name: "sad",      label: "SAD" },
  { threshold: -0.5,  name: "depressed",label: "DEPRESSED" },
  { threshold: -999,  name: "miserable",label: "MISERABLE" }
];

export function getEmotionByBalance(initBalance, balance) {
  const pct = (balance - initBalance) / initBalance;
  for (const e of emotionTable) {
    if (pct >= e.threshold) return e;
  }
  return emotionTable[emotionTable.length - 1];
}

export default function BalanceStatus({ initBalance, balance }) {
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
        maxWidth: 480
      }}>
      <img
        src={`/wojak_emotion/${emotion.name}.png`}
        alt={emotion.label}
        width={90}
        height={90}
        style={{ borderRadius: "12px", marginRight: 28, border: "2px solid #444" }}
      />
      <div style={{ color: "#f7f7f7", textAlign: "left" }}>
        <div style={{ fontSize: 22, fontWeight: "bold", letterSpacing: 1 }}>
          💵 Balance : {balance.toFixed(2)} USDT
        </div>
        <div style={{ fontSize: 18, opacity: 0.8 }}>
          상태: <span>{emotion.label}</span>
        </div>
      </div>
    </div>
  );
}
