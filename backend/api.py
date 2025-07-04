import os
import asyncio
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.websockets import WebSocketDisconnect, WebSocket
from pydantic import BaseModel
from bot import BinanceBot

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGINS", "*").split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BotControl(BaseModel):
    action: str  # 'start' 또는 'stop'

bot = BinanceBot()
clients: set[WebSocket] = set()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(bot.run())
    asyncio.create_task(log_broadcaster())

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
        bot.trade_logs.append("⏸️ 봇 작동 정지")
        return JSONResponse({"status": "bot stopped"})
    return JSONResponse({"error": "invalid action"}, status_code=400)

@app.post("/bot/start")
async def start_bot():
    bot.running = True
    logger.info("Bot started via /bot/start")
    bot.trade_logs.append("✅ 봇 작동 시작")
    return JSONResponse({"status": "bot started"})

@app.post("/bot/stop")
async def stop_bot():
    bot.running = False
    logger.info("Bot stopped via /bot/stop")
    bot.trade_logs.append("⏸️ 봇 작동 정지")
    return JSONResponse({"status": "bot stopped"})

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

@app.get("/bot/logs")
async def get_logs():
    logs = bot.trade_logs[-100:]
    return {"logs": logs}

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

if __name__ == "__main__":
    import uvicorn
    # h11 버퍼 크기를 기본 16KB -> 64KB로 확대하여 헤더 패킷을 안정적으로 처리
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        http="h11",
        h11_max_incomplete_event_size=65536,
        limit_concurrency=100,
        timeout_keep_alive=5
    )
