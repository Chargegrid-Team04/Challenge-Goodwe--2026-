import random
import time

from fastapi import APIRouter, HTTPException, status

from app.schemas.dois_fatores import (
    Enviar2FARequest,
    Enviar2FAResponse,
    Verificar2FARequest,
    Verificar2FAResponse,
)

router = APIRouter()

_codigos_ativos: dict[str, dict] = {}


@router.post("/enviar", response_model=Enviar2FAResponse)
def enviar_codigo_2fa(dados: Enviar2FARequest):
    identificador = dados.identificador.strip().lower()
    codigo = f"{random.randint(100000, 999999)}"
    expira_em = time.time() + 300  # 5 minutos

    _codigos_ativos[identificador] = {
        "codigo": codigo,
        "expira_em": expira_em,
    }

    return Enviar2FAResponse(
        mensagem=f"Código de verificação enviado para {dados.identificador}.",
        expira_em_segundos=300,
        codigo_simulado=codigo,
    )


@router.post("/verificar", response_model=Verificar2FAResponse)
def verificar_codigo_2fa(dados: Verificar2FARequest):
    identificador = dados.identificador.strip().lower()
    registro = _codigos_ativos.get(identificador)

    if not registro:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum código pendente para este identificador. Solicite um novo código.",
        )

    if time.time() > registro["expira_em"]:
        _codigos_ativos.pop(identificador, None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código de verificação expirado. Solicite um novo código.",
        )

    if registro["codigo"] != dados.codigo.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código de verificação incorreto.",
        )

    _codigos_ativos.pop(identificador, None)
    return Verificar2FAResponse(
        valido=True,
        mensagem="Código 2FA verificado com sucesso!",
    )
