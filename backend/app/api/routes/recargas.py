from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import obter_usuario_logado
from app.db.session import get_db
from app.models.conector import Conector
from app.models.estacao import Estacao
from app.models.recarga import Recarga
from app.models.usuario import Usuario
from app.models.veiculo import Veiculo
from app.schemas.recarga import (
    EstimativaRecargaRequest,
    EstimativaRecargaResponse,
    RecargaCreate,
    RecargaResponse,
    ResumoRecargasResponse,
)

router = APIRouter()


def calcular_preco_kwh(estacao: Estacao, modo: str) -> Decimal:
    modo_upper = modo.upper()
    if modo_upper == "RAPIDO" and estacao.preco_rapido_kwh is not None:
        return Decimal(estacao.preco_rapido_kwh)
    if modo_upper == "ECONOMICO" and estacao.preco_economico_kwh is not None:
        return Decimal(estacao.preco_economico_kwh)
    if modo_upper == "INTELIGENTE" and estacao.preco_inteligente_kwh is not None:
        return Decimal(estacao.preco_inteligente_kwh)
    return Decimal(estacao.preco_base_kwh)


@router.post("/estimativa", response_model=EstimativaRecargaResponse)
def estimar_recarga(
    dados: EstimativaRecargaRequest,
    db: Session = Depends(get_db),
):
    estacao = db.get(Estacao, dados.estacao_id)
    if not estacao:
        raise HTTPException(status_code=404, detail="Estação não encontrada.")

    conector = db.get(Conector, dados.conector_id)
    if not conector:
        raise HTTPException(status_code=404, detail="Conector não encontrado.")

    veiculo = db.get(Veiculo, dados.veiculo_id)
    if not veiculo:
        raise HTTPException(status_code=404, detail="Veículo não encontrado.")

    quantidade_kwh = Decimal("0")
    if dados.quantidade_kwh and dados.quantidade_kwh > 0:
        quantidade_kwh = Decimal(dados.quantidade_kwh)
    elif dados.percentual_desejado is not None:
        soc_ini = Decimal(dados.soc_inicial or 0)
        delta_perc = max(Decimal(0), Decimal(dados.percentual_desejado) - soc_ini)
        quantidade_kwh = (delta_perc / Decimal(100)) * Decimal(veiculo.capacidade_bateria_kwh)
    else:
        quantidade_kwh = Decimal(veiculo.capacidade_bateria_kwh) * Decimal("0.8")

    preco_kwh = calcular_preco_kwh(estacao, dados.modo)
    taxa_servico = Decimal("2.50")
    valor_estimado = (quantidade_kwh * preco_kwh) + taxa_servico

    potencia = Decimal(conector.potencia_kw) if conector.potencia_kw > 0 else Decimal("22.0")
    tempo_estimado_minutos = int((quantidade_kwh / potencia) * Decimal(60))
    tempo_estimado_minutos = max(10, tempo_estimado_minutos)

    return EstimativaRecargaResponse(
        modo=dados.modo.upper(),
        preco_kwh=preco_kwh,
        quantidade_kwh=round(quantidade_kwh, 2),
        tempo_estimado_minutos=tempo_estimado_minutos,
        taxa_servico=taxa_servico,
        valor_estimado=round(valor_estimado, 2),
    )


@router.get("/resumo", response_model=ResumoRecargasResponse)
def obter_resumo_recargas(
    usuario_atual: Usuario = Depends(obter_usuario_logado),
    db: Session = Depends(get_db),
):
    recargas_usuario = db.scalars(
        select(Recarga).where(Recarga.usuario_id == usuario_atual.id)
    ).all()

    total_recargas = len(recargas_usuario)
    total_kwh = sum((Decimal(r.energia_entregue_kwh) for r in recargas_usuario), Decimal("0"))
    total_gasto = sum(
        (Decimal(r.valor_final or r.valor_estimado or 0) for r in recargas_usuario if r.status in ("CONCLUIDA", "PAGA")),
        Decimal("0"),
    )

    recarga_ativa = db.scalar(
        select(Recarga)
        .where(
            Recarga.usuario_id == usuario_atual.id,
            Recarga.status == "CARREGANDO",
        )
        .order_by(Recarga.id.desc())
    )

    return ResumoRecargasResponse(
        total_recargas=total_recargas,
        total_kwh=round(total_kwh, 2),
        total_gasto=round(total_gasto, 2),
        recarga_ativa=recarga_ativa,
    )


@router.get("", response_model=list[RecargaResponse])
def listar_recargas(
    usuario_atual: Usuario = Depends(obter_usuario_logado),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Recarga)
        .where(Recarga.usuario_id == usuario_atual.id)
        .order_by(Recarga.data_criacao.desc())
    )
    return db.scalars(stmt).all()


