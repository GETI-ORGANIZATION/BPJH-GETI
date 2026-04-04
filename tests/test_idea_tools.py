"""Tests for Feishu usage-guide helpers."""

import hashlib
import json

from EvoScientist.tools.idea import (
    FeishuIdeaDocClient,
    parse_update_request_text,
    update_command_usage_guide,
)
from tests.conftest import run_async


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
    assert "## /delete" in markdown
    assert "## /update" in markdown
    assert "## /idea start" not in markdown
    assert "`max_papers`" in markdown

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
    assert "已写入命令: /search, /delete, /update" in result
