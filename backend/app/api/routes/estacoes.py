from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.conector import Conector
from app.models.estacao import Estacao
from app.models.veiculo import Veiculo
from app.schemas.estacao import EstacaoResponse

router = APIRouter()


@router.get("", response_model=list[EstacaoResponse])
def listar_estacoes(
    busca: str | None = Query(None, description="Busca por nome ou endereço"),
    disponivel: bool | None = Query(None, description="Apenas postos com conectores livres agora"),
    compativel: bool | None = Query(None, description="Apenas postos compatíveis com o veículo do usuário"),
    ordenar_por: str | None = Query(None, description="PRECO ou POTENCIA"),
    usuario_id: int | None = Query(1, description="ID do usuário para verificar veículo compatível"),
    db: Session = Depends(get_db),
):
    stmt = select(Estacao).where(Estacao.ativa == True)

    if busca:
        termo = f"%{busca.strip()}%"
        stmt = stmt.where(Estacao.nome.ilike(termo) | Estacao.endereco.ilike(termo))

    if disponivel:
        stmt = stmt.where(Estacao.conectores.any(Conector.status == "DISPONIVEL"))

    if compativel:
        veiculo = db.scalar(
            select(Veiculo)
            .where(Veiculo.usuario_id == (usuario_id or 1), Veiculo.ativo == True)
            .order_by(Veiculo.principal.desc())
        )
        if veiculo:
            tipos = [veiculo.tipo_conector]
            if veiculo.conector_secundario:
                tipos.append(veiculo.conector_secundario)
            stmt = stmt.where(Estacao.conectores.any(Conector.tipo.in_(tipos)))

    if ordenar_por == "PRECO":
        stmt = stmt.order_by(Estacao.preco_base_kwh.asc())
    elif ordenar_por == "POTENCIA":
        sub_potencia = (
            select(func.max(Conector.potencia_kw))
            .where(Conector.estacao_id == Estacao.id)
            .scalar_subquery()
        )
        stmt = stmt.order_by(sub_potencia.desc().nullslast())

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
