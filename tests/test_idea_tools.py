"""Tests for idea request parsing and brief publishing helpers."""

import hashlib
import json
from pathlib import Path

from EvoScientist.tools.idea import (
    FeishuIdeaDocClient,
    build_idea_brief,
    parse_idea_request_text,
    parse_update_request_text,
    publish_idea_brief_to_feishu_doc,
    run_idea_pipeline,
    update_command_usage_guide,
)
from tests.conftest import run_async


def test_parse_idea_request_text_multiline():
    payload = parse_idea_request_text(
        """
        /idea start
        query: multimodal scientific discovery
        requirements:
        - novel
        - interesting
        urls:
        - https://example.com/paper-a
        - https://example.com/paper-b
        notes:
        - focus on low-cost experiments
        """
    )

    assert payload["query"] == "multimodal scientific discovery"
    assert payload["requirements"] == ["novel", "interesting"]
    assert payload["seed_urls"] == [
        "https://example.com/paper-a",
        "https://example.com/paper-b",
    ]
    assert payload["notes"] == ["focus on low-cost experiments"]


def test_parse_idea_request_text_with_limits():
    payload = parse_idea_request_text(
        """
        /idea start
        query: multimodal scientific discovery
        max_ideas: 5
        max_sources: 6
        """
    )

    assert payload["max_ideas"] == 5
    assert payload["max_sources"] == 6


def test_parse_idea_request_text_with_site_urls():
    payload = parse_idea_request_text(
        """
        /idea start
        query: multimodal scientific discovery
        site_urls:
        - https://example.com/papers
        - https://example.org/archive
        """
    )

    assert payload["site_urls"] == [
        "https://example.com/papers",
        "https://example.org/archive",
    ]


def test_parse_update_request_text_supports_inline_and_structured_fields():
    inline_payload = parse_update_request_text("/update fldcn_usage_demo")
    assert inline_payload["folder_token"] == "fldcn_usage_demo"
    assert inline_payload["title"] == "牢大使用说明"

    structured_payload = parse_update_request_text(
        """
        /update
        folder_token: fldcn_usage_docs
        title: 群使用说明
        ignored_field: should be ignored
        """
    )
    assert structured_payload["folder_token"] == "fldcn_usage_docs"
    assert structured_payload["title"] == "群使用说明"


