import time
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.usuario import Usuario

JWT_ALGORITHM = "HS256"


def criar_token(usuario_id: int, expira_em_segundos: int = 3600) -> str:
    payload = {
        "sub": str(usuario_id),
        "exp": int(time.time()) + expira_em_segundos,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)


def obter_usuario_logado(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Usuario:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária. Envie o cabeçalho Authorization: Bearer <token>",
        )

    partes = authorization.split()
    if len(partes) != 2 or partes[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Formato do token inválido. Use 'Bearer <token>'",
        )

    token = partes[1]
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[JWT_ALGORITHM])
        usuario_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
        )

    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário associado ao token não encontrado.",
        )

    return usuario
