import os
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import json


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    @property
    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


def _google_search(query: str, limit: int) -> list[dict[str, str]]:
    api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
    search_engine_id = os.getenv("GOOGLE_SEARCH_CX")
    if not api_key or not search_engine_id:
        return []

    url = (
        "https://www.googleapis.com/customsearch/v1?key="
        f"{quote_plus(api_key)}&cx={quote_plus(search_engine_id)}&q={quote_plus(query)}&num={limit}"
    )
    request = Request(url, headers={"User-Agent": "GoodWe-RAG/1.0"})
    with urlopen(request, timeout=8) as response:
        payload = json.load(response)

    return [
        {
            "title": item.get("title", "Resultado web"),
            "url": item.get("link", ""),
            "snippet": item.get("snippet", ""),
        }
        for item in payload.get("items", [])[:limit]
    ]


def _duckduckgo_search(query: str, limit: int) -> list[dict[str, str]]:
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    request = Request(url, headers={"User-Agent": "GoodWe-RAG/1.0"})
    with urlopen(request, timeout=8) as response:
        html = response.read().decode("utf-8", errors="ignore")

    parser = _TextParser()
    parser.feed(html)
    text = parser.text
    if not text:
        return []
    return [{"title": "DuckDuckGo", "url": url, "snippet": text[:1500]}]


def search_web(query: str, *, limit: int = 3) -> list[dict[str, str]]:
    """Search Google Custom Search when configured, otherwise use DuckDuckGo."""
    try:
        results = _google_search(query, limit)
        if results:
            return results
        return _duckduckgo_search(query, limit)
    except Exception:
        return []


def format_web_context(results: list[dict[str, Any]]) -> str:
    if not results:
        return ""
    lines = ["Fontes web recentes; confirme dados críticos antes de agir:"]
    for result in results:
        lines.append(
            f"- {result.get('title', 'Resultado')}: {result.get('snippet', '')} "
            f"(URL: {result.get('url', '')})"
        )
    return "\n".join(lines)
