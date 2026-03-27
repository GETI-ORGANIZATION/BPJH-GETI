"""Tests for literature collection helpers in ``EvoScientist.tools.search``."""

import json
from pathlib import Path

from EvoScientist.tools.search import (
    _extract_claims_from_text,
    _load_jsonl,
    _upsert_evidence_record,
    collect_sources,
    crawl_site_articles,
    extract_claims,
    read_paper_source,
)
from tests.conftest import run_async


def test_collect_sources_writes_source_index(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    async def fake_search(query: str, max_results: int, topic: str):
        return {
            "results": [
                {
                    "title": "Vision-Language Survey",
                    "url": "https://example.com/vlm-survey",
                    "content": "A survey of multimodal methods.",
                },
                {
                    "title": "Agent Lab",
                    "url": "https://example.com/agent-lab.pdf",
                    "content": "An agent benchmark paper.",
                },
            ]
        }

    monkeypatch.setattr(
        "EvoScientist.tools.search._search_tavily_results",
        fake_search,
    )

    result = run_async(
        collect_sources.ainvoke(
            {
                "query": "multimodal agent",
                "seed_urls": ["https://seed.example.com/paper"],
                "max_results": 2,
            }
        )
    )

    index_path = tmp_path / "artifacts" / "lit_review" / "source_index.json"
    assert index_path.exists()
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["query"] == "multimodal agent"
    assert len(payload["sources"]) == 3
    assert payload["sources"][1]["source_type"] == "pdf"
    assert "Collected 3 source(s)" in result


def test_collect_sources_uses_seed_urls_without_tavily_key(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    result = run_async(
        collect_sources.ainvoke(
            {
                "query": "multimodal agent",
                "seed_urls": [
                    "https://seed.example.com/paper-a",
                    "https://seed.example.com/paper-b.pdf",
                ],
                "max_results": 2,
            }
        )
    )

    index_path = tmp_path / "artifacts" / "lit_review" / "source_index.json"
    assert index_path.exists()
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert len(payload["sources"]) == 2
    assert payload["sources"][1]["source_type"] == "pdf"
    assert "Collected 2 source(s)" in result
    assert "Tavily search skipped because TAVILY_API_KEY is not configured." in result


def test_crawl_site_articles_extracts_article_links(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    class _FakeResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self):
            return None

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, headers=None):
            html = """
            <html>
              <body>
                <a href="/abs/1234.5678">Paper A</a>
                <a href="/paper/agent-lab">Agent Lab</a>
                <a href="/about">About</a>
              </body>
            </html>
            """
            return _FakeResponse(html)

    monkeypatch.setattr("EvoScientist.tools.search.httpx.AsyncClient", lambda **kwargs: _FakeClient())

    result = run_async(
        crawl_site_articles.ainvoke(
            {
                "site_urls": ["https://example.com/papers"],
                "keywords": ["paper", "agent"],
                "max_articles_per_site": 5,
            }
        )
    )

    index_path = tmp_path / "artifacts" / "lit_review" / "site_crawl_index.json"
    assert index_path.exists()
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert len(payload["articles"]) == 2
    assert payload["articles"][0]["url"].startswith("https://example.com/")
    assert "discovered 2 article link(s)" in result


def test_crawl_site_articles_recurses_listing_pages(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    class _FakeResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self):
            return None

    pages = {
        "https://example.com/papers": """
            <html><body>
              <a href="/archive/page-2">Next Page</a>
            </body></html>
        """,
        "https://example.com/archive/page-2": """
            <html><body>
              <a href="/abs/9999.0001">Recursive Paper</a>
            </body></html>
        """,
    }

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, headers=None):
            return _FakeResponse(pages[url])

    monkeypatch.setattr("EvoScientist.tools.search.httpx.AsyncClient", lambda **kwargs: _FakeClient())

    run_async(
        crawl_site_articles.ainvoke(
            {
                "site_urls": ["https://example.com/papers"],
                "keywords": ["paper"],
                "max_articles_per_site": 5,
                "max_depth": 2,
                "max_pages_per_site": 5,
            }
        )
    )

    index_path = tmp_path / "artifacts" / "lit_review" / "site_crawl_index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["articles"][0]["url"] == "https://example.com/abs/9999.0001"


