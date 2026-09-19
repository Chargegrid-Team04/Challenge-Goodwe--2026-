from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import gerar_hash_senha, verificar_senha
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.usuario import (
    LoginRequest,
    LoginResponse,
    UsuarioCreate,
    UsuarioResponse,
)


router = APIRouter()


@router.get("/{usuario_id}", response_model=UsuarioResponse)
def buscar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
):
    usuario = db.get(Usuario, usuario_id)

    if usuario is None:
        raise HTTPException(
            status_code=404,
            detail="Usuário não encontrado",
        )

    return usuario

@router.get("/email/{email}", response_model=UsuarioResponse)
def buscar_usuario_por_email(
    email: str,
    db: Session = Depends(get_db),
):
    usuario = db.scalar(select(Usuario).where(Usuario.email == email))

    if usuario is None:
        raise HTTPException(
            status_code=404,
            detail="Usuário não encontrado",
        )

    return usuario


def autenticar_usuario(db: Session, email: str, senha: str) -> Usuario | None:
    usuario = db.scalar(
        select(Usuario).where(Usuario.email == email.strip().lower())
    )

    if not usuario or not verificar_senha(senha, usuario.senha_hash):
        return None

    return usuario


@router.post("/login", response_model=LoginResponse)
def login(
    dados: LoginRequest,
    db: Session = Depends(get_db),
):
    usuario = autenticar_usuario(db, email=dados.email, senha=dados.senha)

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos.",
        )

    return LoginResponse(
        mensagem="Login realizado com sucesso!",
        usuario=usuario,
    )


@router.post("", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
def criar_usuario(
    dados: UsuarioCreate,
    db: Session = Depends(get_db),
):
    email_formatado = dados.email.strip().lower()
    usuario_existente = db.scalar(
        select(Usuario).where(Usuario.email == email_formatado)
    )

    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Já existe um usuário cadastrado com este e-mail.",
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

    return novo_usuario