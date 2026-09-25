from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.recarga import Recarga


router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "frontend" / "paginas"
MAPA_DIR = BASE_DIR / "backend" / "mapa"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
def view_index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )


@router.get("/mapa", response_class=HTMLResponse)
def view_mapa(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="mapa.html",
        context={},
    )


@router.get("/mapa-interativo")
def view_mapa_interativo():
    return FileResponse(
        str(MAPA_DIR / "index.html")
    )


@router.get("/carregando", response_class=HTMLResponse)
def view_carregando(
    request: Request,
    recarga_id: int | None = None,
    db: Session = Depends(get_db),
):
    recarga = None
    if recarga_id:
        recarga = db.get(Recarga, recarga_id)

    if not recarga:
        recarga = db.query(Recarga).order_by(Recarga.id.desc()).first()

    if recarga:
        recarga_dict = jsonable_encoder(recarga)
        capacidade = (
            float(recarga.veiculo.capacidade_bateria_kwh)
            if recarga.veiculo and recarga.veiculo.capacidade_bateria_kwh
            else 60.0
        )
        potencia = (
            float(recarga.conector.potencia_kw)
            if recarga.conector and recarga.conector.potencia_kw
            else 50.0
        )
        recarga_dict["capacidade_bateria_kwh"] = capacidade
        recarga_dict["potencia_conector_kw"] = potencia

        soc_ini = float(recarga_dict.get("soc_inicial") or 20.0)
        recarga_dict["soc_inicial"] = soc_ini

        percentual = (
            float(recarga_dict["percentual_desejado"])
            if recarga_dict.get("percentual_desejado") is not None
            else None
        )
        qtd = (
            float(recarga_dict["quantidade_kwh"])
            if recarga_dict.get("quantidade_kwh") is not None
            else None
        )

        if not qtd or qtd <= 0:
            meta_soc = percentual if percentual is not None else 80.0
            recarga_dict["quantidade_kwh"] = max(1.0, round(((meta_soc - soc_ini) / 100.0) * capacidade, 2))

        if not recarga_dict.get("preco_kwh") or float(recarga_dict["preco_kwh"]) <= 0:
            recarga_dict["preco_kwh"] = 2.10

        if recarga_dict.get("taxa_servico") is None:
            recarga_dict["taxa_servico"] = 0.0
    else:
        recarga_dict = {
            "id": 1,
            "usuario_id": 1,
            "veiculo_id": 1,
            "estacao_id": 1,
            "conector_id": 1,
            "modo": "ECONOMICO",
            "status": "EM_ANDAMENTO",
            "quantidade_kwh": 35.0,
            "percentual_desejado": 80.0,
            "soc_inicial": 20.0,
            "soc_atual": 20.0,
            "soc_final": 80.0,
            "preco_kwh": 2.10,
            "taxa_servico": 0.0,
            "capacidade_bateria_kwh": 60.0,
            "potencia_conector_kw": 50.0,
            "energia_entregue_kwh": 0.0,
            "valor_estimado": 73.50,
        }

    return templates.TemplateResponse(
        request=request,
        name="carregando.html",
        context={
            "recarga": recarga_dict,
        },
    )


@router.get("/pagamento", response_class=HTMLResponse)
def view_pagamento(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pagamento.html",
        context={},
    )


@router.get("/posto", response_class=HTMLResponse)
def view_posto(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="posto.html",
        context={},
    )


@router.get("/perfil", response_class=HTMLResponse)
def view_perfil(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="perfil.html",
        context={},
    )


@router.get("/recarga", response_class=HTMLResponse)
def view_recarga(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="recarga.html",
        context={},
    )


@router.get("/historicos", response_class=HTMLResponse)
def view_historicos(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="historicos.html",
        context={},
    )