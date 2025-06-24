from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from threading import Thread

# bot.py 파일에서 BinanceBot 클래스를 임포트합니다.
# 이전에 api.py 파일 내부에 있던 BinanceBot 클래스 정의는 bot.py에만 있어야 합니다.
from bot import BinanceBot 

app = FastAPI()

# ⭐️ CORS 설정 (서버-프론트 주소에 맞게 수정)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://akiraa.netlify.app",      # 예비: 이전 프론트
        "https://eveleen.netlify.app",     # 실제 프론트
        "http://localhost:3000",           # 로컬 개발용
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# BinanceBot 인스턴스를 생성합니다.
# 이 인스턴스는 bot.py 파일에 정의된 클래스를 사용합니다.
bot = BinanceBot()

# ✅ UptimeRobot, HEAD 대응용 루트 엔드포인트
@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
def read_root(request: Request):
    if request.method == "HEAD":
        return JSONResponse(content=None, status_code=200)
    return {"message": "Binance Trading Bot API"}

# ✅ /ping 엔드포인트 - 서버 모니터링 용도
@app.api_route("/ping", methods=["GET", "HEAD"])
def ping(request: Request):
    if request.method == "HEAD":
        return Response(status_code=204)
    return {"status": "ok"}

# ✅ 봇 제어
@app.post("/bot/start")
def start_bot():
    if not bot.running:
        Thread(target=bot.start_bot).start()
        return {"message": "🚀 봇 시작됨"}
    return {"message": "⚠️ 봇 이미 실행중"}

@app.post("/bot/stop")
def stop_bot():
    if bot.running:
        bot.stop()
        return {"message": "🛑 봇 정지됨"}
    return {"message": "⚠️ 봇 이미 정지됨"}

@app.get("/bot/status")
def bot_status():
    return {
        "running": bot.running,
        "balance": bot.balance,
        "position": bot.position,       # 현재 포지션 (1:롱, -1:숏, 0:없음)
        "entry_price": bot.entry_price, # 진입 가격
        "leverage": bot.leverage        # 레버리지
    }

@app.get("/bot/logs")
def get_logs():
    return {"logs": bot.trade_logs}

# ⚠️ Render는 __main__에서 uvicorn.run()을 호출하지 않음!
# 배포 환경에서는 Procfile이나 render.yaml이 자동 실행함
