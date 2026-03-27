"""Tests for the hard-routed `/idea start` serve flow."""

from __future__ import annotations

import json

from EvoScientist.cli import commands
from EvoScientist.cli.channel import ChannelMessage


class _FakeSyncTool:
    def __init__(self, handler):
        self._handler = handler

    def invoke(self, payload):
        return self._handler(payload)


class _FakeAsyncTool:
    def __init__(self, handler):
        self._handler = handler

    async def ainvoke(self, payload):
        return await self._handler(payload)


def test_serve_process_message_hard_routes_idea_start(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    publish_payloads: list[dict] = []
    ask_user_payloads: list[dict] = []

    async def _fake_pipeline(payload):
        assert payload["max_ideas"] == 5
        assert payload["max_sources"] == 6
        run_dir = tmp_path / "artifacts" / "ideas" / "runs" / "20260319-demo-run"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "idea_candidates.json").write_text(
            json.dumps(
                [
                    {
                        "title": "Idea Alpha",
                        "idea_description": "Alpha description",
                        "motivation": "Alpha motivation",
                        "novelty": "Alpha novelty",
                        "background": "Alpha background",
                        "proposed_method": "Alpha method",
                        "validation_plan": "Alpha validation",
                        "risks": "Alpha risks",
                        "evidence_urls": ["https://example.com/a"],
                    },
                    {
                        "title": "Idea Beta",
                        "idea_description": "Beta description",
                        "motivation": "Beta motivation",
                        "novelty": "Beta novelty",
                        "background": "Beta background",
                        "proposed_method": "Beta method",
                        "validation_plan": "Beta validation",
                        "risks": "Beta risks",
                        "evidence_urls": ["https://example.com/b"],
                    },
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (run_dir / "source_index.md").write_text(
            "# Source Index\n\nBody",
            encoding="utf-8",
        )
        (run_dir / "evidence_report.md").write_text(
            "# Evidence Report\n\nBody",
            encoding="utf-8",
        )
        (run_dir / "latest_pipeline_log.md").write_text(
            "# Idea Pipeline Log\n\nStep details",
            encoding="utf-8",
        )
        (run_dir / "idea-alpha.md").write_text(
            "# Idea Alpha\n\n## Idea Description\nAlpha description",
            encoding="utf-8",
        )
        ideas_dir = tmp_path / "artifacts" / "ideas"
        ideas_dir.mkdir(parents=True, exist_ok=True)
        (ideas_dir / "last_run.json").write_text(
            json.dumps(
                {
                    "run_dir": "artifacts/ideas/runs/20260319-demo-run",
                    "source_index_markdown_path": "artifacts/ideas/runs/20260319-demo-run/source_index.md",
                    "evidence_markdown_path": "artifacts/ideas/runs/20260319-demo-run/evidence_report.md",
                    "candidates_markdown_path": "artifacts/ideas/runs/20260319-demo-run/idea_candidates.md",
                    "candidates_json_path": "artifacts/ideas/runs/20260319-demo-run/idea_candidates.json",
                    "latest_log_path": "artifacts/ideas/runs/20260319-demo-run/latest_pipeline_log.md",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return "Pipeline completed."

    def _fake_build(payload):
        ideas_dir = tmp_path / "artifacts" / "ideas" / "runs" / "20260319-demo-run"
        ideas_dir.mkdir(parents=True, exist_ok=True)
        brief_path = ideas_dir / "idea-alpha.md"
        brief_path.write_text(
            "# Idea Alpha\n\n## Idea Description\nAlpha description",
            encoding="utf-8",
        )
        assert payload["idea_title"] == "Idea Alpha"
        assert payload["output_dir"].endswith("20260319-demo-run")
        return "Saved markdown to artifacts/ideas/idea-alpha.md"

    async def _fake_publish(payload):
        publish_payloads.append(payload)
        return "Published idea brief to Feishu doc.\nURL: https://feishu.cn/docx/demo-alpha"

    import EvoScientist.tools as tools_mod

    monkeypatch.setattr(tools_mod, "run_idea_pipeline", _FakeAsyncTool(_fake_pipeline))
    monkeypatch.setattr(tools_mod, "build_idea_brief", _FakeSyncTool(_fake_build))
    monkeypatch.setattr(
        tools_mod,
        "publish_idea_brief_to_feishu_doc",
        _FakeAsyncTool(_fake_publish),
    )
    monkeypatch.setattr(
        commands,
        "channel_ask_user_prompt",
        lambda ask_user_data, msg: (
            ask_user_payloads.append(ask_user_data) or {
                "status": "answered",
                "answers": ["Idea Alpha"],
            }
        ),
    )

    def _unexpected_run_streaming(**kwargs):
        raise AssertionError("run_streaming should not be called for /idea start")

    monkeypatch.setattr(commands, "run_streaming", _unexpected_run_streaming)

    captured: dict[str, str] = {}
    monkeypatch.setattr(
        commands,
        "_set_channel_response",
        lambda msg_id, response: captured.setdefault(msg_id, response),
    )

    msg = ChannelMessage(
        msg_id="msg-1",
        content=(
            "/idea start\n"
            "query: multimodal agents for scientific discovery\n"
            "requirements:\n"
            "- novel\n"
            "- interesting\n"
            "max_ideas: 5\n"
            "max_sources: 6\n"
        ),
        sender="tester",
        channel_type="feishu",
        chat_id="chat-1",
        metadata={},
    )

    commands._serve_process_message(
        msg,
        agent=object(),
        thread_id="thread-1",
        model=None,
        workspace_dir=str(tmp_path),
        show_thinking=False,
    )

    response = captured["msg-1"]
    assert "Pipeline completed." in response
    assert "Selected candidate: Idea Alpha" in response
    assert "Published idea brief to Feishu doc." in response
    assert "Motivation: Alpha motivation" in response
    assert "Novelty: Alpha novelty" in response
    assert "Alpha background" in ask_user_payloads[0]["questions"][0]["question"]
    assert "Alpha validation" in ask_user_payloads[0]["questions"][0]["question"]
    assert len(publish_payloads) == 6
    assert publish_payloads[0]["markdown_path"].endswith("source_index.md")
    assert publish_payloads[1]["markdown_path"].endswith("evidence_report.md")
    assert publish_payloads[2]["markdown_path"].endswith("idea_candidates.md")
    assert publish_payloads[3]["markdown_path"].endswith("latest_pipeline_log.md")
    assert publish_payloads[4]["markdown_path"].endswith("idea-alpha.md")
    assert publish_payloads[5]["markdown_path"].endswith("latest_pipeline_log.md")


def test_handle_idea_start_command_returns_pipeline_summary_when_selection_cancelled(
    monkeypatch,
    tmp_path,
):
    monkeypatch.chdir(tmp_path)

    async def _fake_pipeline(payload):
        run_dir = tmp_path / "artifacts" / "ideas" / "runs" / "20260319-demo-run"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "idea_candidates.json").write_text(
            json.dumps([{"title": "Idea Alpha"}], ensure_ascii=False),
            encoding="utf-8",
        )
        ideas_dir = tmp_path / "artifacts" / "ideas"
        ideas_dir.mkdir(parents=True, exist_ok=True)
        (ideas_dir / "last_run.json").write_text(
            json.dumps(
                {
                    "candidates_json_path": "artifacts/ideas/runs/20260319-demo-run/idea_candidates.json",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return "Pipeline completed."

    import EvoScientist.tools as tools_mod

    monkeypatch.setattr(tools_mod, "run_idea_pipeline", _FakeAsyncTool(_fake_pipeline))
    monkeypatch.setattr(
        commands,
        "channel_ask_user_prompt",
        lambda ask_user_data, msg: {"status": "cancelled"},
    )

    msg = ChannelMessage(
        msg_id="msg-2",
        content="/idea start\nquery: multimodal agents",
        sender="tester",
        channel_type="feishu",
        chat_id="chat-1",
        metadata={},
    )

    response = commands._handle_idea_start_command(msg, workspace_dir=str(tmp_path))
    assert "Pipeline completed." in response
    assert "selection was cancelled or timed out" in response


def test_publish_markdown_with_recovery_can_skip_after_issue(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    markdown_path = tmp_path / "artifacts" / "ideas" / "latest_pipeline_log.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("# Log", encoding="utf-8")

    class _FailingPublishTool:
        async def ainvoke(self, payload):
            return "Failed to publish Feishu doc for log: permission denied"

    import EvoScientist.tools as tools_mod

    monkeypatch.setattr(
        tools_mod,
        "publish_idea_brief_to_feishu_doc",
        _FailingPublishTool(),
    )
    monkeypatch.setattr(
        commands,
        "channel_ask_user_prompt",
        lambda ask_user_data, msg: {"status": "answered", "answers": ["skip"]},
    )

    msg = ChannelMessage(
        msg_id="msg-3",
        content="/idea start\nquery: multimodal agents",
        sender="tester",
        channel_type="feishu",
        chat_id="chat-1",
        metadata={},
    )

    response = commands._publish_markdown_with_recovery(
        msg,
        markdown_path=str(markdown_path),
        title="Idea Pipeline Log",
        record_key="idea-log-demo",
        step_name="Pipeline log publish",
    )
    assert "was skipped after a publish issue" in response
