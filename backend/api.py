from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from bot import BinanceBot
from threading import Thread
import uvicorn

app = FastAPI()

# ⭐️ CORS 설정 (서버-프론트 주소에 맞게 수정)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://akiraa.netlify.app",      # 예비: 이전 프론트
        "https://eveleen.netlify.app",     # 실제 프론트
        "http://localhost:3000",           # 로컬 개발용
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bot = BinanceBot()

@app.get("/")
def read_root():
    return {"message": "Binance Trading Bot API"}

@app.post("/bot/start")
def start_bot():
    if not bot.running:
        Thread(target=bot.start).start()
        return {"message": "🚀 봇 시작됨"}
    return {"message": "⚠️ 봇 이미 실행중"}

@app.post("/bot/stop")
def stop_bot():
    if bot.running:
        bot.stop()
        return {"message": "🛑 봇 정지됨"}
    return {"message": "⚠️ 봇 이미 정지됨"}

@app.get("/bot/status")
def bot_status():
    return {
        "running": bot.running,
        "balance": bot.balance,
        "position": bot.position,               # 현재 포지션 (1:롱, -1:숏, 0:없음)
        "entry_price": bot.entry_price,         # 진입가격
        "leverage": bot.leverage               # 레버리지
    }

@app.get("/bot/logs")
def get_logs():
    return {"logs": bot.trade_logs}

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000)
