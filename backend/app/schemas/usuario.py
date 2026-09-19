from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UsuarioResponse(BaseModel):
    id: int
    nome: str
    email: str
    telefone: str | None
    url_foto: str | None
    data_criacao: datetime

    model_config = ConfigDict(from_attributes=True)


class UsuarioCreate(BaseModel):
    nome: str
    email: str
    senha: str
    telefone: str | None = None
    url_foto: str | None = None


class LoginRequest(BaseModel):
    email: str
    senha: str


class LoginResponse(BaseModel):
    mensagem: str
    usuario: UsuarioResponse