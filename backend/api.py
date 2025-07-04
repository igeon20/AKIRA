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

# CORS 설정 (프론트엔드 도메인 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGINS", "*").split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 루트 엔드포인트 (GET/HEAD) - UptimeRobot용
@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def root():
    return {"message": "Trading Bot API is running"}

# favicon 요청 응답 (빈 콘텐츠)
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

# 봇 제어용 Pydantic 모델
class BotControl(BaseModel):
    action: str  # 'start' or 'stop'

# 트레이딩 봇 인스턴스 생성
bot = BinanceBot()
# WebSocket 클라이언트 집합
clients: set[WebSocket] = set()

@app.on_event("startup")
async def startup_event():
    # 봇 실행 및 로그 브로드캐스터 시작
    asyncio.create_task(bot.run())
    asyncio.create_task(log_broadcaster())

@app.post("/bot/control")
async def control_bot(cmd: BotControl):
    if cmd.action == "start":
        bot.running = True
        return JSONResponse({"status": "bot started"})
    elif cmd.action == "stop":
        bot.running = False
        return JSONResponse({"status": "bot stopped"})
    return JSONResponse({"error": "invalid action"}, status_code=400)

@app.get("/bot/status")
async def get_status():
    # 잔고 조회 (USDT)
    balance = float(next(
        (b['balance'] for b in bot.client.futures_account_balance() if b['asset'] == 'USDT'),
        0
    ))
    return {
        "running": getattr(bot, 'running', True),
        "position": bot.position,
        "entry_price": bot.entry_price,
        "balance": balance
    }

@app.websocket("/ws/logs")
async def websocket_logs(ws: WebSocket):
    # 클라이언트 연결
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
        new_logs = bot.trade_logs[idx:]
        for entry in new_logs:
            balance = float(next(
                (b['balance'] for b in bot.client.futures_account_balance() if b['asset'] == 'USDT'),
                0
            ))
            payload = {
                "log": entry,
                "balance": balance,
                "position": bot.position,
                "entry_price": bot.entry_price
            }
            # 모든 클라이언트에 전송
            for ws in list(clients):
                try:
                    await ws.send_json(payload)
                except:
                    clients.discard(ws)
        idx += len(new_logs)
        await asyncio.sleep(1)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
