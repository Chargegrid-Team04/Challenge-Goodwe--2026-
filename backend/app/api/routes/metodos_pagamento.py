from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import obter_usuario_logado
from app.db.session import get_db
from app.models.metodo_pagamento import MetodoPagamento
from app.models.usuario import Usuario
from app.schemas.metodo_pagamento import (
    MetodoPagamentoCreate,
    MetodoPagamentoResponse,
)

router = APIRouter()


@router.get("", response_model=list[MetodoPagamentoResponse])
def listar_metodos_pagamento(
    usuario_atual: Usuario = Depends(obter_usuario_logado),
    db: Session = Depends(get_db),
):
    stmt = (
        select(MetodoPagamento)
        .where(
            MetodoPagamento.usuario_id == usuario_atual.id,
            MetodoPagamento.ativo == True,
        )
        .order_by(MetodoPagamento.principal.desc(), MetodoPagamento.id.asc())
    )
    return db.scalars(stmt).all()


@router.post("", response_model=MetodoPagamentoResponse, status_code=status.HTTP_201_CREATED)
def criar_metodo_pagamento(
    dados: MetodoPagamentoCreate,
    usuario_atual: Usuario = Depends(obter_usuario_logado),
    db: Session = Depends(get_db),
):
    tipo_upper = dados.tipo.upper()
    if tipo_upper not in ("PIX", "CARTAO_CREDITO"):
        raise HTTPException(
            status_code=400,
            detail="Tipo de pagamento inválido. Use 'PIX' ou 'CARTAO_CREDITO'.",
        )

    if dados.principal:
        db.execute(
            update(MetodoPagamento)
            .where(MetodoPagamento.usuario_id == usuario_atual.id)
            .values(principal=False)
        )

    novo_metodo = MetodoPagamento(
        usuario_id=usuario_atual.id,
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
    usuario_atual: Usuario = Depends(obter_usuario_logado),
    db: Session = Depends(get_db),
):
    metodo = db.scalar(
        select(MetodoPagamento).where(
            MetodoPagamento.id == metodo_id,
            MetodoPagamento.usuario_id == usuario_atual.id,
            MetodoPagamento.ativo == True,
        )
    )
    if not metodo:
        raise HTTPException(status_code=404, detail="Método de pagamento não encontrado.")

    metodo.ativo = False
    db.commit()
    return {"mensagem": "Método de pagamento desativado com sucesso."}
