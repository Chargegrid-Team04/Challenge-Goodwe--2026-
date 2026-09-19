from pydantic import BaseModel


class Enviar2FARequest(BaseModel):
    identificador: str 


class Enviar2FAResponse(BaseModel):
    mensagem: str
    expira_em_segundos: int = 300
    codigo_simulado: str | None = None


class Verificar2FARequest(BaseModel):
    identificador: str
    codigo: str


class Verificar2FAResponse(BaseModel):
    valido: bool
    mensagem: str
