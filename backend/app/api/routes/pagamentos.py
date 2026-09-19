from datetime import datetime, timezone
from decimal import Decimal
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.metodo_pagamento import MetodoPagamento
from app.models.pagamento import Pagamento
from app.models.recarga import Recarga
from app.schemas.pagamento import PagamentoCreate, PagamentoResponse

router = APIRouter()


@router.post("", response_model=PagamentoResponse, status_code=status.HTTP_201_CREATED)
def criar_pagamento(
    dados: PagamentoCreate,
    db: Session = Depends(get_db),
):
    recarga = db.get(Recarga, dados.recarga_id)
    if not recarga:
        raise HTTPException(status_code=404, detail="Recarga não encontrada.")

    valor_pagamento = dados.valor or recarga.valor_final or recarga.valor_estimado or Decimal("10.00")

    if dados.metodo_pagamento_id:
        metodo = db.get(MetodoPagamento, dados.metodo_pagamento_id)
        if not metodo:
            raise HTTPException(status_code=404, detail="Método de pagamento inválido.")

    novo_pagamento = Pagamento(
        recarga_id=dados.recarga_id,
        metodo_pagamento_id=dados.metodo_pagamento_id,
        valor=valor_pagamento,
        status="PAGO",
        transacao_gateway=f"tx_{uuid.uuid4().hex[:12]}",
        pago_em=datetime.now(timezone.utc),
    )

    recarga.status = "CONCLUIDA"

    db.add(novo_pagamento)
    db.commit()
    db.refresh(novo_pagamento)
    return novo_pagamento


@router.get("/{pagamento_id}", response_model=PagamentoResponse)
def obter_pagamento(
    pagamento_id: int,
    db: Session = Depends(get_db),
):
    pagamento = db.get(Pagamento, pagamento_id)
    if not pagamento:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado.")

    return pagamento
