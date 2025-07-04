# backend/api.py

import os
import asyncio
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
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
    # REST 폴링 기반으로 봇을 백그라운드에서 실행
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

# ─── 봇 상태 조회 엔드포인트 ───────────────────────────────
@app.get("/bot/status")
async def get_status():
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

# ─── 최근 로그 조회 엔드포인트 ────────────────────────────
@app.get("/bot/logs")
async def get_logs():
    return {"logs": bot.trade_logs[-100:]}

# ─── React 정적 파일 서빙 및 SPA fallback ──────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 프로젝트 루트 기준으로 ../frontend/build
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, os.pardir, "frontend", "build"))

if os.path.isdir(FRONTEND_DIR):
    # 1) 정적 리소스(js/css/img 등)
    app.mount(
        "/static",
        StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")),
        name="static"
    )

    # 2) 루트 경로에 index.html 반환
    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    # 3) 그 외 모든 GET 요청도 index.html (SPA 라우팅 지원)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
