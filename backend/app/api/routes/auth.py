from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import gerar_hash_senha, verificar_senha
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.auth import (
    AuthLoginRequest,
    AuthResponse,
    RefreshResponse,
    RefreshTokenRequest,
    RegisterRequest,
)
from app.schemas.usuario import UsuarioResponse

router = APIRouter()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
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

    return AuthResponse(
        mensagem="Usuário registrado com sucesso!",
        usuario=UsuarioResponse.model_validate(novo_usuario),
    )


@router.post("/login", response_model=AuthResponse)
def login(dados: AuthLoginRequest, db: Session = Depends(get_db)):
    email_formatado = dados.email.strip().lower()
    usuario = db.scalar(select(Usuario).where(Usuario.email == email_formatado))

    if not usuario or not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos.",
        )

    return AuthResponse(
        mensagem="Login realizado com sucesso!",
        usuario=UsuarioResponse.model_validate(usuario),
    )


@router.post("/refresh", response_model=RefreshResponse)
def refresh(dados: RefreshTokenRequest | None = None):
    return RefreshResponse(
        mensagem="Sessão atualizada com sucesso.",
        status="ativo",
    )
