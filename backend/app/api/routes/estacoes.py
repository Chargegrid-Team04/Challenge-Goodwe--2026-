from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.estacao import Estacao
from app.schemas.estacao import EstacaoResponse

router = APIRouter()


@router.get("", response_model=list[EstacaoResponse])
def listar_estacoes(
    busca: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Estacao).where(Estacao.ativa == True)
    if busca:
        termo = f"%{busca}%"
        stmt = stmt.where(Estacao.nome.ilike(termo) | Estacao.endereco.ilike(termo))

    return db.scalars(stmt).all()


@router.get("/{estacao_id}", response_model=EstacaoResponse)
def obter_estacao(
    estacao_id: int,
    db: Session = Depends(get_db),
):
    estacao = db.get(Estacao, estacao_id)
    if not estacao or not estacao.ativa:
        raise HTTPException(status_code=404, detail="Estação não encontrada.")
    return estacao