@router.post("", response_model=RecargaResponse, status_code=status.HTTP_201_CREATED)
def criar_recarga(
    dados: RecargaCreate,
    usuario_atual: Usuario = Depends(obter_usuario_logado),
    db: Session = Depends(get_db),
):
    estacao = db.get(Estacao, dados.estacao_id)
    if not estacao:
        raise HTTPException(status_code=404, detail="Estação não encontrada.")

    conector = db.get(Conector, dados.conector_id)
    if not conector:
        raise HTTPException(status_code=404, detail="Conector não encontrado.")

    veiculo = db.get(Veiculo, dados.veiculo_id)
    if not veiculo:
        raise HTTPException(status_code=404, detail="Veículo não encontrado.")

    preco_kwh = calcular_preco_kwh(estacao, dados.modo)
    taxa_servico = Decimal("2.50")

    quantidade = Decimal(dados.quantidade_kwh) if dados.quantidade_kwh else Decimal(veiculo.capacidade_bateria_kwh) * Decimal("0.8")
    valor_estimado = (quantidade * preco_kwh) + taxa_servico

    nova_recarga = Recarga(
        usuario_id=usuario_atual.id,
        veiculo_id=dados.veiculo_id,
        estacao_id=dados.estacao_id,
        conector_id=dados.conector_id,
        modo=dados.modo.upper(),
        status="PENDENTE",
        quantidade_kwh=quantidade,
        percentual_desejado=dados.percentual_desejado,
        tempo_disponivel_minutos=dados.tempo_disponivel_minutos,
        soc_inicial=dados.soc_inicial or Decimal("20"),
        soc_atual=dados.soc_inicial or Decimal("20"),
        preco_kwh=preco_kwh,
        taxa_servico=taxa_servico,
        valor_estimado=round(valor_estimado, 2),
        energia_entregue_kwh=Decimal("0.000"),
    )

    db.add(nova_recarga)
    db.commit()
    db.refresh(nova_recarga)
    return nova_recarga


@router.get("/{recarga_id}", response_model=RecargaResponse)
def obter_recarga(
    recarga_id: int,
    usuario_atual: Usuario = Depends(obter_usuario_logado),
    db: Session = Depends(get_db),
):
    recarga = db.scalar(
        select(Recarga).where(
            Recarga.id == recarga_id,
            Recarga.usuario_id == usuario_atual.id,
        )
    )
    if not recarga:
        raise HTTPException(status_code=404, detail="Recarga não encontrada.")
    return recarga


@router.post("/{recarga_id}/iniciar", response_model=RecargaResponse)
def iniciar_recarga(
    recarga_id: int,
    usuario_atual: Usuario = Depends(obter_usuario_logado),
    db: Session = Depends(get_db),
):
    recarga = db.scalar(
        select(Recarga).where(
            Recarga.id == recarga_id,
            Recarga.usuario_id == usuario_atual.id,
        )
    )
    if not recarga:
        raise HTTPException(status_code=404, detail="Recarga não encontrada.")

    recarga.status = "CARREGANDO"
    recarga.iniciada_em = datetime.now(timezone.utc)
    recarga.potencia_atual_kw = Decimal("22.0")
    recarga.tempo_restante_minutos = 45

    conector = db.get(Conector, recarga.conector_id)
    if conector:
        conector.status = "CARREGANDO"

    db.commit()
    db.refresh(recarga)
    return recarga


@router.post("/{recarga_id}/finalizar", response_model=RecargaResponse)
def finalizar_recarga(
    recarga_id: int,
    usuario_atual: Usuario = Depends(obter_usuario_logado),
    db: Session = Depends(get_db),
):
    recarga = db.scalar(
        select(Recarga).where(
            Recarga.id == recarga_id,
            Recarga.usuario_id == usuario_atual.id,
        )
    )
    if not recarga:
        raise HTTPException(status_code=404, detail="Recarga não encontrada.")

    recarga.status = "CONCLUIDA"
    recarga.finalizada_em = datetime.now(timezone.utc)
    recarga.soc_final = recarga.percentual_desejado or Decimal("100")
    recarga.energia_entregue_kwh = recarga.quantidade_kwh or Decimal("30.0")
    recarga.valor_final = recarga.valor_estimado
    recarga.potencia_atual_kw = Decimal("0.0")
    recarga.tempo_restante_minutos = 0

    conector = db.get(Conector, recarga.conector_id)
    if conector:
        conector.status = "DISPONIVEL"

    db.commit()
    db.refresh(recarga)
    return recarga


@router.post("/{recarga_id}/cancelar", response_model=RecargaResponse)
def cancelar_recarga(
    recarga_id: int,
    usuario_atual: Usuario = Depends(obter_usuario_logado),
    db: Session = Depends(get_db),
):
    recarga = db.scalar(
        select(Recarga).where(
            Recarga.id == recarga_id,
            Recarga.usuario_id == usuario_atual.id,
        )
    )
    if not recarga:
        raise HTTPException(status_code=404, detail="Recarga não encontrada.")

    recarga.status = "CANCELADA"
    conector = db.get(Conector, recarga.conector_id)
    if conector:
        conector.status = "DISPONIVEL"

    db.commit()
    db.refresh(recarga)
    return recarga
