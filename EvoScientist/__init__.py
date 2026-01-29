"""EvoScientist Agent — AI-powered research & code execution."""

from .backends import CustomSandboxBackend, ReadOnlyFilesystemBackend
from .middleware import create_skills_middleware
from .prompts import get_system_prompt, RESEARCHER_INSTRUCTIONS
from .tools import tavily_search, think_tool
from .EvoScientist import EvoScientist_agent, create_cli_agent

__all__ = [
    # Agent graph (main export)
    "EvoScientist_agent",
    "create_cli_agent",
    # Backends
    "CustomSandboxBackend",
    "ReadOnlyFilesystemBackend",
    # Middleware
    "create_skills_middleware",
    # Prompts
    "get_system_prompt",
    "RESEARCHER_INSTRUCTIONS",
    # Tools
    "tavily_search",
    "think_tool",
]
