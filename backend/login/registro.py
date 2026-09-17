import re
from typing import List, Optional
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from app.models.usuario import Usuario 
from main import SessionLocal

# ==========================================
# SCHEMAS DE VALIDAÇÃO (Pydantic)
# ==========================================


class VeiculoSchema(BaseModel):
    marca: str
    modelo_ano: str
    placa: str
    cor: str
    carroceria: str


class RegistroUsuarioSchema(BaseModel):
    nome_completo: str
    email: EmailStr
    cpf: str
    telefone: str
    senha: str
    cep_endereco: str
    veiculo: VeiculoSchema


class LoginSchema(BaseModel):
    login: str  # Pode ser Email ou CPF
    senha: str


# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================


def get_db():
    """Gerencia a sessão com o banco de dados por requisição."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def validar_senha(senha: str) -> bool:
    """Garante no mínimo 4 caracteres e 2 letras."""
    if len(senha) < 4:
        return False
    letras = len(re.findall(r"[a-zA-Z]", senha))
    return letras >= 2


def sanitizar_numeros(texto: str) -> str:
    """Remove pontuações e mantém apenas números."""
    return re.sub(r"\D", "", texto)


# ==========================================
# APLICAÇÃO FASTAPI E ROTAS
# ==========================================

app = FastAPI(
    title="EV Charging Station API",
    description="API de cadastro, login e mapeamento para carregadores de veículos elétricos.",
    version="1.0.0",
)


@app.post("/api/registro", status_code=status.HTTP_201_CREATED)
def registrar_usuario(
    dados: RegistroUsuarioSchema, db: Session = Depends(get_db)
):
    # 1. Validação de Senha
    if not validar_senha(dados.senha):
        raise HTTPException(
            status_code=400,
            detail="A senha deve ter no mínimo 4 caracteres e conter pelo menos 2 letras.",
        )

    # 2. Tratamento de campos
    email = dados.email.strip().lower()
    cpf = sanitizar_numeros(dados.cpf)
    telefone = sanitizar_numeros(dados.telefone)

    # 3. Verificação de Duplicatas no Model Usuario
    if db.query(Usuario).filter(Usuario.email == email).first():
        raise HTTPException(
            status_code=409, detail="Este e-mail já está cadastrado."
        )
    if db.query(Usuario).filter(Usuario.cpf == cpf).first():
        raise HTTPException(
            status_code=409, detail="Este CPF já está cadastrado."
        )
    if db.query(Usuario).filter(Usuario.telefone == telefone).first():
        raise HTTPException(
            status_code=409, detail="Este telefone já está cadastrado."
        )

    # 4. Criação do Usuário
    novo_usuario = Usuario(
        nome_completo=dados.nome_completo,
        email=email,
        cpf=cpf,
        telefone=telefone,
        senha_hash=generate_password_hash(dados.senha),
        cep_endereco=dados.cep_endereco,
    )

    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)

    return {
        "mensagem": "Usuário cadastrado com sucesso!",
        "usuario_id": novo_usuario.id,
    }


@app.post("/api/login")
def login(dados: LoginSchema, db: Session = Depends(get_db)):
    identificador_limpo = sanitizar_numeros(dados.login)

    # Busca usuário por Email ou por CPF usando a classe Usuario
    usuario = (
        db.query(Usuario)
        .filter(
            (Usuario.email == dados.login.strip().lower())
            | (Usuario.cpf == identificador_limpo)
        )
        .first()
    )

    if not usuario or not check_password_hash(usuario.senha_hash, dados.senha):
        raise HTTPException(
            status_code=401, detail="Credenciais inválidas."
        )

    codigo_2fa = "123456"

    return {
        "mensagem": "Credenciais válidas. Digite o código enviado para o seu dispositivo.",
        "usuario_id": usuario.id,
        "codigo_dev_teste": codigo_2fa,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("registro:app", host="127.0.0.1", port=8000, reload=True)
