import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ContextSource:
    title: str
    content: str
    origin: str


DEFAULT_CONTEXT = (
    "Contexto operacional GoodWe: infraestrutura de recarga elétrica, inversores e carregadores "
    "inteligentes. Priorize segurança, eficiência energética, disponibilidade e recomendações verificáveis."
)


def _chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> Iterable[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return

    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        yield normalized[start:end]
        if end == len(normalized):
            break
        start = end - overlap


def _read_document(path: Path) -> str:
    if path.suffix.lower() in {".txt", ".md", ".csv", ".json"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            return ""
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    return ""


def _document_sources(documents_dir: Path) -> list[ContextSource]:
    if not documents_dir.exists():
        return []

    sources: list[ContextSource] = []
    for path in documents_dir.rglob("*"):
        if not path.is_file() or path.name.startswith("."):
            continue
        text = _read_document(path)
        for index, chunk in enumerate(_chunk_text(text)):
            sources.append(
                ContextSource(
                    title=f"{path.name} (trecho {index + 1})",
                    content=chunk,
                    origin=str(path),
                )
            )
    return sources


def retrieve_document_context(query: str, *, limit: int = 4) -> list[ContextSource]:
    """Retrieve relevant local document chunks using a private, local keyword ranking."""
    documents_dir = Path(
        os.getenv(
            "RAG_DOCUMENTS_DIR",
            Path(__file__).resolve().parents[2] / "data" / "documents",
        )
    )
    query_terms = set(re.findall(r"\w+", query.lower()))
    ranked: list[tuple[int, ContextSource]] = []

    for source in _document_sources(documents_dir):
        source_terms = set(re.findall(r"\w+", source.content.lower()))
        score = len(query_terms & source_terms)
        if score > 0:
            ranked.append((score, source))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [source for _, source in ranked[:limit]]


def format_context(sources: list[ContextSource]) -> str:
    if not sources:
        return DEFAULT_CONTEXT

    sections = [DEFAULT_CONTEXT, "\nFontes locais relevantes:"]
    for source in sources:
        sections.append(f"[{source.title}]\n{source.content}")
    return "\n\n".join(sections)
