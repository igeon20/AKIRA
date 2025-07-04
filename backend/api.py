import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from bot import BinanceBot

app = FastAPI()
bot = BinanceBot()
clients = set()

class BotControl(BaseModel):
    action: str  # 'start' or 'stop'

@app.on_event("startup")
async def startup_event():
    # 봇 실행
    asyncio.create_task(bot.run())
    # 로그 브로드캐스터 실행
    asyncio.create_task(log_broadcaster())

@app.post("/bot/control")
async def control_bot(cmd: BotControl):
    if cmd.action == 'start':
        bot.running = True
        return JSONResponse({"status": "bot started"})
    elif cmd.action == 'stop':
        bot.running = False
        return JSONResponse({"status": "bot stopped"})
    else:
        return JSONResponse({"error": "invalid action"}, status_code=400)

@app.get("/bot/status")
def get_status():
    return {
        "running": bot.running,
        "position": bot.position,
        "entry_price": bot.entry_price,
        "balance": bot.balance
    }

@app.websocket("/ws/logs")
async def websocket_logs(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        clients.remove(ws)

async def log_broadcaster():
    last = 0
    while True:
        # trade_logs 업데이트된 부분만 브로드캐스트
        logs = bot.trade_logs[last:]
        for entry in logs:
            payload = {
                "log": entry,
                "balance": bot.balance,
                "position": bot.position,
                "entry_price": bot.entry_price
            }
            dead = []
            for ws in clients:
                try:
                    await ws.send_json(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                clients.discard(ws)
        last += len(logs)
        await asyncio.sleep(1)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
