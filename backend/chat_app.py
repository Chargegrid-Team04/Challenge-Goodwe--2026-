import inspect
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterator

import gradio as gr
from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.services.ai_service import get_charging_stations_context
from app.services.charging_prediction_service import predict_charging
from app.services.context_service import format_context, retrieve_document_context
from app.services.web_search_service import format_web_context, search_web

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

MODEL_NAME = "gemini-3.6-flash"
MAX_OUTPUT_TOKENS = 4096
MAX_API_RETRIES = 2
DEFAULT_SYSTEM_PROMPT = (
    "Você é um assistente útil para a plataforma GoodWe. "
    "Responda de forma clara, prática e segura, com foco em infraestrutura de recarga, mobilidade elétrica e suporte ao usuário."
)


def _build_system_context() -> str:
    """Retrieve local RAG context and optionally public web context."""
    return format_context([])


def _build_retrieved_context(query: str) -> str:
    local_sources = retrieve_document_context(query)
    context = format_context(local_sources)

    if os.getenv("RAG_ENABLE_DATABASE", "false").lower() == "true":
        try:
            from app.db.session import SessionLocal

            with SessionLocal() as db:
                database_context = get_charging_stations_context(db)
            context = f"{context}\n\n{database_context}"
        except Exception:
            # Database context is optional; local documents and the fallback remain available.
            pass

    if os.getenv("RAG_ENABLE_WEB_SEARCH", "false").lower() == "true":
        web_context = format_web_context(search_web(query))
        if web_context:
            context = f"{context}\n\n{web_context}"

    return context


def _load_station_choices() -> list[tuple[str, int]]:
    """Load station labels for the UI while keeping database IDs internal."""
    try:
        from app.db.session import SessionLocal
        from app.models.estacao import Estacao

        with SessionLocal() as db:
            stations = db.query(Estacao).filter(Estacao.ativa.is_(True)).order_by(Estacao.nome).all()
            return [
                (f"{station.nome} - {station.endereco}", station.id)
                for station in stations
            ]
    except Exception:
        return []


def _prepare_gemini_history(history: list[dict[str, Any]]) -> list[types.Content]:
    """Convert Gradio messages into Gemini-compatible content history."""
    gemini_history: list[types.Content] = []

    for message in history or []:
        role = str(message.get("role", "user")).lower()
        content = message.get("content", "")
        if not content:
            continue

        gemini_role = "user" if role == "user" else "model"
        gemini_history.append(
            types.Content(
                role=gemini_role,
                parts=[types.Part.from_text(text=str(content))],
            )
        )

    return gemini_history


