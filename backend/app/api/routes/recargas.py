from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.ocpp_ws import enviar_remote_start, enviar_remote_stop
from app.db.session import get_db
from app.models.conector import Conector
from app.models.estacao import Estacao
from app.models.recarga import Recarga
from app.models.veiculo import Veiculo
from app.schemas.recarga import (
    EstimativaRecargaRequest,
    EstimativaRecargaResponse,
    RecargaCreate,
    RecargaResponse,
    ResumoRecargasResponse,
)
from app.schemas.energy_management import (
    EnergyManagementRequest,
    EnergyManagementResponse,
)
from app.schemas.charging_prediction import (
    ChargingPredictionRequest,
    ChargingPredictionResponse,
)
from app.services.charging_prediction_service import predict_charging
from app.services.energy_management_service import (
    ChargingLoad,
    calculate_energy_management,
)
from app.services.charging_estimate_service import calculate_charging_estimate

router = APIRouter()


class ConcluirRecargaSimuladaRequest(BaseModel):
    energia_entregue_kwh: Decimal = Field(ge=0)
    soc_final: Decimal = Field(ge=0, le=100)
    valor_final: Decimal = Field(ge=0)
    status: str
    duracao_segundos: int = Field(ge=0)


@router.post(
    "/previsao-inteligente",
    response_model=ChargingPredictionResponse,
)
def prever_recarga_inteligente(
    dados: ChargingPredictionRequest,
    db: Session = Depends(get_db),
):
    estacao = db.get(Estacao, dados.estacao_id)

    if not estacao:
        raise HTTPException(
            status_code=404,
            detail="Estação não encontrada.",
        )

    veiculo = db.get(Veiculo, dados.veiculo_id)

    if not veiculo:
        raise HTTPException(
            status_code=404,
            detail="Veículo não encontrado.",
        )

    connector_types = {
        veiculo.tipo_conector.upper(),
        (veiculo.conector_secundario or "").upper(),
    }

    conector = next(
        (
            item
            for item in estacao.conectores
            if (
                item.tipo.upper() in connector_types
                and item.status.upper() == "DISPONIVEL"
            )
        ),
        None,
    )

    if not conector:
        conector = next(
            (
                item
                for item in estacao.conectores
                if item.status.upper() == "DISPONIVEL"
            ),
            None,
        )

    if not conector:
        raise HTTPException(
            status_code=409,
            detail="Nenhum conector disponível na estação.",
        )

    active_cars = len(
        db.scalars(
            select(Recarga).where(
                Recarga.estacao_id == dados.estacao_id,
                Recarga.status == "CARREGANDO",
            )
        ).all()
    )

    try:
        prediction = predict_charging(
            battery_capacity_kwh=Decimal(
                veiculo.capacidade_bateria_kwh
            ),
            current_soc_percent=dados.current_soc_percent,
            target_soc_percent=dados.target_soc_percent,
            requested_source=dados.requested_source,
            connector_power_kw=Decimal(
                conector.potencia_kw
            ),
            station_capacity_kw=dados.station_capacity_kw,
            base_price_per_kwh=Decimal(
                estacao.preco_base_kwh
            ),
            active_cars=active_cars,
            current_at=(
                dados.current_at
                or datetime.now(timezone.utc)
            ),
            solar_available_kw=dados.solar_available_kw,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return ChargingPredictionResponse(
        estacao_id=estacao.id,
        veiculo_id=veiculo.id,
        active_cars=prediction.active_cars,
        source=prediction.source,
        suggestion=prediction.suggestion,
        energy_required_kwh=prediction.energy_required_kwh,
        charging_power_kw=prediction.charging_power_kw,
        estimated_minutes=prediction.estimated_minutes,
        price_per_kwh=prediction.price_per_kwh,
        estimated_cost=prediction.estimated_cost,
        peak_period=prediction.peak_period,
        source_is_estimated=prediction.source_is_estimated,
    )


@router.post(
    "/controle-demanda",
    response_model=EnergyManagementResponse,
)
def controlar_demanda(
    dados: EnergyManagementRequest,
    db: Session = Depends(get_db),
):
    estacao = db.get(
        Estacao,
        dados.estacao_id,
    )

    if not estacao:
        raise HTTPException(
            status_code=404,
            detail="Estação não encontrada.",
        )

    recargas_ativas = db.scalars(
        select(Recarga).where(
            Recarga.estacao_id == dados.estacao_id,
            Recarga.status == "CARREGANDO",
        )
    ).all()

    loads = [
        ChargingLoad(
            charging_id=recarga.id,
            requested_power_kw=Decimal(
                recarga.potencia_atual_kw
                or recarga.conector.potencia_kw
                or 0
            ),
        )
        for recarga in recargas_ativas
    ]

    result = calculate_energy_management(
        loads,
        station_capacity_kw=dados.station_capacity_kw,
        base_price_per_kwh=Decimal(
            estacao.preco_base_kwh
        ),
        current_at=(
            dados.current_at
            or datetime.now(timezone.utc)
        ),
        peak_start=estacao.horario_pico_inicio,
        peak_end=estacao.horario_pico_fim,
        external_price_multiplier=dados.external_price_multiplier,
        minimum_power_kw=dados.minimum_power_kw,
    )

    if dados.aplicar_ajuste:
        allocations_by_id = {
            item.charging_id: item
            for item in result.allocations
        }

        for recarga in recargas_ativas:
            allocation = allocations_by_id.get(
                recarga.id
            )

            if allocation is not None:
                recarga.potencia_atual_kw = (
                    allocation.allocated_power_kw
                )

        db.commit()

    return EnergyManagementResponse(
        estacao_id=estacao.id,
        active_charging_count=len(recargas_ativas),
        total_requested_power_kw=result.total_requested_power_kw,
        total_allocated_power_kw=result.total_allocated_power_kw,
        available_power_kw=result.available_power_kw,
        utilization_percent=result.utilization_percent,
        price_per_kwh=result.price_per_kwh,
        price_multiplier=result.price_multiplier,
        peak_period=result.peak_period,
        allocations=[
            {
                "recarga_id": item.charging_id,
                "requested_power_kw": item.requested_power_kw,
                "allocated_power_kw": item.allocated_power_kw,
                "reduction_percent": item.reduction_percent,
            }
            for item in result.allocations
        ],
    )


def calcular_preco_kwh(
    estacao: Estacao,
    modo: str,
) -> Decimal:
    modo_upper = modo.upper()

    if (
        modo_upper == "RAPIDO"
        and estacao.preco_rapido_kwh is not None
    ):
        return Decimal(
            estacao.preco_rapido_kwh
        )

    if (
        modo_upper == "ECONOMICO"
        and estacao.preco_economico_kwh is not None
    ):
        return Decimal(
            estacao.preco_economico_kwh
        )

    if (
        modo_upper == "INTELIGENTE"
        and estacao.preco_inteligente_kwh is not None
    ):
        return Decimal(
            estacao.preco_inteligente_kwh
        )

    return Decimal(
        estacao.preco_base_kwh
    )


def _calcular_potencia_disponivel(
    db: Session,
    estacao: Estacao,
    conector: Conector,
) -> Decimal:
    """Infer remaining site headroom from connector ratings and live/reserved ports."""
    if conector.estacao_id != estacao.id:
        raise HTTPException(
            status_code=400,
            detail="O conector selecionado não pertence a este posto.",
        )

    if conector.status.upper() != "DISPONIVEL":
        raise HTTPException(
            status_code=409,
            detail="O conector selecionado não está disponível.",
        )

    conectores = list(estacao.conectores)
    capacidade_instalada = sum(
        (max(Decimal("0"), Decimal(item.potencia_kw)) for item in conectores),
        Decimal("0"),
    )
    recargas_ativas = db.scalars(
        select(Recarga).where(
            Recarga.estacao_id == estacao.id,
            Recarga.status == "CARREGANDO",
        )
    ).all()
    recargas_por_conector = {recarga.conector_id: recarga for recarga in recargas_ativas}
    if conector.id in recargas_por_conector:
        raise HTTPException(
            status_code=409,
            detail="O conector selecionado já possui uma recarga em andamento.",
        )

    potencia_em_uso = sum(
        (
            max(
                Decimal("0"),
                Decimal(
                    recarga.potencia_atual_kw
                    or recarga.conector.potencia_kw
                    or 0
                ),
            )
            for recarga in recargas_ativas
        ),
        Decimal("0"),
    )
    potencia_reservada = sum(
        (
            max(Decimal("0"), Decimal(item.potencia_kw))
            for item in conectores
            if item.status.upper() != "DISPONIVEL"
            and item.id not in recargas_por_conector
        ),
        Decimal("0"),
    )
    capacidade_disponivel = max(
        Decimal("0"),
        capacidade_instalada - potencia_em_uso - potencia_reservada,
    )
    return min(Decimal(conector.potencia_kw), capacidade_disponivel)


def _estimar_recarga_com_dados(
    db: Session,
    *,
    estacao_id: int,
    conector_id: int,
    veiculo_id: int,
    modo: str,
    percentual_desejado: Decimal,
    tempo_disponivel_minutos: int,
):
    estacao = db.get(Estacao, estacao_id)
    if not estacao or not estacao.ativa:
        raise HTTPException(status_code=404, detail="Posto não encontrado ou inativo.")

    conector = db.get(Conector, conector_id)
    if not conector:
        raise HTTPException(status_code=404, detail="Conector não encontrado.")

    veiculo = db.get(Veiculo, veiculo_id)
    if not veiculo or not veiculo.ativo:
        raise HTTPException(status_code=404, detail="Veículo não encontrado ou inativo.")
    if veiculo.soc_atual is None:
        raise HTTPException(status_code=400, detail="O veículo não possui SoC atual.")

    potencia_disponivel = _calcular_potencia_disponivel(db, estacao, conector)
    if potencia_disponivel <= 0:
        raise HTTPException(
            status_code=409,
            detail="O posto não tem potência disponível para uma nova recarga.",
        )

    preco_kwh = calcular_preco_kwh(estacao, modo)
    taxa_servico = Decimal("2.50")
    try:
        calculo = calculate_charging_estimate(
            battery_capacity_kwh=Decimal(veiculo.capacidade_bateria_kwh),
            current_soc_percent=Decimal(veiculo.soc_atual),
            target_soc_percent=percentual_desejado,
            available_power_kw=potencia_disponivel,
            available_minutes=tempo_disponivel_minutos,
            mode=modo,
            unit_price=preco_kwh,
            service_fee=taxa_servico,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return estacao, conector, veiculo, calculo


@router.post(
    "/estimativa",
    response_model=EstimativaRecargaResponse,
)
def estimar_recarga(
    dados: EstimativaRecargaRequest,
    db: Session = Depends(get_db),
):
    _, _, _, calculo = _estimar_recarga_com_dados(
        db,
        estacao_id=dados.estacao_id,
        conector_id=dados.conector_id,
        veiculo_id=dados.veiculo_id,
        modo=dados.modo,
        percentual_desejado=dados.percentual_desejado,
        tempo_disponivel_minutos=dados.tempo_disponivel_minutos,
    )

    return EstimativaRecargaResponse(
        modo=dados.modo.upper(),
        preco_kwh=calculo.unit_price,
        quantidade_kwh=calculo.quantity_kwh,
        tempo_estimado_minutos=calculo.estimated_minutes,
        tempo_disponivel_minutos=dados.tempo_disponivel_minutos,
        potencia_disponivel_kw=calculo.available_power_kw,
        potencia_alocada_kw=calculo.charging_power_kw,
        soc_atual=calculo.current_soc_percent,
        soc_estimado=calculo.estimated_soc_percent,
        percentual_desejado=calculo.target_soc_percent,
        valor_energia=calculo.energy_cost,
        taxa_servico=calculo.service_fee,
        valor_estimado=calculo.estimated_cost,
    )


@router.get(
    "/resumo",
    response_model=ResumoRecargasResponse,
)
def obter_resumo_recargas(
    usuario_id: int = Query(
        ...,
        description="ID do usuário logado",
    ),
    db: Session = Depends(get_db),
):
    stmt = select(Recarga).where(
        Recarga.usuario_id == usuario_id
    )

    recargas = db.scalars(
        stmt
    ).all()

    total_recargas = len(recargas)

    total_kwh = Decimal("0")
    total_gasto = Decimal("0")

    for r in recargas:
        kwh_val = r.energia_entregue_kwh if (r.energia_entregue_kwh is not None and r.energia_entregue_kwh > 0) else r.quantidade_kwh
        if kwh_val is not None:
            try:
                total_kwh += Decimal(str(kwh_val))
            except Exception:
                pass

        st = (r.status or "").upper()
        if st in ("CONCLUIDA", "CONCLUÍDA", "FINALIZADA") or r.valor_final is not None:
            val = r.valor_final if r.valor_final is not None else r.valor_estimado
            if val is not None:
                try:
                    total_gasto += Decimal(str(val))
                except Exception:
                    pass

    stmt_ativa = select(
        Recarga
    ).where(
        Recarga.status == "CARREGANDO"
    )

    stmt_ativa = stmt_ativa.where(
        Recarga.usuario_id == usuario_id
    )

    recarga_ativa = db.scalar(
        stmt_ativa.order_by(
            Recarga.id.desc()
        )
    )

    return ResumoRecargasResponse(
        total_recargas=total_recargas,
        total_kwh=round(
            total_kwh,
            2,
        ),
        total_gasto=round(
            total_gasto,
            2,
        ),
        recarga_ativa=recarga_ativa,
    )


@router.get(
    "",
    response_model=list[RecargaResponse],
)
def listar_recargas(
    usuario_id: int = Query(
        ...,
        description="ID do usuário logado",
    ),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Recarga)
        .where(
            Recarga.usuario_id == usuario_id
        )
        .order_by(
            Recarga.data_criacao.desc()
        )
    )

    return db.scalars(
        stmt
    ).all()


@router.post(
    "",
    response_model=RecargaResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_recarga(
    dados: RecargaCreate,
    db: Session = Depends(get_db),
):
    estacao, conector, veiculo, calculo = _estimar_recarga_com_dados(
        db,
        estacao_id=dados.estacao_id,
        conector_id=dados.conector_id,
        veiculo_id=dados.veiculo_id,
        modo=dados.modo,
        percentual_desejado=dados.percentual_desejado,
        tempo_disponivel_minutos=dados.tempo_disponivel_minutos,
    )

    soc_inicial = calculo.current_soc_percent
    preco_kwh = calcular_preco_kwh(
        estacao,
        dados.modo,
    )
    taxa_servico = calculo.service_fee
    quantidade = calculo.quantity_kwh
    valor_estimado = calculo.estimated_cost
    tempo_estimado_minutos = calculo.estimated_minutes

    nova_recarga = Recarga(
        usuario_id=veiculo.usuario_id,
        veiculo_id=dados.veiculo_id,
        estacao_id=dados.estacao_id,
        conector_id=dados.conector_id,
        modo=dados.modo.upper(),
        status="PENDENTE",

        quantidade_kwh=round(
            quantidade,
            2,
        ),

        percentual_desejado=dados.percentual_desejado,

        tempo_disponivel_minutos=
            dados.tempo_disponivel_minutos,

        soc_inicial=soc_inicial,
        soc_atual=soc_inicial,
        soc_final=None,

        preco_kwh=preco_kwh,
        taxa_servico=taxa_servico,

        valor_estimado=round(
            valor_estimado,
            2,
        ),

        valor_final=None,

        energia_entregue_kwh=
            Decimal("0.000"),

        potencia_atual_kw=calculo.charging_power_kw,

        tempo_restante_minutos=
            tempo_estimado_minutos,
    )

    db.add(
        nova_recarga
    )

    db.commit()
    db.refresh(
        nova_recarga
    )

    return nova_recarga


@router.get(
    "/{recarga_id}",
    response_model=RecargaResponse,
)
def obter_recarga(
    recarga_id: int,
    db: Session = Depends(get_db),
):
    recarga = db.get(
        Recarga,
        recarga_id,
    )

    if not recarga:
        raise HTTPException(
            status_code=404,
            detail="Recarga não encontrada.",
        )

    return recarga


@router.post(
    "/{recarga_id}/concluir-simulada",
    response_model=RecargaResponse,
)
def concluir_recarga_simulada(
    recarga_id: int,
    dados: ConcluirRecargaSimuladaRequest,
    db: Session = Depends(get_db),
):
    recarga = db.get(
        Recarga,
        recarga_id,
    )

    if not recarga:
        raise HTTPException(
            status_code=404,
            detail="Recarga não encontrada.",
        )

    status_final = (
        dados.status
        .strip()
        .upper()
    )

    if status_final not in (
        "CONCLUIDA",
        "CANCELADA",
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Status final deve ser "
                "CONCLUIDA ou CANCELADA."
            ),
        )

    veiculo = db.get(
        Veiculo,
        recarga.veiculo_id,
    )

    if not veiculo:
        raise HTTPException(
            status_code=404,
            detail="Veículo não encontrado.",
        )

    conector = db.get(
        Conector,
        recarga.conector_id,
    )

    agora = datetime.now(
        timezone.utc
    )

    recarga.status = (
        status_final
    )

    recarga.energia_entregue_kwh = (
        dados.energia_entregue_kwh
    )

    recarga.soc_atual = (
        dados.soc_final
    )

    recarga.soc_final = (
        dados.soc_final
    )

    recarga.valor_final = (
        dados.valor_final
    )

    recarga.potencia_atual_kw = (
        Decimal("0")
    )

    recarga.tempo_restante_minutos = 0

    recarga.iniciada_em = (
        agora
        - timedelta(
            seconds=dados.duracao_segundos
        )
    )

    recarga.finalizada_em = (
        agora
    )

    veiculo.soc_atual = (
        dados.soc_final
    )

    if conector:
        conector.status = (
            "DISPONIVEL"
        )

    db.commit()
    db.refresh(
        recarga
    )

    return recarga


@router.post(
    "/{recarga_id}/iniciar",
    response_model=RecargaResponse,
)
async def iniciar_recarga(
    recarga_id: int,
    db: Session = Depends(get_db),
):
    recarga = db.get(
        Recarga,
        recarga_id,
    )

    if not recarga:
        raise HTTPException(
            status_code=404,
            detail="Recarga não encontrada.",
        )

    conector = db.get(
        Conector,
        recarga.conector_id,
    )

    if not conector:
        raise HTTPException(
            status_code=404,
            detail="Conector não encontrado.",
        )

    aceito = await enviar_remote_start(
        conector.codigo,
        recarga.id,
    )

    if not aceito:
        raise HTTPException(
            status_code=409,
            detail=(
                "Carregador não conectado "
                "ou não aceitou o comando."
            ),
        )

    db.refresh(
        recarga
    )

    return recarga


@router.post(
    "/{recarga_id}/finalizar",
    response_model=RecargaResponse,
)
async def finalizar_recarga(
    recarga_id: int,
    db: Session = Depends(get_db),
):
    recarga = db.get(
        Recarga,
        recarga_id,
    )

    if not recarga:
        raise HTTPException(
            status_code=404,
            detail="Recarga não encontrada.",
        )

    conector = db.get(
        Conector,
        recarga.conector_id,
    )

    if not conector:
        raise HTTPException(
            status_code=404,
            detail="Conector não encontrado.",
        )

    aceito = await enviar_remote_stop(
        conector.codigo,
        recarga.id,
    )

    if not aceito:
        raise HTTPException(
            status_code=409,
            detail=(
                "Carregador não conectado "
                "ou não aceitou o comando."
            ),
        )

    db.refresh(
        recarga
    )

    return recarga


@router.post(
    "/{recarga_id}/cancelar",
    response_model=RecargaResponse,
)
def cancelar_recarga(
    recarga_id: int,
    db: Session = Depends(get_db),
):
    recarga = db.get(
        Recarga,
        recarga_id,
    )

    if not recarga:
        raise HTTPException(
            status_code=404,
            detail="Recarga não encontrada.",
        )

    recarga.status = (
        "CANCELADA"
    )

    conector = db.get(
        Conector,
        recarga.conector_id,
    )

    if conector:
        conector.status = (
            "DISPONIVEL"
        )

    db.commit()
    db.refresh(
        recarga
    )

    return recarga