from EvoScientist.cli import commands
from EvoScientist.cli.channel import ChannelMessage


class _FakeAsyncTool:
    def __init__(self, handler):
        self._handler = handler

    async def ainvoke(self, payload):
        return await self._handler(payload)


def test_serve_process_message_hard_routes_search(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    async def _fake_search(payload):
        assert payload["request_text"].startswith("/search")
        return "牢大已完成论文抓取任务。\n论文标题：\n1. Agent Lab"

    import EvoScientist.tools as tools_mod

    monkeypatch.setattr(tools_mod, "run_paper_search", _FakeAsyncTool(_fake_search))

    def _unexpected_run_streaming(**kwargs):
        raise AssertionError("run_streaming should not be called for /search")

    monkeypatch.setattr(commands, "run_streaming", _unexpected_run_streaming)

    captured: dict[str, str] = {}
    monkeypatch.setattr(
        commands,
        "_set_channel_response",
        lambda msg_id, response: captured.setdefault(msg_id, response),
    )

    msg = ChannelMessage(
        msg_id="msg-search-1",
        content="/search\nquery: multimodal agents",
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

    assert "牢大已完成论文抓取任务。" in captured["msg-search-1"]
    assert "Agent Lab" in captured["msg-search-1"]


def test_serve_process_message_hard_routes_delete(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    async def _fake_delete(payload):
        assert payload["request_text"].startswith("/delete")
        return "delete ok"

    import EvoScientist.tools.paper_search as paper_search_mod

    monkeypatch.setattr(paper_search_mod, "delete_paper_search_run", _FakeAsyncTool(_fake_delete))

    def _unexpected_run_streaming(**kwargs):
        raise AssertionError("run_streaming should not be called for /delete")

    monkeypatch.setattr(commands, "run_streaming", _unexpected_run_streaming)

    captured: dict[str, str] = {}
    monkeypatch.setattr(
        commands,
        "_set_channel_response",
        lambda msg_id, response: captured.setdefault(msg_id, response),
    )

    msg = ChannelMessage(
        msg_id="msg-delete-1",
        content="/delete 20260404-123456",
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

    assert captured["msg-delete-1"] == "delete ok"
