from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.api.routes.ai import router as ai_router
from app.api.routes import views
from app.db.session import engine

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
BACKEND_DIR = BASE_DIR / "backend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    engine.dispose()


app = FastAPI(
    title="GoodWe API",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
app.mount("/backend/mapa", StaticFiles(directory=str(BACKEND_DIR / "mapa")), name="backend_mapa")

app.include_router(
    api_router,
    prefix="/api",
)

app.include_router(
    ai_router,
    prefix="/api/v1/ai",
    tags=["AI"],
)

app.include_router(
    views.router,
    tags=["Páginas Web"],
)