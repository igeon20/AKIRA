import os
import asyncio
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.websockets import WebSocketDisconnect, WebSocket
from fastapi.staticfiles import StaticFiles    # 추가
from pydantic import BaseModel
from bot import BinanceBot

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

app = FastAPI()

# ─── CORS 설정 ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGINS", "*").split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 봇 인스턴스 및 WS 클라이언트 관리 ───────────────────────────
class BotControl(BaseModel):
    action: str  # 'start' 또는 'stop'

bot = BinanceBot()
clients: set[WebSocket] = set()

@app.on_event("startup")
async def startup_event():
    # 봇 백그라운드 실행
    asyncio.create_task(bot.run())
    # 로그 브로드캐스트 태스크
    asyncio.create_task(log_broadcaster())

# ─── 봇 제어 Endpoint ────────────────────────────────────────────
@app.post("/bot/control")
async def control_bot(cmd: BotControl):
    if cmd.action == "start":
        bot.running = True
        logger.info("Bot started via /bot/control")
        bot.trade_logs.append("✅ 봇 작동 시작")
        return JSONResponse({"status": "bot started"})
    elif cmd.action == "stop":
        bot.running = False
        logger.info("Bot stopped via /bot/control")
        bot.trade_logs.append("⏹️ 봇 작동 중지")
        return JSONResponse({"status": "bot stopped"})
    else:
        return JSONResponse({"status": "unknown action"}, status_code=400)

# ─── 봇 상태 조회 Endpoint ───────────────────────────────────────
@app.get("/bot/status")
async def get_status():
    balance = float(next(
        (b["balance"] for b in bot.client.futures_account_balance() if b["asset"] == "USDT"),
        0
    ))
    return {
        "running": bot.running,
        "position": bot.position,
        "entry_price": bot.entry_price,
        "balance": balance
    }

# ─── 최근 로그 조회 Endpoint ─────────────────────────────────────
@app.get("/bot/logs")
async def get_logs():
    logs = bot.trade_logs[-100:]
    return {"logs": logs}

# ─── WebSocket 로그 스트리밍 ────────────────────────────────────
@app.websocket("/ws/logs")
async def websocket_logs(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        clients.discard(ws)

async def log_broadcaster():
    idx = 0
    while True:
        new = bot.trade_logs[idx:]
        if new:
            # 매 전송 시점의 잔고도 함께 보냄
            balance = float(next(
                (b["balance"] for b in bot.client.futures_account_balance() if b["asset"] == "USDT"),
                0
            ))
            payloads = [
                {
                    "log": entry,
                    "balance": balance,
                    "position": bot.position,
                    "entry_price": bot.entry_price
                }
                for entry in new
            ]
            for ws in list(clients):
                for p in payloads:
                    try:
                        await ws.send_json(p)
                    except:
                        clients.discard(ws)
        idx += len(new)
        await asyncio.sleep(1)

# ─── React 정적 파일 서빙 ───────────────────────────────────────
frontend_build = os.path.join(os.path.dirname(__file__), "frontend", "build")
if os.path.isdir(frontend_build):
    # API(/bot/...)가 우선 처리되고, 그 외는 React 빌드 산출물을 서빙
    app.mount("/", StaticFiles(directory=frontend_build, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    # h11 버퍼 크기를 기본 16KB → 64KB로 확대하여 헤더 안정성 확보
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        http="h11",
        h11_max_incomplete_event_size=65536,
        limit_concurrency=100,
        timeout_keep_alive=5
    )
