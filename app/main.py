from fastapi import FastAPI
from app.base.interface import RootResponse
from app.news.router import router as newsRouter
from app.ticker.router import router as tickerRouter
from app.signals.router import router as signalsRouter
from app.ai.router import router as aiRouter
from app.notification.router import router as notificationRouter
from fastapi.middleware.cors import CORSMiddleware
from chainlit.utils import mount_chainlit
from fastapi.staticfiles import StaticFiles

origins = [
    "https://okane-signals.vercel.app",
    "https://okane-signals-git-dev-pointmekins-projects.vercel.app",
    "https://okane-signals-i66hoyzcj-pointmekins-projects.vercel.app",
    # Wildcard for any Vercel preview deployments with okane-signals
    "https://*okane-signals*.vercel.app",
    "https://*okane-signals*.pointmekins-projects.vercel.app",
    
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:4173",
    "http://localhost:3000",
]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(newsRouter)
app.include_router(tickerRouter)
app.include_router(signalsRouter)
app.include_router(aiRouter)
app.include_router(notificationRouter)
app.mount("/public", StaticFiles(directory="public"), name="public")
app.mount("/logo", StaticFiles(directory="public"), name="public")

@app.get("/", response_model=RootResponse)
def read_root():
    return {"status": 200, "message": "Monii 0.1.0"}

mount_chainlit(app=app, target="app/chainlit/chainlit.py", path="/chat")

