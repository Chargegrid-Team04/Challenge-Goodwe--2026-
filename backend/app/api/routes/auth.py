import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import JWT_ALGORITHM, criar_token
from app.core.config import settings
from app.core.security import gerar_hash_senha, verificar_senha
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.auth import AuthLoginRequest, RefreshTokenRequest, RegisterRequest, TokenResponse
from app.schemas.usuario import UsuarioResponse

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(dados: RegisterRequest, db: Session = Depends(get_db)):
    email_formatado = dados.email.strip().lower()
    existente = db.scalar(select(Usuario).where(Usuario.email == email_formatado))
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Já existe um usuário com este e-mail.",
        )

    novo_usuario = Usuario(
        nome=dados.nome,
        email=email_formatado,
        senha_hash=gerar_hash_senha(dados.senha),
        telefone=dados.telefone,
        url_foto=dados.url_foto,
    )
    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)

    access_token = criar_token(novo_usuario.id, expira_em_segundos=7200)
    refresh_token = criar_token(novo_usuario.id, expira_em_segundos=604800)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        usuario=UsuarioResponse.model_validate(novo_usuario),
    )


@router.post("/login", response_model=TokenResponse)
def login(dados: AuthLoginRequest, db: Session = Depends(get_db)):
    email_formatado = dados.email.strip().lower()
    usuario = db.scalar(select(Usuario).where(Usuario.email == email_formatado))

    if not usuario or not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos.",
        )

    access_token = criar_token(usuario.id, expira_em_segundos=7200)
    refresh_token = criar_token(usuario.id, expira_em_segundos=604800)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        usuario=UsuarioResponse.model_validate(usuario),
    )


@router.post("/refresh")
def refresh(dados: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(dados.refresh_token, settings.jwt_secret_key, algorithms=[JWT_ALGORITHM])
        usuario_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido ou expirado.",
        )

    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado.",
        )

    novo_access_token = criar_token(usuario.id, expira_em_segundos=7200)
    novo_refresh_token = criar_token(usuario.id, expira_em_segundos=604800)

    return {
        "access_token": novo_access_token,
        "refresh_token": novo_refresh_token,
        "token_type": "bearer",
    }
