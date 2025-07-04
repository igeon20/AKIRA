import os
import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bot import BinanceBot

# FastAPI 앱 생성
app = FastAPI()

# CORS (필요한 origin만 설정하세요)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGINS", "*") .split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health-check (GET/HEAD) — UptimeRobot 등에서 OK 응답용
@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def root():
    return {"message": "Trading Bot API is running"}

# favicon 무응답
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

# 봇 제어 모델
class BotControl(BaseModel):
    action: str  # 'start' 또는 'stop'

# 봇 인스턴스와 WS 클라이언트 집합
bot = BinanceBot()
clients: set[WebSocket] = set()

# 서버 시작 시 봇·브로드캐스터 기동
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(bot.run())
    asyncio.create_task(log_broadcaster())

# 봇 시작/정지
@app.post("/bot/control")
async def control_bot(cmd: BotControl):
    if cmd.action == "start":
        bot.running = True
        return JSONResponse({"status": "bot started"})
    elif cmd.action == "stop":
        bot.running = False
        return JSONResponse({"status": "bot stopped"})
    return JSONResponse({"error": "invalid action"}, status_code=400)

# 봇 상태 조회
@app.get("/bot/status")
async def get_status():
    balance = float(next(
        (b["balance"] for b in bot.client.futures_account_balance() if b["asset"] == "USDT"),
        0
    ))
    return {
        "running": getattr(bot, "running", True),
        "position": bot.position,
        "entry_price": bot.entry_price,
        "balance": balance
    }

# **전체 로그**를 처음 불러올 때
@app.get("/bot/logs")
async def get_logs():
    # 뒤에서 100개만, 오래된 순으로 반환
    logs = bot.trade_logs[-100:]
    return {"logs": logs}

# WebSocket—새 로그 발생 시마다 브로드캐스트
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
            # 현재 잔고 조회
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
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
