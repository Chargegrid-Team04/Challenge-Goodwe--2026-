from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.ai import AIRecommendationRequest, AIRecommendationResponse
from app.services.ai_service import generate_charging_recommendation, get_charging_stations_context

router = APIRouter()


@router.post(
    "/recommendation",
    response_model=AIRecommendationResponse,
    status_code=status.HTTP_200_OK,
)
async def create_recommendation(payload: AIRecommendationRequest):
    try:
        recommendation = generate_charging_recommendation(
            payload.prompt,
            system_prompt=payload.system_prompt,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI configuration error: {exc}",
        ) from exc
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI SDK unavailable: {exc}",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI generation failed: {exc}",
        ) from exc
    except Exception as exc:  # pragma: no cover - fallback for unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while generating recommendation.",
        ) from exc

    return AIRecommendationResponse(recommendation=recommendation)


@router.post(
    "/charging-advice",
    response_model=AIRecommendationResponse,
    status_code=status.HTTP_200_OK,
)
async def charging_advice(
    payload: AIRecommendationRequest,
    db: Session = Depends(get_db),
):
    try:
        charging_context = get_charging_stations_context(db)
        prompt = (
            f"Contexto do sistema:\n{charging_context}\n\n"
            f"Pergunta do usuário:\n{payload.prompt}\n"
        )

        recommendation = generate_charging_recommendation(
            prompt,
            system_prompt=(
                payload.system_prompt
                or "Você é um assistente especialista em infraestrutura de recarga de veículos elétricos e GoodWe. "
                "Responda com recomendações práticas, seguras e alinhadas ao contexto de estações e inversores."
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI configuration error: {exc}",
        ) from exc
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI SDK unavailable: {exc}",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI generation failed: {exc}",
        ) from exc
    except Exception as exc:  # pragma: no cover - fallback
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while generating charging advice.",
        ) from exc

    return AIRecommendationResponse(recommendation=recommendation)
