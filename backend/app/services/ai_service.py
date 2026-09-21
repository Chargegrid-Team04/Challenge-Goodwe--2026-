import os
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover - dependency may not be installed yet
    genai = None
    types = None


DEFAULT_CHARGING_CONTEXT = """
Contexto de infraestrutura GoodWe:
- Rede de infraestrutura de carregamento elétrico posicionada para uso urbano e rodoviário.
- A plataforma GoodWe oferece estações inteligentes com gestão de ocupação, preços dinâmicos e suporte a diferentes tipos de veículos elétricos.
- Inversores e carregadores da linha GoodWe são projetados para operação estável, monitoramento remoto e otimização de energia.
- Recomendações devem priorizar segurança, disponibilidade, custos operacionais e experiência do usuário.
- Quando os dados do banco não estiverem disponíveis, assumir operação genérica e segura.
"""


def get_charging_stations_context(db: Session) -> str:
    """Return DB station data when available, otherwise fall back to a generic GoodWe context."""
    if db is None:
        return DEFAULT_CHARGING_CONTEXT

    try:
        result = db.execute(
            text(
                "SELECT nome, endereco, preco_base_kwh "
                "FROM estacoes WHERE ativa = true ORDER BY id LIMIT 20"
            )
        )
        rows = result.mappings().all()

        if not rows:
            return DEFAULT_CHARGING_CONTEXT

        lines = [
            "Contexto de estações de recarga disponíveis:",
        ]
        for row in rows:
            name = row.get("nome", "Estação")
            address = row.get("endereco", "Endereço não informado")
            price = row.get("preco_base_kwh", "N/D")
            lines.append(f"- {name}: {address} | preço base: {price} €/kWh")
        return "\n".join(lines)
    except Exception:
        return DEFAULT_CHARGING_CONTEXT


class AIService:
    """Service wrapper for the Google Gemini / GenAI API."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3.6-flash"):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")

        if genai is None:
            raise ImportError(
                "The 'google-genai' package is not installed. Install it with: pip install google-genai"
            )

        self.client = genai.Client(api_key=self.api_key)

    def generate_response(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """Generate a text response for a given user prompt/context."""
        try:
            request_config = None
            if types is not None:
                request_config = types.GenerateContentConfig(
                    temperature=temperature,
                    system_instruction=system_prompt,
                )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=request_config,
            )

            if hasattr(response, "text") and response.text:
                return response.text

            if hasattr(response, "candidates") and response.candidates:
                first_candidate = response.candidates[0]
                content = getattr(first_candidate, "content", None)
                if content is not None and hasattr(content, "parts"):
                    parts_text = []
                    for part in content.parts:
                        if hasattr(part, "text") and part.text:
                            parts_text.append(part.text)
                    if parts_text:
                        return "".join(parts_text)

            return str(response)
        except Exception as exc:
            raise RuntimeError(f"Failed to generate Gemini response: {exc}") from exc


def generate_charging_recommendation(
    user_context: str,
    *,
    system_prompt: Optional[str] = None,
) -> str:
    """Convenience function for EV charging-related recommendations."""
    service = AIService()
    default_system_prompt = (
        "You are a helpful assistant for electric vehicle charging infrastructure. "
        "Provide clear, practical recommendations based on the user's context and station data."
    )
    return service.generate_response(
        user_context,
        system_prompt=system_prompt or default_system_prompt,
        temperature=0.4,
    )
