from fastapi import FastAPI
from app.base.interface import RootResponse
from app.news.router import router as newsRouter
from app.ticker.router import router as tickerRouter
from app.signals.router import router as signalsRouter
from app.ai.router import router as aiRouter

app = FastAPI()
app.include_router(newsRouter)
app.include_router(tickerRouter)
app.include_router(signalsRouter)
app.include_router(aiRouter)

@app.get("/", response_model=RootResponse)
def read_root():
    return {"status": 200, "message": "Monii"}
