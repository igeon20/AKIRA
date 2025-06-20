from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

# ✅ UptimeRobot을 위한 루트 엔드포인트 (HEAD 지원 포함)
@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
def read_root(request: Request):
    if request.method == "HEAD":
        return JSONResponse(content=None, status_code=200)  # ✅ 여기 수정됨
    return {"message": "Binance Trading Bot API"}

# ✅ /ping 엔드포인트 추가 (선택적으로 모니터링 용도로 사용 가능)
@app.api_route("/ping", methods=["GET", "HEAD"])
def ping(request: Request):
        if request.method == "HEAD":
        return Response(status_code=204)
    return {"status": "ok"}

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
        "leverage": bot.leverage                # 레버리지
    }

@app.get("/bot/logs")
def get_logs():
    return {"logs": bot.trade_logs}

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000)
