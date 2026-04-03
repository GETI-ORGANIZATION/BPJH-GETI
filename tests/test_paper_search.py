import json
from pathlib import Path

from EvoScientist.tools.paper_search import (
    delete_paper_search_run,
    parse_delete_request_text,
    parse_search_request_text,
    run_paper_search,
)
from tests.conftest import run_async


class _FakeAsyncTool:
    def __init__(self, handler):
        self._handler = handler

    async def ainvoke(self, payload):
        return await self._handler(payload)


def test_parse_search_request_text_supports_multiline_fields():
    payload = parse_search_request_text(
        "/search\n"
        "query: multimodal agents for scientific discovery\n"
        "keywords:\n"
        "- multimodal agents\n"
        "- scientific discovery\n"
        "date_from: 2023-01-01\n"
        "date_to: 2025-12-31\n"
        "sort: newest\n"
        "max_papers: 7\n"
        "max_results: 9\n"
        "site_urls:\n"
        "- https://example.com/papers\n"
        "seed_urls:\n"
        "- https://example.com/a.pdf\n"
    )

    assert payload["query"] == "multimodal agents for scientific discovery"
    assert payload["keywords"] == ["multimodal agents", "scientific discovery"]
    assert payload["date_from"] == "2023-01-01"
    assert payload["date_to"] == "2025-12-31"
    assert payload["sort"] == "newest"
    assert payload["max_papers"] == 7
    assert payload["max_results"] == 9
    assert payload["site_urls"] == ["https://example.com/papers"]
    assert payload["seed_urls"] == ["https://example.com/a.pdf"]


def test_parse_delete_request_text_extracts_selector():
    payload = parse_delete_request_text("/delete 20260404-123456")

    assert payload["selector"] == "20260404-123456"
    assert payload["normalized_selector"] == "20260404123456"


def test_parse_search_request_text_ignores_unknown_fields():
    payload = parse_search_request_text(
        "/search\n"
        "query: agent benchmark\n"
        "foo: should be ignored\n"
        "这是一句额外说明，也应该忽略\n"
        "max_papers: 2\n"
    )

    assert payload["query"] == "agent benchmark"
    assert payload["max_papers"] == 2
    assert payload["notes"] == []


