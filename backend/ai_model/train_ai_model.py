import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib
import json

# 1. CSV 불러오기
csv_path = "../data/minute_ohlcv.csv"
print(f"Loading data from {csv_path} ...")
df = pd.read_csv(csv_path)

# 2. 컬럼명을 소문자로 자동 통일!
df.columns = [c.strip().lower() for c in df.columns]
print("컬럼명:", list(df.columns))

# 3. 사용할 feature 정의 (소문자!)
feature_cols = ["open", "high", "low", "close", "volume"]

# 4. feature 누락 자동 검사
for col in feature_cols:
    if col not in df.columns:
        raise Exception(f"데이터에 feature 컬럼 '{col}' 없음! 컬럼명: {list(df.columns)}")

# 5. label 생성(예: close가 10분 뒤 +0.2% 이상이면 1, -0.2% 이하면 -1, 아니면 0)
future = df['close'].shift(-10)
pct = (future - df['close']) / df['close']
df['label'] = 0
df.loc[pct > 0.002, 'label'] = 1
df.loc[pct < -0.002, 'label'] = -1

df = df.dropna(subset=feature_cols + ['label'])
print("전체 샘플 수:", len(df))

# 6. 데이터 일부만 사용 (예: 최신 8만개)
if len(df) > 80000:
    df = df.tail(80000)
    print("최신 8만개로 제한:", len(df))

X = df[feature_cols]
y = df['label']
print("학습 시작 (행:", X.shape[0], ", 피처:", X.shape[1], ") ...")

# 7. 트리 수 줄이고 병렬처리로 속도 최적화
model = RandomForestClassifier(n_estimators=40, random_state=42, n_jobs=-1)
model.fit(X, y)
print("학습 완료!")

# 8. 모델 저장
joblib.dump(model, "ai_model.pkl")
with open("feature_config.json", "w") as f:
    json.dump(feature_cols, f)
print("모델 저장 완료 (ai_model.pkl, feature_config.json)")