def test_build_idea_brief_writes_markdown_and_index(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    evidence_dir = tmp_path / "artifacts" / "lit_review"
    evidence_dir.mkdir(parents=True)
    evidence_path = evidence_dir / "evidence.jsonl"
    evidence_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "title": "Paper A",
                        "url": "https://example.com/paper-a",
                        "source_type": "webpage",
                        "summary": "Paper A studies multimodal discovery agents.",
                        "claims": ["Results show better discovery planning."],
                        "relevance_score": 1.0,
                    }
                ),
                json.dumps(
                    {
                        "title": "Paper B",
                        "url": "https://example.com/paper-b",
                        "source_type": "pdf",
                        "summary": "Paper B is related but less direct.",
                        "claims": ["The method improves benchmark performance."],
                        "relevance_score": 0.5,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = build_idea_brief.invoke(
        {
            "idea_title": "Multimodal Discovery Planner",
            "idea_description": "Use multimodal agents to propose scientific hypotheses.",
            "request_text": """
            query: multimodal scientific discovery
            requirements: novel, interesting
            urls:
            - https://example.com/paper-a
            """,
        }
    )

    brief_path = tmp_path / "artifacts" / "ideas" / "multimodal-discovery-planner.md"
    index_path = tmp_path / "artifacts" / "ideas" / "index.json"
    assert brief_path.exists()
    assert index_path.exists()
    markdown = brief_path.read_text(encoding="utf-8")
    assert "## Idea Description" in markdown
    assert "## Relevant Evidence And Research Results" in markdown
    assert "Paper A" in markdown
    assert "Results show better discovery planning." in markdown
    index_payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert index_payload[0]["title"] == "Multimodal Discovery Planner"
    assert "Saved markdown" in result


def test_publish_idea_brief_to_feishu_doc_tracks_state(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    brief_path = tmp_path / "artifacts" / "ideas" / "test-idea.md"
    brief_path.parent.mkdir(parents=True)
    brief_path.write_text("# Test Idea\n\nBody", encoding="utf-8")

    class _FakeConfig:
        feishu_app_id = "cli_test"
        feishu_app_secret = "secret"
        feishu_domain = "https://open.feishu.cn"
        feishu_doc_folder_token = "folder_123"

    class _FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def publish_markdown_doc(self, *, title: str, markdown_content: str, folder_token: str = ""):
            assert title == "Test Idea Doc"
            assert "# Test Idea" in markdown_content
            assert folder_token == "folder_123"
            return {
                "document_token": "doc_token_123",
                "url": "https://feishu.cn/docx/doc_token_123",
                "folder_token": folder_token,
            }

        async def aclose(self):
            return None

    monkeypatch.setattr("EvoScientist.tools.idea.get_effective_config", lambda: _FakeConfig())
    monkeypatch.setattr("EvoScientist.tools.idea.FeishuIdeaDocClient", _FakeClient)

    result = run_async(
        publish_idea_brief_to_feishu_doc.ainvoke(
            {
                "markdown_path": str(brief_path),
                "title": "Test Idea Doc",
                "record_key": "idea-1",
            }
        )
    )

    state_path = tmp_path / "artifacts" / "ideas" / "feishu_docs.json"
    assert state_path.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["idea-1"]["document_token"] == "doc_token_123"
    assert "Published idea brief to Feishu doc." in result


def test_feishu_doc_client_markdown_to_paragraphs():
    client = FeishuIdeaDocClient(app_id="cli_test", app_secret="secret")
    paragraphs = client._markdown_to_paragraphs(
        "# Title\n\nFirst line\ncontinues here\n\n- bullet one\n- bullet two\n\nFinal paragraph."
    )
    assert paragraphs == [
        "# Title",
        "First line continues here",
        "- bullet one",
        "- bullet two",
        "Final paragraph.",
    ]


def test_feishu_doc_client_create_folder_uses_title_field():
    captured: dict[str, object] = {}

    class _FakeResponse:
        def json(self):
            return {
                "code": 0,
                "data": {
                    "token": "fld_demo",
                    "url": "https://feishu.cn/drive/folder/fld_demo",
                },
            }

    class _FakeHttpClient:
        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return _FakeResponse()

    client = FeishuIdeaDocClient(
        app_id="cli_test",
        app_secret="secret",
        http_client=_FakeHttpClient(),
    )
    client._token = "tenant_token"

    payload = run_async(
        client.create_folder(parent_folder_token="fld_parent", name="papers")
    )

    assert payload["token"] == "fld_demo"
    assert captured["json"] == {"title": "papers"}


def test_update_command_usage_guide_refreshes_doc(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    calls: dict[str, object] = {
        "deleted": [],
        "publish": None,
    }

    class _FakeConfig:
        feishu_app_id = "cli_test"
        feishu_app_secret = "secret"
        feishu_domain = "https://open.feishu.cn"
        feishu_doc_folder_token = ""

    class _FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def delete_drive_file(self, *, file_token: str, file_type: str = "file", wait_timeout_seconds: float = 20.0):
            deleted = calls["deleted"]
            assert isinstance(deleted, list)
            deleted.append((file_token, file_type))
            return {"status": "success"}

        async def publish_markdown_doc(self, *, title: str, markdown_content: str, folder_token: str = ""):
            calls["publish"] = {
                "title": title,
                "folder_token": folder_token,
                "markdown_content": markdown_content,
            }
            return {
                "document_token": "doc_usage_new",
                "url": "https://feishu.cn/docx/doc_usage_new",
                "folder_token": folder_token,
            }

        async def aclose(self):
            return None

    folder_token = "fldcn_usage_docs"
    logical_key = f"command-usage-{hashlib.sha1(folder_token.encode('utf-8')).hexdigest()[:12]}"
    state_path = tmp_path / "artifacts" / "ideas" / "feishu_docs.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                logical_key: {
                    "document_token": "doc_usage_old",
                    "folder_token": folder_token,
                    "title": "旧说明",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("EvoScientist.tools.idea.get_effective_config", lambda: _FakeConfig())
    monkeypatch.setattr("EvoScientist.tools.idea.FeishuIdeaDocClient", _FakeClient)

    result = run_async(
        update_command_usage_guide.ainvoke(
            {
                "request_text": (
                    "/update\n"
                    f"folder_token: {folder_token}\n"
                    "title: 群使用说明"
                ),
            }
        )
    )

    guide_path = tmp_path / "artifacts" / "usage" / "command_usage.md"
    assert guide_path.exists()
    markdown = guide_path.read_text(encoding="utf-8")
    assert "# 群使用说明" in markdown
    assert "## /search" in markdown
    assert "`max_papers`" in markdown
    assert "## /update" in markdown

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state[logical_key]["document_token"] == "doc_usage_new"
    assert state[logical_key]["folder_token"] == folder_token
    assert state[logical_key]["title"] == "群使用说明"

    assert calls["deleted"] == [("doc_usage_old", "docx")]
    assert calls["publish"] == {
        "title": "群使用说明",
        "folder_token": folder_token,
        "markdown_content": markdown,
    }
    assert "牢大已更新使用说明文档。" in result
    assert "已写入命令: /idea start, /search, /delete, /update" in result


def test_run_idea_pipeline_creates_candidates_and_doc(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    publish_payloads: list[dict] = []

    class _FakeAsyncTool:
        def __init__(self, handler):
            self._handler = handler

        async def ainvoke(self, payload):
            return await self._handler(payload)

    async def _fake_collect(payload):
        target = tmp_path / "artifacts" / "lit_review"
        target.mkdir(parents=True, exist_ok=True)
        (target / "source_index.json").write_text(
            json.dumps(
                {
                    "query": payload["query"],
                    "sources": [
                        {"url": "https://example.com/a", "title": "Paper A"},
                        {"url": "https://example.com/b", "title": "Paper B"},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return "ok"

    async def _fake_read(payload):
        target = tmp_path / "artifacts" / "lit_review"
        target.mkdir(parents=True, exist_ok=True)
        path = target / "evidence.jsonl"
        existing = []
        if path.exists():
            existing = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        existing.append(
            {
                "title": f"Title for {payload['url']}",
                "url": payload["url"],
                "source_type": "webpage",
                "summary": "This paper studies multimodal discovery agents.",
                "claims": [],
                "relevance_score": 1.0,
                "content_path": str(target / "dummy.md"),
            }
        )
        path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in existing) + "\n", encoding="utf-8")
        return "ok"

    async def _fake_extract(payload):
        path = tmp_path / "artifacts" / "lit_review" / "evidence.jsonl"
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for record in records:
            if record["url"] == payload["url"]:
                record["claims"] = ["Results show stronger multimodal hypothesis search."]
        path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in records) + "\n", encoding="utf-8")
        return "ok"

    async def _fake_publish(payload):
        publish_payloads.append(payload)
        return "Published idea brief to Feishu doc.\nURL: https://feishu.cn/docx/demo"

    monkeypatch.setattr("EvoScientist.tools.idea.collect_sources", _FakeAsyncTool(_fake_collect))
    monkeypatch.setattr("EvoScientist.tools.idea.read_paper_source", _FakeAsyncTool(_fake_read))
    monkeypatch.setattr("EvoScientist.tools.idea.extract_claims", _FakeAsyncTool(_fake_extract))
    monkeypatch.setattr(
        "EvoScientist.tools.idea.publish_idea_brief_to_feishu_doc",
        _FakeAsyncTool(_fake_publish),
    )
    monkeypatch.setattr(
        "EvoScientist.tools.idea._generate_candidate_ideas",
        lambda **kwargs: __import__("asyncio").sleep(
            0,
            result=[
                {
                    "title": "Idea Alpha",
                    "idea_description": "Use multimodal agents to generate scientific hypotheses.",
                    "motivation": "Current systems do not connect evidence across modalities well.",
                    "novelty": "Couple multimodal retrieval with iterative agent planning.",
                    "evidence_urls": ["https://example.com/a"],
                    "research_results": ["Results show stronger multimodal hypothesis search."],
                },
                {
                    "title": "Idea Beta",
                    "idea_description": "Use lightweight multimodal feedback loops for low-cost discovery.",
                    "motivation": "Low-cost setups are still underexplored.",
                    "novelty": "Emphasize cheap verification loops.",
                    "evidence_urls": ["https://example.com/b"],
                    "research_results": ["Related work highlights efficiency gains."],
                },
            ],
        ),
    )

    result = run_async(
        run_idea_pipeline.ainvoke(
            {
                "request_text": """
                /idea start
                query: multimodal scientific discovery
                requirements:
                - novel
                - interesting
                """,
                "max_sources": 2,
                "max_ideas": 2,
                "publish_to_feishu_doc": True,
            }
        )
    )

    run_index = tmp_path / "artifacts" / "ideas" / "runs" / "index.json"
    latest_log = tmp_path / "artifacts" / "ideas" / "latest_pipeline_log.md"
    last_run = tmp_path / "artifacts" / "ideas" / "last_run.json"
    assert run_index.exists()
    assert latest_log.exists()
    assert last_run.exists()
    last_run_payload = json.loads(last_run.read_text(encoding="utf-8"))
    candidates_md = tmp_path / last_run_payload["candidates_markdown_path"]
    candidates_json = tmp_path / last_run_payload["candidates_json_path"]
    assert candidates_md.exists()
    assert candidates_json.exists()
    assert "run_id" in last_run_payload
    assert "Idea Alpha" in candidates_md.read_text(encoding="utf-8")
    assert len(publish_payloads) == 2
    assert publish_payloads[0]["markdown_path"].endswith("idea_candidates.md")
    assert publish_payloads[1]["markdown_path"].endswith("latest_pipeline_log.md")
    assert "Published idea brief to Feishu doc." in result
    assert "Candidates:" in result
    assert "Pipeline log:" in result