def test_read_paper_source_persists_evidence(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    async def fake_fetch(url: str, timeout: float = 20.0):
        return {
            "title": "Multimodal Lab Notes",
            "url": url,
            "source_type": "webpage",
            "content": (
                "We study multimodal planning with agents. "
                "Results show improved retrieval alignment across text and vision."
            ),
            "warning": None,
            "content_type": "text/html",
        }

    monkeypatch.setattr(
        "EvoScientist.tools.search._fetch_source_content",
        fake_fetch,
    )

    result = run_async(
        read_paper_source.ainvoke(
            {
                "url": "https://example.com/multimodal-lab",
                "keywords": ["multimodal", "agent"],
            }
        )
    )

    evidence_path = tmp_path / "artifacts" / "lit_review" / "evidence.jsonl"
    assert evidence_path.exists()
    records = _load_jsonl(evidence_path)
    assert len(records) == 1
    assert records[0]["title"] == "Multimodal Lab Notes"
    assert records[0]["relevance_score"] == 1.0
    assert Path(records[0]["content_path"]).exists()
    assert "Read source: Multimodal Lab Notes" in result


def test_read_paper_source_accepts_json_string_keywords(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    async def fake_fetch(url: str, timeout: float = 20.0):
        return {
            "title": "Agent Discovery Notes",
            "url": url,
            "source_type": "webpage",
            "content": (
                "We study multimodal planning with agents. "
                "Results show improved retrieval alignment across text and vision."
            ),
            "warning": None,
            "content_type": "text/html",
        }

    monkeypatch.setattr(
        "EvoScientist.tools.search._fetch_source_content",
        fake_fetch,
    )

    run_async(
        read_paper_source.ainvoke(
            {
                "url": "https://example.com/agent-discovery",
                "keywords": '["multimodal", "agent"]',
            }
        )
    )

    evidence_path = tmp_path / "artifacts" / "lit_review" / "evidence.jsonl"
    records = _load_jsonl(evidence_path)
    assert records[0]["keywords"] == ["multimodal", "agent"]


def test_extract_claims_updates_existing_record(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    source_dir = tmp_path / "artifacts" / "lit_review" / "sources"
    source_dir.mkdir(parents=True)
    source_path = source_dir / "paper.md"
    source_path.write_text(
        (
            "We propose a multimodal planner for agents. "
            "Results show the system improves retrieval quality by 12 percent. "
            "The ablation study suggests stronger cross-modal alignment."
        ),
        encoding="utf-8",
    )

    evidence_path = tmp_path / "artifacts" / "lit_review" / "evidence.jsonl"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    _upsert_evidence_record(
        evidence_path,
        {
            "title": "Planner Paper",
            "url": "https://example.com/planner",
            "source_type": "webpage",
            "summary": "",
            "claims": [],
            "keywords": ["multimodal", "agent"],
            "relevance_score": 0.0,
            "content_path": source_path.as_posix(),
            "warning": None,
        },
    )

    result = run_async(
        extract_claims.ainvoke(
            {
                "url": "https://example.com/planner",
                "max_claims": 2,
            }
        )
    )

    records = _load_jsonl(evidence_path)
    assert len(records[0]["claims"]) == 2
    assert "improves retrieval quality" in records[0]["claims"][1]
    assert "Extracted 2 claim(s)" in result


def test_extract_claims_accepts_json_string_keywords(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    source_dir = tmp_path / "artifacts" / "lit_review" / "sources"
    source_dir.mkdir(parents=True)
    source_path = source_dir / "paper.md"
    source_path.write_text(
        (
            "We propose a multimodal planner for agents. "
            "Results show the system improves retrieval quality by 12 percent."
        ),
        encoding="utf-8",
    )

    evidence_path = tmp_path / "artifacts" / "lit_review" / "evidence.jsonl"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    _upsert_evidence_record(
        evidence_path,
        {
            "title": "Planner Paper",
            "url": "https://example.com/planner",
            "source_type": "webpage",
            "summary": "",
            "claims": [],
            "keywords": [],
            "relevance_score": 0.0,
            "content_path": source_path.as_posix(),
            "warning": None,
        },
    )

    run_async(
        extract_claims.ainvoke(
            {
                "url": "https://example.com/planner",
                "keywords": '["multimodal", "agent"]',
                "max_claims": 1,
            }
        )
    )

    records = _load_jsonl(evidence_path)
    assert records[0]["keywords"] == ["multimodal", "agent"]


def test_extract_claims_falls_back_to_first_sentences():
    claims = _extract_claims_from_text(
        "Sentence one is fairly descriptive and long enough. "
        "Sentence two continues the explanation in detail.",
        max_claims=2,
    )
    assert len(claims) == 2
