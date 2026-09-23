from pydantic import BaseModel, Field


class AIRecommendationRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Prompt or context sent to the AI assistant.")
    system_prompt: str | None = Field(
        default=None,
        description="Optional system instruction for the generation.",
    )


class AIRecommendationResponse(BaseModel):
    recommendation: str = Field(..., description="Generated recommendation text from the AI model.")
