from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from threading import Thread
from bot import BinanceBot
import joblib
import json
import pandas as pd
import os

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://akiraa.netlify.app",
        "https://eveleen.netlify.app",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bot = BinanceBot()

# 모델 로드
AI_MODEL_PATH = os.path.join("ai_model", "ai_model.pkl")
FEATURE_CONFIG_PATH = os.path.join("ai_model", "feature_config.json")
DATA_PATH = os.path.join("data", "minute_ohlcv.csv")
if os.path.exists(AI_MODEL_PATH) and os.path.exists(FEATURE_CONFIG_PATH):
    AI_MODEL = joblib.load(AI_MODEL_PATH)
    with open(FEATURE_CONFIG_PATH) as f:
        FEATURE_COLS = json.load(f)
else:
    AI_MODEL = None
    FEATURE_COLS = []

@app.api_route("/", methods=["GET","HEAD"], include_in_schema=False)
def read_root(req: Request):
    if req.method == 'HEAD': return JSONResponse(content=None, status_code=200)
    return {"message":"API"}

@app.get("/ping")
def ping(): return {"status":"ok"}

@app.post("/bot/start")
def start():
    if not bot.running:
        Thread(target=bot.start_bot).start()
        return {"message":"🚀 봇 시작됨"}
    return {"message":"⚠️ 봇 이미 실행중"}

@app.post("/bot/stop")
def stop():
    if bot.running:
        bot.stop()
        return {"message":"🛑 봇 정지됨"}
    return {"message":"⚠️ 봇 이미 정지됨"}

@app.get("/bot/status")
def bot_status():
    return {
        "running": bot.running,
        "balance": bot.balance,
        "position": bot.position,
        "entry_price": bot.entry_price,
        "leverage": getattr(bot, 'leverage', None)
    }

@app.get("/bot/logs")
def get_logs():
    return {"logs": bot.trade_logs}

@app.get("/bot/ai_signal")
def ai_signal():
    if AI_MODEL is None or not FEATURE_COLS:
        return {"signal": 0, "error": "AI 모델 미적용"}
    try:
        df = pd.read_csv(DATA_PATH)
        df.columns = [c.strip().lower() for c in df.columns]
        last_row = df.iloc[[-1]][FEATURE_COLS].reset_index(drop=True)
        pred = int(AI_MODEL.predict(last_row)[0])
        return {"signal": pred}
    except Exception as e:
        return {"signal": 0, "error": str(e)}