def test_run_paper_search_builds_run_dir_and_uploads_files(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    async def _fake_crawl(payload):
        lit_dir = Path.cwd() / "artifacts" / "lit_review"
        lit_dir.mkdir(parents=True, exist_ok=True)
        (lit_dir / "site_crawl_index.json").write_text(
            json.dumps(
                {
                    "articles": [
                        {
                            "title": "Crawler Paper",
                            "url": "https://example.com/crawler-paper",
                            "source_type": "webpage",
                            "relevance_score": 0.8,
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return "crawl ok"

    async def _fake_collect(payload):
        lit_dir = Path.cwd() / "artifacts" / "lit_review"
        lit_dir.mkdir(parents=True, exist_ok=True)
        (lit_dir / "source_index.json").write_text(
            json.dumps(
                {
                    "sources": [
                        {
                            "rank": 1,
                            "title": "Agent Lab",
                            "url": "https://example.com/agent-lab",
                            "source_type": "webpage",
                            "snippet": "A strong paper about agent labs.",
                            "relevance_score": 1.0,
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return "collect ok"

    async def _fake_fetch(url: str, timeout: float = 20.0):
        return {
            "title": "Agent Lab",
            "url": url,
            "source_type": "webpage",
            "content": (
                "We study multimodal planning agents in scientific discovery. "
                "Results show improved retrieval quality and stronger evidence coverage."
            ),
            "warning": None,
            "content_type": "text/html",
            "raw_html": "<html><head><title>Agent Lab</title></head><body>paper</body></html>",
            "published_at": "2024-05-12",
        }

    class _FakeConfig:
        tavily_api_key = ""
        feishu_app_id = "cli_xxx"
        feishu_app_secret = "secret"
        feishu_domain = "https://open.feishu.cn"
        feishu_doc_folder_token = "fld_root"

    class _FakeFeishuClient:
        uploaded: list[str] = []

        def __init__(self, *args, **kwargs):
            type(self).uploaded = []

        async def _root_folder_token(self):
            return "fld_root"

        async def ensure_child_folder(self, *, parent_folder_token: str, name: str):
            assert parent_folder_token == "fld_root"
            assert name == "papers"
            return {"token": "fld_papers", "url": "https://feishu.cn/drive/folder/fld_papers"}

        async def create_folder(self, *, parent_folder_token: str, name: str):
            assert parent_folder_token == "fld_papers"
            return {"token": "fld_run", "url": f"https://feishu.cn/drive/folder/{name}"}

        async def upload_drive_file(self, *, file_path: str, parent_folder_token: str):
            assert parent_folder_token == "fld_run"
            type(self).uploaded.append(file_path)
            return {"file_token": "file_xxx", "url": "https://feishu.cn/file/demo"}

        async def aclose(self):
            return None

    monkeypatch.setattr(
        "EvoScientist.tools.paper_search.crawl_site_articles",
        _FakeAsyncTool(_fake_crawl),
    )
    monkeypatch.setattr(
        "EvoScientist.tools.paper_search.collect_sources",
        _FakeAsyncTool(_fake_collect),
    )
    monkeypatch.setattr(
        "EvoScientist.tools.paper_search._fetch_source_content",
        _fake_fetch,
    )
    monkeypatch.setattr(
        "EvoScientist.tools.paper_search.get_effective_config",
        lambda: _FakeConfig(),
    )
    monkeypatch.setattr(
        "EvoScientist.tools.paper_search.FeishuIdeaDocClient",
        _FakeFeishuClient,
    )

    result = run_async(
        run_paper_search.ainvoke(
            {
                "request_text": (
                    "/search\n"
                    "query: multimodal agents\n"
                    "site_urls:\n"
                    "- https://example.com/papers\n"
                    "max_papers: 3\n"
                )
            }
        )
    )

    metadata_path = tmp_path / "artifacts" / "paper_search" / "invocations.jsonl"
    assert metadata_path.exists()
    lines = metadata_path.read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[-1])
    assert payload["completed"] is True
    assert payload["run_id"]
    assert payload["paper_count"] == 2
    assert payload["uploaded_count"] >= 3
    assert payload["feishu_folder_token"] == "fld_run"
    assert payload["feishu_folder_name"]
    assert "牢大已完成论文抓取任务。" in result
    assert "Agent Lab" in result
    assert "本地仅记录元数据:" in result
    assert "飞书文件夹:" in result
    assert any(path.endswith("summary.md") for path in _FakeFeishuClient.uploaded)
    assert not (tmp_path / "artifacts" / "paper_search" / "runs").exists()
    assert not (tmp_path / "artifacts" / "lit_review").exists()


def test_delete_paper_search_run_removes_metadata_and_remote_folder(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    metadata_dir = tmp_path / "artifacts" / "paper_search"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = metadata_dir / "invocations.jsonl"
    metadata_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "called_at": "2026-04-04 12:34:56",
                        "command": "/search\\nquery: agent benchmark",
                        "query": "agent benchmark",
                        "completed": True,
                        "status": "completed",
                        "run_id": "20260404-123456-agent-benchmark",
                        "paper_count": 1,
                        "uploaded_count": 3,
                        "feishu_folder_token": "fld_run_1",
                        "feishu_folder_name": "20260404-123456-agent-benchmark",
                        "feishu_folder_url": "https://feishu.cn/drive/folder/fld_run_1",
                        "error": "",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "called_at": "2026-04-04 13:00:00",
                        "command": "/search\\nquery: other run",
                        "query": "other run",
                        "completed": True,
                        "status": "completed",
                        "run_id": "20260404-130000-other-run",
                        "paper_count": 2,
                        "uploaded_count": 4,
                        "feishu_folder_token": "fld_run_2",
                        "feishu_folder_name": "20260404-130000-other-run",
                        "feishu_folder_url": "https://feishu.cn/drive/folder/fld_run_2",
                        "error": "",
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    class _FakeConfig:
        feishu_app_id = "cli_xxx"
        feishu_app_secret = "secret"
        feishu_domain = "https://open.feishu.cn"
        feishu_doc_folder_token = "fld_root"

    class _FakeFeishuClient:
        deleted: list[tuple[str, str]] = []

        def __init__(self, *args, **kwargs):
            type(self).deleted = []

        async def delete_drive_file(self, *, file_token: str, file_type: str = "file"):
            type(self).deleted.append((file_token, file_type))
            return {"file_token": file_token, "file_type": file_type, "status": "success"}

        async def aclose(self):
            return None

    monkeypatch.setattr(
        "EvoScientist.tools.paper_search.get_effective_config",
        lambda: _FakeConfig(),
    )
    monkeypatch.setattr(
        "EvoScientist.tools.paper_search.FeishuIdeaDocClient",
        _FakeFeishuClient,
    )

    result = run_async(
        delete_paper_search_run.ainvoke({"request_text": "/delete 20260404-123456"})
    )

    remaining = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines()]
    assert len(remaining) == 1
    assert remaining[0]["run_id"] == "20260404-130000-other-run"
    assert _FakeFeishuClient.deleted == [("fld_run_1", "folder")]
    assert "/delete" in result