def _extract_stream_text(chunk: Any) -> str:
    """Extract incremental text from Gemini stream chunks."""
    text = getattr(chunk, "text", None)
    if text:
        return text

    candidates = getattr(chunk, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", []) or []:
            value = getattr(part, "text", None)
            if value:
                return value

    return ""


def _normalize_response_text(text: str) -> str:
    """Convert escaped line breaks returned as text into real line breaks."""
    return text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")


def _is_temporary_api_error(error: Exception) -> bool:
    """Identify provider errors that are usually safe to retry."""
    error_text = str(error).upper()
    return "503" in error_text or "UNAVAILABLE" in error_text or "429" in error_text or "RESOURCE_EXHAUSTED" in error_text


def _generate_gemini_response(
    history: list[dict[str, Any]],
    user_message: str,
) -> Iterator[str]:
    """Generate a streaming response from Gemini using the current chat history."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY não está definida no ambiente.")

    client = genai.Client(api_key=api_key)

    prepared_history = _prepare_gemini_history(history)
    context = _build_retrieved_context(user_message)
    latest_prompt = (
        f"{context}\n\n"
        f"Pergunta do usuário:\n{user_message}"
    )

    contents = prepared_history + [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=latest_prompt)],
        )
    ]

    request_config = types.GenerateContentConfig(
        system_instruction=DEFAULT_SYSTEM_PROMPT,
        temperature=0.7,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    for attempt in range(MAX_API_RETRIES + 1):
        emitted_text = False
        try:
            response = client.models.generate_content_stream(
                model=MODEL_NAME,
                contents=contents,
                config=request_config,
            )

            for chunk in response:
                text = _extract_stream_text(chunk)
                if text:
                    emitted_text = True
                    yield text
            return
        except Exception as exc:
            if not _is_temporary_api_error(exc) or emitted_text or attempt >= MAX_API_RETRIES:
                raise
            time.sleep(2**attempt)


def stream_ai_response(
    history: list[dict[str, Any]] | None,
    message: str,
) -> Iterator[tuple[list[dict[str, Any]], str]]:
    """Streaming chat response compatible with Gradio Chatbot(type='messages')."""
    history = history or []
    message = (message or "").strip()

    if not message:
        yield history, ""
        return

    user_message = {"role": "user", "content": message}
    current_history = history + [user_message]
    assistant_buffer = {"role": "assistant", "content": ""}
    yield current_history + [assistant_buffer], ""

    try:
        full_text = ""
        for chunk in _generate_gemini_response(history, message):
            full_text = _normalize_response_text(full_text + chunk)
            updated_history = current_history + [{"role": "assistant", "content": full_text}]
            yield updated_history, ""
    except ValueError as exc:
        error_message = (
            "Não foi possível processar a sua mensagem porque a chave da API Gemini não está configurada. "
            f"Detalhe: {exc}"
        )
        yield current_history + [{"role": "assistant", "content": error_message}], ""
        return
    except Exception as exc:  # pragma: no cover - defensive fallback for API failures
        if _is_temporary_api_error(exc):
            error_message = (
                "A IA está temporariamente sobrecarregada. Aguarde alguns segundos e tente novamente."
            )
            yield current_history + [{"role": "assistant", "content": error_message}], ""
            return
        error_message = (
            "Ocorreu um erro ao conectar com a IA. Verifique sua conexão e tente novamente. "
            f"Detalhe: {exc}"
        )
        yield current_history + [{"role": "assistant", "content": error_message}], ""
        return


def predict_from_gradio(
    station_id: int | None,
    source: str,
    current_soc: float,
    target_soc: float,
    battery_capacity: float,
) -> Iterator[tuple[str, Any]]:
    """Run the deterministic prediction using the existing station and vehicle data."""
    yield "", gr.Button(value="Calculando...", interactive=False)

    try:
        from sqlalchemy import select

        from app.db.session import SessionLocal
        from app.models.estacao import Estacao
        from app.models.recarga import Recarga

        with SessionLocal() as db:
            if station_id is None:
                yield "**Erro:** selecione uma estação.", gr.Button(value="Calcular previsão", interactive=True)
                return

            station = db.get(Estacao, int(station_id))
            if station is None:
                yield "**Erro:** estação não encontrada.", gr.Button(value="Calcular previsão", interactive=True)
                return

            connector = next(
                (
                    item for item in station.conectores
                    if item.status.upper() == "DISPONIVEL"
                ),
                None,
            )
            if connector is None:
                yield "**Erro:** nenhum conector disponível nessa estação.", gr.Button(value="Calcular previsão", interactive=True)
                return

            station_capacity = sum(
                (Decimal(item.potencia_kw) for item in station.conectores),
                Decimal("0"),
            )
            if station_capacity <= 0:
                yield "**Erro:** a estação não possui capacidade cadastrada.", gr.Button(value="Calcular previsão", interactive=True)
                return

            active_cars = len(db.scalars(
                select(Recarga).where(
                    Recarga.estacao_id == station.id,
                    Recarga.status == "CARREGANDO",
                )
            ).all())

            prediction = predict_charging(
                battery_capacity_kwh=Decimal(str(battery_capacity)),
                current_soc_percent=Decimal(str(current_soc)),
                target_soc_percent=Decimal(str(target_soc)),
                requested_source=source,
                connector_power_kw=connector.potencia_kw,
                station_capacity_kw=station_capacity,
                base_price_per_kwh=station.preco_base_kwh,
                active_cars=active_cars,
                current_at=datetime.now(timezone.utc),
                solar_available_kw=None,
            )

        solar_note = "estimada (sem telemetria solar cadastrada)" if prediction.source_is_estimated else "informada pela estação"
        result = (
            f"### Sugestão: {prediction.source}\n\n"
            f"{prediction.suggestion}\n\n"
            f"- Energia necessária: **{prediction.energy_required_kwh} kWh**\n"
            f"- Potência aplicada: **{prediction.charging_power_kw} kW**\n"
            f"- Tempo estimado: **{prediction.estimated_minutes} minutos**\n"
            f"- Preço estimado: **R$ {prediction.price_per_kwh}/kWh**\n"
            f"- Custo estimado: **R$ {prediction.estimated_cost}**\n"
            f"- Carros carregando na estação: **{prediction.active_cars}**\n"
            f"- Energia solar: **{solar_note}**\n\n"
            "> Valores são estimativas e podem variar com telemetria, temperatura, veículo e rede elétrica."
        )
        yield result, gr.Button(value="Calcular previsão", interactive=True)
    except Exception as exc:
        yield f"**Não foi possível calcular a previsão:** {exc}", gr.Button(value="Calcular previsão", interactive=True)
with gr.Blocks() as demo:
    gr.Markdown(
        """
        <div style="text-align:center; margin-bottom:0.75rem;"><h2>GoodWe IA Chat</h2></div>
        <div style="text-align:center; color:#6b7280; margin-bottom:1rem;">Assistente textual para suporte de mobilidade elétrica e recarga.</div>
        """
    )

    chatbot_kwargs: dict[str, Any] = {}
    chatbot_signature = inspect.signature(gr.Chatbot.__init__)
    for key, value in {
        "type": "messages",
        "height": 560,
        "bubble_full_width": False,
        "placeholder": "Pergunte algo sobre recarga, mobilidade elétrica ou operação da infraestrutura...",
        "show_copy_button": True,
    }.items():
        if key in chatbot_signature.parameters:
            chatbot_kwargs[key] = value

    chatbot = gr.Chatbot(**chatbot_kwargs)

    textbox_kwargs: dict[str, Any] = {
        "placeholder": "Digite sua mensagem...",
        "lines": 1,
        "max_lines": 4,
    }
    textbox_signature = inspect.signature(gr.Textbox.__init__)
    if "show_submit_button" in textbox_signature.parameters:
        textbox_kwargs["show_submit_button"] = True
    if "submit_btn" in textbox_signature.parameters:
        textbox_kwargs["submit_btn"] = "Enviar"

    textbox = gr.Textbox(**textbox_kwargs)

    button = gr.Button("Enviar", variant="primary")

    def submit_message(history, message):
        for item in stream_ai_response(history, message):
            yield item

    textbox.submit(
        submit_message,
        inputs=[chatbot, textbox],
        outputs=[chatbot, textbox],
        queue=True,
    )

    button.click(
        submit_message,
        inputs=[chatbot, textbox],
        outputs=[chatbot, textbox],
        queue=True,
    )

    gr.Markdown("## Previsão de recarga")
    gr.Markdown(
        "Selecione a estação e informe os dados atuais do carro. A capacidade elétrica da estação "
        "é calculada pelos conectores cadastrados; os resultados são estimativas."
    )
    station_choices = _load_station_choices()
    with gr.Row():
        station_input = gr.Dropdown(
            choices=station_choices,
            value=station_choices[0][1] if station_choices else None,
            type="value",
            label="Estação (nome e endereço)",
            info="A capacidade é calculada automaticamente pelos conectores da estação.",
        )
        source_input = gr.Dropdown(
            ["POSTO", "SOLAR", "HIBRIDO"],
            value="HIBRIDO",
            label="Fonte de energia",
        )
    with gr.Row():
        current_soc_input = gr.Number(label="Bateria atual (%)", value=20, minimum=0, maximum=100)
        target_soc_input = gr.Number(label="Bateria desejada (%)", value=80, minimum=1, maximum=100)
        battery_capacity_input = gr.Number(
            label="Capacidade da bateria (kWh)",
            value=60,
            minimum=1,
            info="Use a capacidade do carro; ela poderá vir do veículo da conta futuramente.",
        )
    prediction_button = gr.Button("Calcular previsão", variant="primary")
    prediction_output = gr.Markdown()

    prediction_button.click(
        predict_from_gradio,
        inputs=[
            station_input,
            source_input,
            current_soc_input,
            target_soc_input,
            battery_capacity_input,
        ],
        outputs=[prediction_output, prediction_button],
    )


if __name__ == "__main__":
    launch_kwargs = {
        "server_name": "0.0.0.0",
        "server_port": 7860,
        "share": False,
        "debug": False,
    }
    signature = inspect.signature(gr.Blocks.launch)
    if "css" in signature.parameters:
        launch_kwargs["css"] = """
            .gradio-container { max-width: 1100px !important; }
            .chat-wrapper { padding: 1rem; }
        """
    demo.launch(**launch_kwargs)
