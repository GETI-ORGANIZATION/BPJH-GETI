"""EvoScientist Agent graph construction.

This module creates and exports the compiled agent graph.
Usage:
    from EvoScientist import agent

    # Notebook / programmatic usage
    for state in agent.stream(
        {"messages": [HumanMessage(content="your question")]},
        config={"configurable": {"thread_id": "1"}},
        stream_mode="values",
    ):
        ...
"""

import os
from datetime import datetime
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend, CompositeBackend
from langchain.chat_models import init_chat_model

from .backends import CustomSandboxBackend, ReadOnlyFilesystemBackend
from .middleware import create_skills_middleware
from .prompts import RESEARCHER_INSTRUCTIONS, get_system_prompt
from .utils import load_subagents
from .tools import tavily_search, think_tool

# =============================================================================
# Configuration
# =============================================================================

# Backend mode: "sandbox" (with execute) or "filesystem" (read/write only)
BACKEND_MODE = "sandbox"

# Research limits
MAX_CONCURRENT = 3  # Max parallel sub-agents
MAX_ITERATIONS = 3  # Max delegation rounds

# Workspace settings
WORKSPACE_DIR = "./workspace/"
SKILLS_DIR = "./skills/"
SUBAGENTS_CONFIG = Path(__file__).parent / "subagent.yaml"

# =============================================================================
# Initialization
# =============================================================================

# Get current date
current_date = datetime.now().strftime("%Y-%m-%d")

# Generate system prompt with limits
SYSTEM_PROMPT = get_system_prompt(
    max_concurrent=MAX_CONCURRENT,
    max_iterations=MAX_ITERATIONS,
)

# Initialize chat model
chat_model = init_chat_model(
    model="claude-sonnet-4-5-20250929",
    model_provider="anthropic",
    # thinking={"type": "enabled", "budget_tokens": 2000},
)

# Initialize workspace backend based on mode
if BACKEND_MODE == "sandbox":
    _workspace_backend = CustomSandboxBackend(
        root_dir=WORKSPACE_DIR,
        virtual_mode=True,
        timeout=300,
    )
else:
    _workspace_backend = FilesystemBackend(
        root_dir=WORKSPACE_DIR,
        virtual_mode=True,
    )

# Skills backend: read-only access to ./skills/
_skills_backend = ReadOnlyFilesystemBackend(
    root_dir=SKILLS_DIR,
    virtual_mode=True,
)

# Composite backend: workspace as default, skills mounted at /skills/
backend = CompositeBackend(
    default=_workspace_backend,
    routes={"/skills/": _skills_backend},
)

tool_registry = {
    "think_tool": think_tool,
    "tavily_search": tavily_search,
}

prompt_refs = {
    "RESEARCHER_INSTRUCTIONS": RESEARCHER_INSTRUCTIONS.format(date=current_date),
}

subagents = load_subagents(
    SUBAGENTS_CONFIG,
    tool_registry=tool_registry,
    prompt_refs=prompt_refs,
)

# Shared kwargs for agent creation
_AGENT_KWARGS = dict(
    name="EvoScientist",
    model=chat_model,
    tools=[think_tool],
    backend=backend,
    subagents=subagents,
    middleware=[create_skills_middleware(SKILLS_DIR, WORKSPACE_DIR)],
    system_prompt=SYSTEM_PROMPT,
)

# Default agent (no checkpointer) — used by langgraph dev / LangSmith / notebooks
EvoScientist_agent = create_deep_agent(**_AGENT_KWARGS).with_config({"recursion_limit": 500})


def create_cli_agent(workspace_dir: str | None = None):
    """Create agent with InMemorySaver checkpointer for CLI multi-turn support.

    Args:
        workspace_dir: Optional per-session workspace directory. If provided,
            creates a fresh backend rooted at this path. If None, uses the
            module-level default backend (./workspace/).
    """
    from langgraph.checkpoint.memory import InMemorySaver  # type: ignore[import-untyped]

    if workspace_dir:
        ws_backend = CustomSandboxBackend(
            root_dir=workspace_dir,
            virtual_mode=True,
            timeout=300,
        )
        sk_backend = ReadOnlyFilesystemBackend(
            root_dir=SKILLS_DIR,
            virtual_mode=True,
        )
        be = CompositeBackend(
            default=ws_backend,
            routes={"/skills/": sk_backend},
        )
        mw = [create_skills_middleware(SKILLS_DIR, workspace_dir)]
        kwargs = dict(
            _AGENT_KWARGS,
            backend=be,
            middleware=mw,
        )
    else:
        kwargs = dict(_AGENT_KWARGS)

    return create_deep_agent(
        **kwargs,
        checkpointer=InMemorySaver(),
    ).with_config({"recursion_limit": 500})
