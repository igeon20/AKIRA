import React from 'react';

export default function Gear({ size = 60, teeth = 12, color = "#aaa", innerColor = "#888", holeColor = "#666", style }) {
  const center = 50;
  const innerR = 36;
  const toothLength = 12;
  const toothWidth = 6;
  const angleStep = 360 / teeth;

  return (
    <svg width={size} height={size} viewBox="0 0 100 100" style={style}>
      {/* 몸통 */}
      <circle cx={center} cy={center} r={innerR} fill={color} stroke={innerColor} strokeWidth="3" />
      {/* 톱니 */}
      {Array.from({ length: teeth }).map((_, i) => {
        const angle = angleStep * i - angleStep / 2;
        return (
          <rect
            key={i}
            x={center - toothWidth / 2}
            y={center - innerR - toothLength}
            width={toothWidth}
            height={toothLength}
            rx={toothWidth / 2.5}
            fill={innerColor}
            stroke={holeColor}
            strokeWidth="1"
            transform={`rotate(${angle} ${center} ${center})`}
          />
        );
      })}
      {/* 가운데 구멍 */}
      <circle cx={center} cy={center} r={13} fill={holeColor} stroke={innerColor} strokeWidth="2"/>
      <circle cx={center} cy={center} r={6} fill="#222" />
    </svg>
  );
}
