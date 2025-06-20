from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # <--- 이 부분 추가✨
from bot import BinanceBot
import uvicorn

app = FastAPI()

# ⭐️ CORS 설정 (필수 추가✨)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://akiraa.netlify.app/",  # 예비용
        "eveleen.netlify.app", # 실제 프론트 주소로 변경!
        "http://localhost:3000"  # 개발용도 남겨두기 (선택)
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
        from threading import Thread
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
    return {"running": bot.running, "balance": bot.balance}

@app.get("/bot/logs")
def get_logs():
    return {"logs": bot.trade_logs}

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000)
