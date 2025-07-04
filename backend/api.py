import os
import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from bot import BinanceBot

# 서버 시작 시 FastAPI 앱 인스턴스
app = FastAPI()
# 트레이딩 봇 인스턴스
bot = BinanceBot()
# WebSocket 클라이언트 세트
clients: set[WebSocket] = set()

# 루트 엔드포인트 추가 (404 방지)
@app.get("/")
async def read_root():
    return {"message": "Trading Bot API is running"}

# favicon 요청에 대한 빈 응답
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

# 봇 제어용 모델
class BotControl(BaseModel):
    action: str  # 'start' or 'stop'

# 앱 스타트업 시 실행 태스크 등록
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(bot.run())
    asyncio.create_task(log_broadcaster())

# 봇 시작/정지 제어
@app.post("/bot/control")
async def control_bot(cmd: BotControl):
    if cmd.action == 'start':
        bot.running = True
        return JSONResponse({"status": "bot started"})
    if cmd.action == 'stop':
        bot.running = False
        return JSONResponse({"status": "bot stopped"})
    return JSONResponse({"error": "invalid action"}, status_code=400)

# 봇 상태 조회
@app.get("/bot/status")
def get_status():
    balance = float(next(
        (b['balance'] for b in bot.client.futures_account_balance() if b['asset']=='USDT'),
        0
    ))
    return {
        "running": getattr(bot, 'running', True),
        "position": bot.position,
        "entry_price": bot.entry_price,
        "balance": balance
    }

# WebSocket 연결 처리
@app.websocket("/ws/logs")
async def websocket_logs(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        clients.discard(ws)

# 로그 브로드캐스터
async def log_broadcaster():
    idx = 0
    while True:
        new = bot.trade_logs[idx:]
        for entry in new:
            balance = float(next(
                (b['balance'] for b in bot.client.futures_account_balance() if b['asset']=='USDT'),
                0
            ))
            payload = {
                "log": entry,
                "balance": balance,
                "position": bot.position,
                "entry_price": bot.entry_price
            }
            for ws in list(clients):
                try:
                    await ws.send_json(payload)
                except:
                    clients.discard(ws)
        idx += len(new)
        await asyncio.sleep(1)

# Uvicorn 실행 엔트리포인트
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT",8000)))
