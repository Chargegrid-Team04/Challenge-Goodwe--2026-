from fastapi import APIRouter

from app.api.routes import (
    auth,
    dois_fatores,
    estacoes,
    health,
    metodos_pagamento,
    pagamentos,
    recargas,
    usuarios,
    veiculos,
)

api_router = APIRouter()

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"],
)

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Auth"],
)

api_router.include_router(
    usuarios.router,
    prefix="/usuarios",
    tags=["Usuários"],
)

api_router.include_router(
    veiculos.router,
    prefix="/veiculos",
    tags=["Veículos"],
)

api_router.include_router(
    estacoes.router,
    prefix="/estacoes",
    tags=["Estações"],
)

api_router.include_router(
    recargas.router,
    prefix="/recargas",
    tags=["Recargas"],
)

api_router.include_router(
    metodos_pagamento.router,
    prefix="/metodos-pagamento",
    tags=["Métodos de Pagamento"],
)

api_router.include_router(
    pagamentos.router,
    prefix="/pagamentos",
    tags=["Pagamentos"],
)

api_router.include_router(
    dois_fatores.router,
    prefix="/2fa",
    tags=["2FA"],
)
