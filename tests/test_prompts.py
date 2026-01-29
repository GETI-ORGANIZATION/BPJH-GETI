"""Tests for EvoScientist/prompts.py."""

from EvoScientist.prompts import get_system_prompt, EXPERIMENT_WORKFLOW, DELEGATION_STRATEGY


class TestGetSystemPrompt:
    def test_returns_non_empty(self):
        result = get_system_prompt()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_contains_workflow(self):
        result = get_system_prompt()
        assert "Experiment Workflow" in result

    def test_contains_delegation(self):
        result = get_system_prompt()
        assert "Sub-Agent Delegation" in result

    def test_default_params_interpolated(self):
        result = get_system_prompt()
        assert "3 parallel sub-agents" in result
        assert "3 delegation rounds" in result

    def test_custom_params(self):
        result = get_system_prompt(max_concurrent=5, max_iterations=10)
        assert "5 parallel sub-agents" in result
        assert "10 delegation rounds" in result

    def test_workflow_constant_not_empty(self):
        assert len(EXPERIMENT_WORKFLOW) > 0

    def test_delegation_has_placeholders(self):
        assert "{max_concurrent}" in DELEGATION_STRATEGY
        assert "{max_iterations}" in DELEGATION_STRATEGY
