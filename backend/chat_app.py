import inspect
import os
import time
from typing import Any, Iterator

import gradio as gr
from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.services.ai_service import get_charging_stations_context
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


theme = gr.themes.Soft(
    primary_hue=gr.themes.colors.green,
    secondary_hue=gr.themes.colors.blue,
    neutral_hue=gr.themes.colors.gray,
    radius_size="md",
    font=gr.themes.GoogleFont("Inter"),
)

with gr.Blocks() as demo:
    gr.HTML("""
    <style>
        :root {
            color-scheme: light !important;
            --goodwe-primary: #0b2b20;
            --goodwe-primary-soft: #163c30;
            --goodwe-secondary: #00b4d8;
            --goodwe-secondary-hover: #015f70;
            --goodwe-bg: #f1f8f5;
            --goodwe-panel: #ffffff;
            --goodwe-panel-soft: #f4f9f7;
            --goodwe-border: rgba(11, 43, 32, 0.12);
            --goodwe-text: #0f172a;
            --goodwe-muted: #526074;
            --body-background-fill: #f1f8f5;
            --body-text-color: #0f172a;
            --background-fill-primary: #f1f8f5;
            --background-fill-secondary: #ffffff;
            --panel-background-fill: #ffffff;
            --block-background-fill: #ffffff;
            --input-background-fill: #ffffff;
            --input-text-fill: #0f172a;
        }

        html, body {
            color-scheme: light !important;
            background: #f1f8f5 !important;
            color: var(--goodwe-text) !important;
        }

        * { box-sizing: border-box; }

        .gradio-container {
            color-scheme: light !important;
            background: #f1f8f5 !important;
            width: 100% !important;
            max-width: 820px !important;
            min-height: 100dvh !important;
            margin: 0 auto !important;
            padding: max(0.75rem, env(safe-area-inset-top)) 1rem max(3.5rem, calc(env(safe-area-inset-bottom) + 3rem)) !important;
        }

        .gradio-container .wrap {
            background: transparent !important;
            width: 100% !important;
            max-width: 100% !important;
        }

        .gradio-container main,
        .gradio-container .column,
        .gradio-container .block,
        .gradio-container .prose {
            width: 100% !important;
            max-width: 100% !important;
            min-width: 0 !important;
        }

        footer {
            display: none !important;
        }

        #goodwe-header {
            display: flex;
            align-items: center;
            gap: 0.9rem;
            width: 100%;
            min-width: 0;
            margin: 0 auto 0.75rem;
            padding: 0.85rem 1rem;
            border: 1px solid rgba(0, 180, 216, 0.22);
            border-radius: 18px;
            background: linear-gradient(112deg, #0b2b20 0%, #145543 58%, #087f9a 100%);
            box-shadow: 0 10px 24px rgba(11, 43, 32, 0.12);
            text-align: left;
            overflow: hidden;
        }

        #goodwe-header .brand-mark {
            display: grid;
            place-items: center;
            flex: 0 0 44px;
            width: 44px;
            height: 44px;
            border: 1px solid rgba(255, 255, 255, 0.28);
            border-radius: 14px;
            background: rgba(255, 255, 255, 0.12);
            color: #ffffff;
            font-size: 0.9rem;
            font-weight: 800;
        }

        #goodwe-header .header-copy {
            flex: 1 1 auto;
            min-width: 0;
            overflow-wrap: normal;
            word-break: normal;
        }

        #goodwe-header h2 {
            margin: 0;
            color: #ffffff;
            font-size: 1.2rem;
            font-weight: 750;
        }

        #goodwe-header .eyebrow {
            display: block;
            margin-bottom: 0.1rem;
            color: #a6e8ed;
            font-size: 0.66rem;
            font-weight: 700;
            letter-spacing: 0.08em;
        }

        #goodwe-header .subtitle {
            display: block;
            margin-top: 0.15rem;
            color: rgba(255,255,255,0.78);
            font-size: 0.78rem;
            line-height: 1.35;
        }

        #amper-navbar {
            position: fixed;
            z-index: 1001;
            right: 0;
            bottom: 0;
            left: 0;
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 1rem;
            width: 100%;
            height: calc(70px + env(safe-area-inset-bottom));
            padding: 8px max(16px, calc((100vw - 820px) / 2 + 24px)) max(8px, env(safe-area-inset-bottom));
            border-top: 1px solid #d3dbe5;
            background: #ffffff;
            box-shadow: 0 -8px 24px rgba(11, 43, 32, 0.07);
        }

        #amper-navbar a {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 4px;
            min-width: 0;
            border-radius: 12px;
            color: #475569;
            font-family: Inter, system-ui, -apple-system, sans-serif !important;
            text-decoration: none;
            transition: color 150ms ease, background-color 150ms ease, transform 150ms ease;
        }

        #amper-navbar svg {
            width: 24px;
            height: 24px;
            fill: none;
            color: #475569 !important;
            stroke: #475569 !important;
            stroke-width: 2;
            stroke-linecap: round;
            stroke-linejoin: round;
            transform: translateY(-1px);
        }

        #amper-navbar span {
            overflow: hidden;
            max-width: 100%;
            color: inherit;
            font-size: 11px;
            font-weight: 500;
            line-height: 24px;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        #amper-navbar a:hover,
        #amper-navbar a:focus-visible {
            background: #e6f6f8;
            color: #00809a;
        }

        #amper-navbar a:hover svg,
        #amper-navbar a:focus-visible svg {
            color: #00b4d8 !important;
            stroke: #00b4d8 !important;
        }

        #amper-navbar a[aria-current="page"] {
            color: #00b4d8;
        }

        #amper-navbar a[aria-current="page"] svg {
            color: #00b4d8 !important;
            stroke: #00b4d8 !important;
            stroke-width: 2.5;
            transform: translateY(-1px) scale(1.08);
        }

        #amper-navbar a[aria-current="page"] span {
            font-weight: 700;
        }

        #amper-navbar a:active {
            transform: scale(0.94);
        }

        #amper-navbar a:focus-visible {
            outline: 2px solid #00b4d8;
            outline-offset: 1px;
        }

        #goodwe-chatbot {
            background: var(--goodwe-panel) !important;
            border: 1px solid rgba(0, 180, 216, 0.24) !important;
            border-radius: 18px !important;
            height: clamp(360px, calc(100dvh - 400px), 680px) !important;
            min-height: 360px !important;
            box-shadow: 0 12px 28px rgba(11, 43, 32, 0.07) !important;
            color: var(--goodwe-text) !important;
        }

        #goodwe-chatbot * {
            color: #111827 !important;
        }

        #goodwe-chatbot button,
        #goodwe-chatbot [role="button"] {
            border: 1px solid rgba(0, 128, 154, 0.24) !important;
            border-radius: 10px !important;
            background: #e6f6f8 !important;
            box-shadow: none !important;
            color: #07586a !important;
            transition: background-color 150ms ease, color 150ms ease, border-color 150ms ease;
        }

        #goodwe-chatbot button svg,
        #goodwe-chatbot [role="button"] svg,
        #goodwe-chatbot button svg *,
        #goodwe-chatbot [role="button"] svg * {
            color: currentColor !important;
            stroke: currentColor !important;
        }

        #goodwe-chatbot button:hover,
        #goodwe-chatbot [role="button"]:hover {
            border-color: #087f9a !important;
            background: #087f9a !important;
            color: #ffffff !important;
        }

        #goodwe-chatbot button:focus-visible,
        #goodwe-chatbot [role="button"]:focus-visible {
            outline: 3px solid rgba(0, 180, 216, 0.38) !important;
            outline-offset: 2px;
        }

        #goodwe-chatbot .bubble-wrap,
        #goodwe-chatbot .wrapper,
        #goodwe-chatbot .placeholder-content,
        #goodwe-chatbot .placeholder {
            background: #ffffff !important;
            color: var(--goodwe-text) !important;
        }

        #goodwe-chatbot [data-testid="block-label"] {
            background: #e7f4f1 !important;
            border-color: rgba(11, 43, 32, 0.12) !important;
            color: var(--goodwe-primary) !important;
        }

        #goodwe-chatbot .placeholder p {
            color: #111827 !important;
        }

        #goodwe-composer {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            align-items: stretch !important;
            width: 100% !important;
            min-width: 0 !important;
            gap: 0.6rem !important;
            margin-top: 0.65rem;
            padding: 0.5rem;
            border: 1px solid rgba(0, 180, 216, 0.2);
            border-radius: 17px;
            background: var(--goodwe-panel) !important;
            box-shadow: 0 8px 20px rgba(11, 43, 32, 0.06);
        }

        #goodwe-composer #goodwe-textbox {
            flex: 1 1 auto !important;
            min-width: 0 !important;
            width: auto !important;
            margin: 0 !important;
            min-height: 54px !important;
            border: 0 !important;
            border-radius: 12px !important;
            color: var(--goodwe-text) !important;
            background: #ffffff !important;
            box-shadow: none !important;
        }

        #goodwe-composer [data-testid="block-label"] {
            display: none !important;
        }

        #goodwe-textbox textarea,
        #goodwe-textbox input {
            background: transparent !important;
            color: var(--goodwe-text) !important;
            font-size: 1rem !important;
        }

        #goodwe-textbox textarea::placeholder {
            color: rgba(82, 96, 116, 0.8) !important;
        }

        .gradio-container button,
        .gradio-container .button-primary,
        .gradio-container .primary {
            border: none !important;
            border-radius: 12px !important;
            font-weight: 700 !important;
            background: linear-gradient(135deg, var(--goodwe-primary) 0%, var(--goodwe-primary-soft) 100%) !important;
            color: #ffffff !important;
            box-shadow: 0 10px 20px rgba(11, 43, 32, 0.15);
        }

        .gradio-container button:hover,
        .gradio-container .button-primary:hover,
        .gradio-container .primary:hover {
            background: linear-gradient(135deg, var(--goodwe-primary-soft) 0%, var(--goodwe-primary) 100%) !important;
        }

        #goodwe-composer #goodwe-send-button {
            flex: 0 0 84px !important;
            width: 84px !important;
            min-width: 84px !important;
            min-height: 54px !important;
            margin: 0 !important;
            border-radius: 13px !important;
            background: linear-gradient(110deg, var(--goodwe-primary) 0%, #087f9a 100%) !important;
        }

        .gradio-container .gr-markdown,
        .gradio-container .gradio-html,
        .gradio-container .label,
        .gradio-container .textbox,
        .gradio-container .chatbot {
            color: var(--goodwe-text) !important;
        }

        .gradio-container .bubble {
            border-radius: 18px !important;
        }

        #goodwe-chatbot .message.user {
            background: linear-gradient(135deg, #e6f7f1, #d7f0e8) !important;
            color: var(--goodwe-text) !important;
        }

        #goodwe-chatbot .message.bot {
            background: #eaf8fb !important;
            border: 1px solid rgba(0, 180, 216, 0.13) !important;
            color: var(--goodwe-text) !important;
        }

        @media (max-width: 600px) {
            .main.fillable {
                padding: 0.6rem !important; 
            }

            .gradio-container {
                padding-left: 0.7rem !important;
                padding-right: 0.7rem !important;
            }

            #goodwe-header {
                gap: 0.7rem;
                margin-bottom: 0.6rem;
                padding: 0.75rem 0.8rem;
                border-radius: 16px;
            }

            #goodwe-header .brand-mark {
                flex-basis: 40px;
                width: 40px;
                height: 40px;
                border-radius: 12px;
            }

            #goodwe-header h2 { font-size: 1.08rem; }
            #goodwe-header .subtitle { font-size: 0.74rem; }

            #goodwe-chatbot {
                height: clamp(280px, calc(100dvh - 400px), 520px) !important;
                min-height: 280px !important;
                border-radius: 16px !important;
            }

            #goodwe-composer {
                gap: 0.4rem !important;
                padding: 0.4rem;
                border-radius: 15px;
            }

            #goodwe-composer #goodwe-send-button {
                flex-basis: 72px !important;
                width: 72px !important;
                min-width: 72px !important;
                min-height: 50px !important;
                padding: 0.5rem !important;
                font-size: 0.88rem !important;
            }
        }
    </style>
    """)

    gr.HTML("""
        <nav id="amper-navbar" aria-label="Navegação principal">
            <a href="/mapa" aria-label="Mapa">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/></svg>
                <span>Mapa</span>
            </a>
            <a href="/ia/" aria-label="Ampia, assistente de IA" aria-current="page">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg>
                <span>Ampia</span>
            </a>
            <a href="/historicos" aria-label="Histórico">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/></svg>
                <span>Histórico</span>
            </a>
            <a href="/perfil" aria-label="Perfil">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                <span>Perfil</span>
            </a>
        </nav>
    """)

    gr.Markdown(
        """
        <div id="goodwe-header">
            <div class="brand-mark" aria-hidden="true">AM</div>
            <div class="header-copy">
                <span class="eyebrow">Amper · MOBILIDADE ELÉTRICA</span>
                <h2>Assistente Amper</h2>
                <span class="subtitle">Suporte para recarga e mobilidade elétrica</span>
            </div>
        </div>
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

    chatbot = gr.Chatbot(**chatbot_kwargs, elem_id="goodwe-chatbot")

    with gr.Row(elem_id="goodwe-composer"):
        textbox = gr.Textbox(
            placeholder="Digite sua mensagem...",
            lines=1,
            max_lines=4,
            show_label=False,
            elem_id="goodwe-textbox",
            scale=1,
            min_width=0,
        )
        button = gr.Button(
            "Enviar",
            variant="primary",
            elem_id="goodwe-send-button",
            elem_classes=["goodwe-primary"],
            scale=0,
            min_width=84,
        )

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


if __name__ == "__main__":
    launch_kwargs = {
        "server_name": "0.0.0.0",
        "server_port": 8000,
        "share": False,
        "debug": False,
    }
    demo.launch(**launch_kwargs)
