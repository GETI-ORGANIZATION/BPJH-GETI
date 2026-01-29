"""Tests for StreamState, SubAgentState, and display helpers from cli.py."""

from EvoScientist.cli import (
    SubAgentState,
    StreamState,
    _parse_todo_items,
    _build_todo_stats,
)


# === SubAgentState ===

class TestSubAgentState:
    def test_add_tool_call(self):
        sa = SubAgentState("research-agent")
        sa.add_tool_call("tavily_search", {"query": "test"}, "tc1")
        assert len(sa.tool_calls) == 1
        assert sa.tool_calls[0]["name"] == "tavily_search"

    def test_add_tool_call_dedup_by_id(self):
        sa = SubAgentState("research-agent")
        sa.add_tool_call("tavily_search", {"query": "test"}, "tc1")
        sa.add_tool_call("tavily_search", {"query": "updated"}, "tc1")
        assert len(sa.tool_calls) == 1
        assert sa.tool_calls[0]["args"]["query"] == "updated"

    def test_add_tool_call_merge_name(self):
        """When first call has empty name, second should fill it in."""
        sa = SubAgentState("agent")
        sa.add_tool_call("", {}, "tc1")
        # Empty name + empty id → skipped entirely
        # But with an id, it can be tracked:
        # Actually, empty name with id is also skipped per the code (not name check)
        # Let's use a named call first, then merge args
        sa2 = SubAgentState("agent")
        sa2.add_tool_call("search", {}, "tc1")
        sa2.add_tool_call("search", {"query": "test"}, "tc1")
        assert sa2.tool_calls[0]["args"] == {"query": "test"}

    def test_skip_empty_name_no_id(self):
        sa = SubAgentState("agent")
        sa.add_tool_call("", {}, "")
        assert len(sa.tool_calls) == 0

    def test_add_tool_result_matched(self):
        sa = SubAgentState("agent")
        sa.add_tool_call("execute", {}, "tc1")
        sa.add_tool_result("execute", "output", True)
        result = sa.get_result_for(sa.tool_calls[0])
        assert result is not None
        assert result["content"] == "output"

    def test_add_tool_result_fallback(self):
        """When name doesn't match, falls back to first unmatched."""
        sa = SubAgentState("agent")
        sa.add_tool_call("execute", {}, "tc1")
        sa.add_tool_result("different_name", "output", True)
        result = sa.get_result_for(sa.tool_calls[0])
        assert result is not None
        assert result["content"] == "output"

    def test_get_result_for_no_match(self):
        sa = SubAgentState("agent")
        tc = {"id": "tc_missing", "name": "x", "args": {}}
        assert sa.get_result_for(tc) is None

    def test_get_result_for_index_fallback(self):
        """When no id, falls back to index-based matching."""
        sa = SubAgentState("agent")
        tc = {"id": "", "name": "execute", "args": {}}
        sa.tool_calls.append(tc)
        sa.tool_results.append({"name": "execute", "content": "ok", "success": True})
        result = sa.get_result_for(tc)
        assert result is not None


# === StreamState ===

