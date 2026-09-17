from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioResponse


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