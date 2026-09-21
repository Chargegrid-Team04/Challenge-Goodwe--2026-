from pathlib import Path

from app.services.context_service import format_context, retrieve_document_context


def test_retrieve_document_context_returns_relevant_local_text(tmp_path: Path, monkeypatch):
    documents = tmp_path / "documents"
    documents.mkdir()
    (documents / "manual.md").write_text(
        "O carregador GoodWe suporta monitoramento remoto e gestão de potência.",
        encoding="utf-8",
    )
    monkeypatch.setenv("RAG_DOCUMENTS_DIR", str(documents))

    sources = retrieve_document_context("Como funciona o monitoramento do carregador?")

    assert len(sources) == 1
    assert "monitoramento remoto" in sources[0].content
    assert "manual.md" in format_context(sources)


def test_retrieve_document_context_ignores_unrelated_text(tmp_path: Path, monkeypatch):
    documents = tmp_path / "documents"
    documents.mkdir()
    (documents / "notes.txt").write_text("Receita de bolo de chocolate.", encoding="utf-8")
    monkeypatch.setenv("RAG_DOCUMENTS_DIR", str(documents))

    assert retrieve_document_context("status do carregador") == []
