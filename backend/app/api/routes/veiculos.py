from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.veiculo import Veiculo
from app.schemas.veiculo import (
    VeiculoCreate,
    VeiculoResponse,
    VeiculoUpdate,
)

router = APIRouter()


@router.get("", response_model=list[VeiculoResponse])
def listar_veiculos(
    usuario_id: int | None = Query(
        None,
        description="Filtrar por ID do usuário",
    ),
    db: Session = Depends(get_db),
):
    stmt = select(Veiculo).where(
        Veiculo.ativo.is_(True)
    )

    if usuario_id is not None:
        stmt = stmt.where(
            Veiculo.usuario_id == usuario_id
        )

    stmt = stmt.order_by(
        Veiculo.principal.desc(),
        Veiculo.id.asc(),
    )

    return db.scalars(stmt).all()


@router.post(
    "",
    response_model=VeiculoResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_veiculo(
    dados: VeiculoCreate,
    db: Session = Depends(get_db),
):
    user_id = dados.usuario_id or 1

    if dados.principal:
        db.execute(
            update(Veiculo)
            .where(
                Veiculo.usuario_id == user_id,
                Veiculo.ativo.is_(True),
            )
            .values(principal=False)
        )

    novo_veiculo = Veiculo(
        usuario_id=user_id,
        marca=dados.marca,
        modelo=dados.modelo,
        versao=dados.versao,
        capacidade_bateria_kwh=dados.capacidade_bateria_kwh,
        tipo_conector=dados.tipo_conector,
        conector_secundario=dados.conector_secundario,
        principal=dados.principal,
        soc_atual=dados.soc_atual,
    )

    db.add(novo_veiculo)
    db.commit()
    db.refresh(novo_veiculo)

    return novo_veiculo


@router.put(
    "/{veiculo_id}",
    response_model=VeiculoResponse,
)
def atualizar_veiculo(
    veiculo_id: int,
    dados: VeiculoUpdate,
    db: Session = Depends(get_db),
):
    veiculo = db.scalar(
        select(Veiculo).where(
            Veiculo.id == veiculo_id,
            Veiculo.ativo.is_(True),
        )
    )

    if not veiculo:
        raise HTTPException(
            status_code=404,
            detail="Veículo não encontrado.",
        )

    dados_atualizacao = dados.model_dump(
        exclude_unset=True
    )

    if dados_atualizacao.get("principal") is True:
        db.execute(
            update(Veiculo)
            .where(
                Veiculo.usuario_id == veiculo.usuario_id,
                Veiculo.id != veiculo.id,
                Veiculo.ativo.is_(True),
            )
            .values(principal=False)
        )

    for campo, valor in dados_atualizacao.items():
        setattr(
            veiculo,
            campo,
            valor,
        )

    db.commit()
    db.refresh(veiculo)

    return veiculo


@router.delete(
    "/{veiculo_id}",
    status_code=status.HTTP_200_OK,
)
def deletar_veiculo(
    veiculo_id: int,
    db: Session = Depends(get_db),
):
    veiculo = db.scalar(
        select(Veiculo).where(
            Veiculo.id == veiculo_id,
            Veiculo.ativo.is_(True),
        )
    )

    if not veiculo:
        raise HTTPException(
            status_code=404,
            detail="Veículo não encontrado.",
        )

    veiculo.ativo = False

    db.commit()

    return {
        "mensagem": "Veículo removido com sucesso."
    }


@router.patch(
    "/{veiculo_id}/principal",
    response_model=VeiculoResponse,
)
def definir_veiculo_principal(
    veiculo_id: int,
    db: Session = Depends(get_db),
):
    veiculo = db.scalar(
        select(Veiculo).where(
            Veiculo.id == veiculo_id,
            Veiculo.ativo.is_(True),
        )
    )

    if not veiculo:
        raise HTTPException(
            status_code=404,
            detail="Veículo não encontrado.",
        )

    db.execute(
        update(Veiculo)
        .where(
            Veiculo.usuario_id == veiculo.usuario_id,
            Veiculo.id != veiculo.id,
            Veiculo.ativo.is_(True),
        )
        .values(principal=False)
    )

    veiculo.principal = True

    db.commit()
    db.refresh(veiculo)

    return veiculo