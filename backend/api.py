from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from threading import Thread
from bot import BinanceBot

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://akiraa.netlify.app",
        "https://eveleen.netlify.app",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bot = BinanceBot()

@app.api_route("/", methods=["GET","HEAD"], include_in_schema=False)
def read_root(request: Request):
    if request.method == "HEAD": return JSONResponse(content=None, status_code=200)
    return {"message": "Binance Trading Bot API"}

@app.api_route("/ping", methods=["GET","HEAD"])
def ping(request: Request):
    if request.method=="HEAD": return Response(status_code=204)
    return {"status":"ok"}

@app.post("/bot/start")
def start_bot():
    if not bot.running:
        Thread(target=bot.start_bot).start()
        return {"message":"🚀 봇 시작됨"}
    return {"message":"⚠️ 봇 이미 실행중"}

@app.post("/bot/stop")
def stop_bot():
    if bot.running:
        bot.stop()
        return {"message":"🛑 봇 정지됨"}
    return {"message":"⚠️ 봇 이미 정지됨"}

@app.get("/bot/status")
def bot_status():
    return {
        "running": bot.running,
        "balance": bot.balance,
        "position": bot.position,
        "entry_price": bot.entry_price,
        "leverage": bot.leverage
    }

@app.get("/bot/logs")
def get_logs():
    return {"logs": bot.trade_logs}
