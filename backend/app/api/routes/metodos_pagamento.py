from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.metodo_pagamento import MetodoPagamento
from app.schemas.metodo_pagamento import (
    MetodoPagamentoCreate,
    MetodoPagamentoResponse,
)

router = APIRouter()


@router.get("", response_model=list[MetodoPagamentoResponse])
def listar_metodos_pagamento(
    usuario_id: int | None = Query(None, description="Filtrar por ID do usuário"),
    db: Session = Depends(get_db),
):
    stmt = select(MetodoPagamento).where(MetodoPagamento.ativo == True)
    if usuario_id is not None:
        stmt = stmt.where(MetodoPagamento.usuario_id == usuario_id)
    stmt = stmt.order_by(MetodoPagamento.principal.desc(), MetodoPagamento.id.asc())
    return db.scalars(stmt).all()


@router.post("", response_model=MetodoPagamentoResponse, status_code=status.HTTP_201_CREATED)
def criar_metodo_pagamento(
    dados: MetodoPagamentoCreate,
    db: Session = Depends(get_db),
):
    user_id = dados.usuario_id or 1
    tipo_upper = dados.tipo.upper()
    if tipo_upper not in ("PIX", "CARTAO_CREDITO"):
        raise HTTPException(
            status_code=400,
            detail="Tipo de pagamento inválido. Use 'PIX' ou 'CARTAO_CREDITO'.",
        )

    if dados.principal:
        db.execute(
            update(MetodoPagamento)
            .where(MetodoPagamento.usuario_id == user_id)
            .values(principal=False)
        )

    novo_metodo = MetodoPagamento(
        usuario_id=user_id,
        tipo=tipo_upper,
        bandeira=dados.bandeira,
        ultimos_4=dados.ultimos_4,
        token_gateway=dados.token_gateway or f"tok_{tipo_upper.lower()}_mock",
        principal=dados.principal,
        ativo=True,
    )

    db.add(novo_metodo)
    db.commit()
    db.refresh(novo_metodo)
    return novo_metodo


@router.delete("/{metodo_id}", status_code=status.HTTP_200_OK)
def deletar_metodo_pagamento(
    metodo_id: int,
    db: Session = Depends(get_db),
):
    metodo = db.get(MetodoPagamento, metodo_id)
    if not metodo or not metodo.ativo:
        raise HTTPException(status_code=404, detail="Método de pagamento não encontrado.")

    metodo.ativo = False
    db.commit()
    return {"mensagem": "Método de pagamento desativado com sucesso."}
