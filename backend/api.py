import os
import asyncio
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from bot import BinanceBot

# ─── 로깅 설정 ───────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ─── CORS 설정 ───────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGINS", "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 봇 인스턴스 생성 ───────────────────────────────────
class BotControl(BaseModel):
    action: str  # 'start' 또는 'stop'

bot = BinanceBot()

@app.on_event("startup")
async def startup_event():
    # 봇 모니터링 태스크만 실행 (REST 폴링)
    asyncio.create_task(bot.run())

# ─── 봇 제어 엔드포인트 ─────────────────────────────────
@app.post("/bot/control")
async def control_bot(cmd: BotControl):
    if cmd.action == "start":
        bot.running = True
        bot.trade_logs.append("✅ 봇 작동 시작")
        logger.info("Bot started")
        return JSONResponse({"status": "bot started"})
    elif cmd.action == "stop":
        bot.running = False
        bot.trade_logs.append("⏹️ 봇 작동 중지")
        logger.info("Bot stopped")
        return JSONResponse({"status": "bot stopped"})
    else:
        return JSONResponse({"status": "unknown action"}, status_code=400)

# ─── 봇 상태 조회 ───────────────────────────────────────
@app.get("/bot/status")
async def get_status():
    # 계좌 잔고 조회
    usdt = next(
        (b["balance"] for b in bot.client.futures_account_balance() if b["asset"] == "USDT"),
        0
    )
    return {
        "running": bot.running,
        "position": bot.position,
        "entry_price": bot.entry_price,
        "balance": float(usdt),
    }

# ─── 최근 로그 조회 ─────────────────────────────────────
@app.get("/bot/logs")
async def get_logs():
    return {"logs": bot.trade_logs[-100:]}

# ─── React 정적 서빙 ───────────────────────────────────
frontend_build = os.path.join(os.path.dirname(__file__), "frontend", "build")
if os.path.isdir(frontend_build):
    app.mount("/", StaticFiles(directory=frontend_build, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
