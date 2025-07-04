# backend/api.py
import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from bot import BinanceBot

app = FastAPI()
bot = BinanceBot()
clients: set[WebSocket] = set()

class BotControl(BaseModel):
    action: str  # 'start' or 'stop'

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(bot.run())
    asyncio.create_task(log_broadcaster())

@app.post("/bot/control")
async def control_bot(cmd: BotControl):
    if cmd.action == 'start':
        bot.running = True
        return JSONResponse({"status": "bot started"})
    if cmd.action == 'stop':
        bot.running = False
        return JSONResponse({"status": "bot stopped"})
    return JSONResponse({"error": "invalid action"}, status_code=400)

@app.get("/bot/status")
def get_status():
    return {
        "running": getattr(bot, 'running', True),
        "position": bot.position,
        "entry_price": bot.entry_price,
        "balance": float(next(
            (b['balance'] for b in bot.client.futures_account_balance() if b['asset']=='USDT'), 0
        ))
    }

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
        for entry in new:
            payload = {
                "log": entry,
                "balance": float(next(
                    (b['balance'] for b in bot.client.futures_account_balance() if b['asset']=='USDT'), 0
                )),
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT",8000)))