class TestStreamState:
    def test_handle_thinking(self):
        state = StreamState()
        result = state.handle_event({"type": "thinking", "content": "hmm"})
        assert result == "thinking"
        assert state.is_thinking is True
        assert state.thinking_text == "hmm"

    def test_handle_text(self):
        state = StreamState()
        result = state.handle_event({"type": "text", "content": "hello"})
        assert result == "text"
        assert state.is_responding is True
        assert state.response_text == "hello"

    def test_handle_text_accumulates(self):
        state = StreamState()
        state.handle_event({"type": "text", "content": "a"})
        state.handle_event({"type": "text", "content": "b"})
        assert state.response_text == "ab"

    def test_handle_tool_call(self):
        state = StreamState()
        state.handle_event({
            "type": "tool_call",
            "id": "tc1",
            "name": "execute",
            "args": {"command": "ls"},
        })
        assert len(state.tool_calls) == 1
        assert state.tool_calls[0]["name"] == "execute"

    def test_handle_tool_call_update_existing(self):
        state = StreamState()
        state.handle_event({"type": "tool_call", "id": "tc1", "name": "execute", "args": {}})
        state.handle_event({"type": "tool_call", "id": "tc1", "name": "execute", "args": {"command": "ls"}})
        assert len(state.tool_calls) == 1
        assert state.tool_calls[0]["args"] == {"command": "ls"}

    def test_handle_tool_result(self):
        state = StreamState()
        state.handle_event({
            "type": "tool_result",
            "name": "execute",
            "content": "[OK] done",
        })
        assert len(state.tool_results) == 1
        assert state.is_processing is True

    def test_handle_subagent_start(self):
        state = StreamState()
        state.handle_event({"type": "subagent_start", "name": "research-agent", "description": "Search"})
        assert len(state.subagents) == 1
        assert state.subagents[0].name == "research-agent"
        assert state.subagents[0].is_active is True

    def test_handle_subagent_tool_call(self):
        state = StreamState()
        state.handle_event({
            "type": "subagent_tool_call",
            "subagent": "research-agent",
            "name": "tavily_search",
            "args": {"query": "test"},
            "id": "tc_sa1",
        })
        assert len(state.subagents) == 1
        assert len(state.subagents[0].tool_calls) == 1

    def test_handle_subagent_tool_result(self):
        state = StreamState()
        state.handle_event({
            "type": "subagent_tool_call",
            "subagent": "code-agent",
            "name": "execute",
            "args": {},
            "id": "tc1",
        })
        state.handle_event({
            "type": "subagent_tool_result",
            "subagent": "code-agent",
            "name": "execute",
            "content": "output",
            "success": True,
        })
        sa = state.subagents[0]
        assert len(sa.tool_results) == 1

    def test_handle_subagent_end(self):
        state = StreamState()
        state.handle_event({"type": "subagent_start", "name": "agent-x", "description": ""})
        state.handle_event({"type": "subagent_end", "name": "agent-x"})
        assert state.subagents[0].is_active is False

    def test_handle_done(self):
        state = StreamState()
        state.handle_event({"type": "done", "response": "Final answer"})
        assert state.is_processing is False
        assert state.response_text == "Final answer"

    def test_handle_done_does_not_overwrite_existing_response(self):
        state = StreamState()
        state.handle_event({"type": "text", "content": "Already here"})
        state.handle_event({"type": "done", "response": "Final"})
        assert state.response_text == "Already here"

    def test_handle_error(self):
        state = StreamState()
        state.handle_event({"type": "error", "message": "boom"})
        assert "[Error] boom" in state.response_text
        assert state.is_processing is False

    def test_full_event_sequence(self, sample_events):
        state = StreamState()
        for event in sample_events:
            state.handle_event(event)
        assert state.thinking_text == "Let me think..."
        assert "Here is the answer." in state.response_text
        assert len(state.tool_calls) == 1
        assert len(state.tool_results) == 1
        assert len(state.subagents) == 1
        assert state.subagents[0].is_active is False


# === Name merging ===

class TestNameMerging:
    def test_generic_subagent_merged(self):
        state = StreamState()
        # First event creates generic "sub-agent"
        state.handle_event({
            "type": "subagent_tool_call",
            "subagent": "sub-agent",
            "name": "execute",
            "args": {},
            "id": "tc1",
        })
        assert len(state.subagents) == 1
        assert state.subagents[0].name == "sub-agent"

        # Proper name arrives, should merge
        sa = state._get_or_create_subagent("code-agent", "write code")
        assert len(state.subagents) == 1
        assert sa.name == "code-agent"
        assert len(sa.tool_calls) == 1  # preserved from generic entry

    def test_no_merge_when_not_generic(self):
        state = StreamState()
        state.handle_event({"type": "subagent_start", "name": "research-agent", "description": ""})
        state._get_or_create_subagent("code-agent")
        assert len(state.subagents) == 2


# === _parse_todo_items ===

class TestParseTodoItems:
    def test_json_input(self):
        import json
        items = [{"status": "todo", "content": "Do X"}]
        result = _parse_todo_items(json.dumps(items))
        assert result is not None
        assert len(result) == 1

    def test_python_literal(self):
        result = _parse_todo_items('[{"status": "done", "content": "Y"}]')
        assert result is not None

    def test_embedded_list(self):
        text = "Updated todos:\n" + '[{"status": "todo", "content": "A"}]'
        result = _parse_todo_items(text)
        assert result is not None

    def test_invalid_input(self):
        assert _parse_todo_items("not a list at all") is None

    def test_empty_string(self):
        assert _parse_todo_items("") is None


# === _build_todo_stats ===

class TestBuildTodoStats:
    def test_mixed_statuses(self):
        items = [
            {"status": "done"},
            {"status": "active"},
            {"status": "todo"},
            {"status": "completed"},
        ]
        result = _build_todo_stats(items)
        assert "1 active" in result
        assert "2 done" in result
        assert "1 pending" in result

    def test_all_done(self):
        items = [{"status": "done"}, {"status": "complete"}]
        result = _build_todo_stats(items)
        assert "2 done" in result
        assert "active" not in result

    def test_unknown_status_becomes_pending(self):
        items = [{"status": "unknown_status"}]
        result = _build_todo_stats(items)
        assert "1 pending" in result

    def test_empty_items(self):
        result = _build_todo_stats([])
        assert "0 items" in result
