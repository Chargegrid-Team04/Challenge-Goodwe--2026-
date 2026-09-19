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
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse

    model_config = ConfigDict(from_attributes=True)
