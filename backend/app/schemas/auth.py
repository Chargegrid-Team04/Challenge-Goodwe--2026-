from pydantic import BaseModel, ConfigDict
from app.schemas.usuario import UsuarioResponse


class RegisterRequest(BaseModel):
    nome: str
    email: str
    senha: str
    telefone: str | None = None
    url_foto: str | None = None


class AuthLoginRequest(BaseModel):
    email: str
    senha: str


class RefreshTokenRequest(BaseModel):
    usuario_id: int | None = 1
    email: str | None = None


class AuthResponse(BaseModel):
    mensagem: str
    usuario: UsuarioResponse

    model_config = ConfigDict(from_attributes=True)


class RefreshResponse(BaseModel):
    mensagem: str
    status: str = "ativo"
