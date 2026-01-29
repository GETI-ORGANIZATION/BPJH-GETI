"""Entry point for ``langgraph dev``.

langgraph.json references ``./langgraph_dev.py:EvoScientist_agent``.
Actual construction lives in ``EvoScientist/EvoScientist.py``.
"""

from EvoScientist.EvoScientist import EvoScientist_agent, create_cli_agent  # noqa: F401
