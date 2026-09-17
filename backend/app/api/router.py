from fastapi import APIRouter

from app.api.routes import health, usuarios


api_router = APIRouter()

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"],
)

api_router.include_router(
    usuarios.router,
    prefix="/usuarios",
    tags=["Usuários"],
)
