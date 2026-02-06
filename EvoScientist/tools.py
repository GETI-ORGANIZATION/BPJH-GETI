"""Tools.

This module provides search and reflection tools for the research agent,
using Tavily for URL discovery and fetching full webpage content.
"""

import asyncio
import base64
import mimetypes
import os
from typing import Literal

import httpx
from dotenv import load_dotenv
from langchain_core.tools import InjectedToolArg, tool
from markdownify import markdownify
from tavily import TavilyClient
from typing_extensions import Annotated

from .paths import resolve_virtual_path

load_dotenv(override=True)

# Lazy initialization - only create client when needed
_tavily_client = None


def _get_tavily_client() -> TavilyClient:
    """Get or create the Tavily client (lazy initialization)."""
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = TavilyClient()
    return _tavily_client


async def fetch_webpage_content(url: str, timeout: float = 10.0) -> str:
    """Fetch and convert webpage content to markdown.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Webpage content as markdown
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return markdownify(response.text)
    except Exception as e:
        return f"Error fetching content from {url}: {str(e)}"


@tool(parse_docstring=True)
async def tavily_search(
    query: str,
    max_results: Annotated[int, InjectedToolArg] = 3,
    topic: Annotated[
        Literal["general", "news", "finance"], InjectedToolArg
    ] = "general",
) -> str:
    """Search the web for information on a given query.

    Uses Tavily to discover relevant URLs, then fetches and returns
    full webpage content as markdown for comprehensive research.

    Args:
        query: Search query to execute

    Returns:
        Formatted search results with full webpage content in markdown
    """

    def _sync_search() -> dict:
        return _get_tavily_client().search(
            query,
            max_results=max_results,
            topic=topic,
        )

    try:
        # Run Tavily search asynchronously
        search_results = await asyncio.to_thread(_sync_search)

        # Fetch full content for each URL concurrently
        results = search_results.get("results", [])
        if not results:
            return f"No results found for '{query}'"

        # Fetch all webpages concurrently
        fetch_tasks = [fetch_webpage_content(r["url"]) for r in results]
        contents = await asyncio.gather(*fetch_tasks)

        # Format results
        result_texts = []
        for result, content in zip(results, contents):
            result_text = f"""## {result["title"]}
**URL:** {result["url"]}

{content}

---
"""
            result_texts.append(result_text)

        return f"""Found {len(result_texts)} result(s) for '{query}':

{"".join(result_texts)}"""

    except Exception as e:
        return f"Search failed: {str(e)}"


@tool(parse_docstring=True)
def skill_manager(
    action: Literal["install", "list", "uninstall", "info"],
    source: str = "",
    name: str = "",
    include_system: bool = False,
) -> str:
    """Manage user-installable skills: install from GitHub or local path, list available skills, get details, or uninstall.

    Actions and required parameters:

    action="install" (requires source):
      Install a skill. The source can be:
      - GitHub shorthand: "owner/repo@skill-name" (e.g. "anthropics/skills@peft")
      - GitHub URL: "https://github.com/owner/repo/tree/main/skill-name"
      - Local path: "./my-skill" or "/path/to/skill"
      Nested skills are auto-resolved — if the skill is not at the repo root, subdirectories are searched automatically.

    action="list":
      List installed skills. By default only shows user-installed skills.
      Set include_system=True to also show built-in system skills (peft, accelerate, flash-attention, etc.).

    action="info" (requires name):
      Get details (description, source, path) about a specific skill by name.
      Searches both user and system skills.

    action="uninstall" (requires name):
      Remove a user-installed skill by name. System skills cannot be uninstalled.

    Args:
        action: The operation to perform — "install", "list", "info", or "uninstall"
        source: Required for install — GitHub shorthand, GitHub URL, or local directory path
        name: Required for info and uninstall — the skill name (e.g. "peft", "my-custom-skill")
        include_system: Only for list — set True to include built-in system skills in the output

    Returns:
        Result message
    """
    from .skills_manager import install_skill, list_skills, uninstall_skill, get_skill_info

    if action == "install":
        if not source:
            return (
                "Error: 'source' is required for install action. "
                "Provide a GitHub shorthand (e.g. source='owner/repo@skill-name'), "
                "a GitHub URL, or a local directory path."
            )
        result = install_skill(source)
        if result["success"]:
            return (
                f"Successfully installed skill: {result['name']}\n"
                f"Description: {result.get('description', '(none)')}\n"
                f"Path: {result['path']}\n\n"
                f"Use load_skill to activate it."
            )
        else:
            return f"Failed to install skill: {result['error']}"

    elif action == "list":
        skills = list_skills(include_system=include_system)
        if not skills:
            if include_system:
                return "No skills found."
            return "No user skills installed. Use action='install' to add skills, or set include_system=True to see built-in skills."
        user_skills = [s for s in skills if s.source == "user"]
        system_skills = [s for s in skills if s.source == "system"]
        lines = []
        if user_skills:
            lines.append(f"User Skills ({len(user_skills)}):")
            for skill in user_skills:
                lines.append(f"  - {skill.name}: {skill.description}")
        if system_skills:
            if lines:
                lines.append("")
            lines.append(f"System Skills ({len(system_skills)}):")
            for skill in system_skills:
                lines.append(f"  - {skill.name}: {skill.description}")
        return "\n".join(lines)

    elif action == "uninstall":
        if not name:
            return (
                "Error: 'name' is required for uninstall action. "
                "Use action='list' first to see installed skill names."
            )
        result = uninstall_skill(name)
        if result["success"]:
            return f"Successfully uninstalled skill: {name}"
        else:
            return f"Failed to uninstall skill: {result['error']}"

    elif action == "info":
        if not name:
            return (
                "Error: 'name' is required for info action. "
                "Use action='list' with include_system=True to see all available skill names."
            )
        info = get_skill_info(name)
        if not info:
            return (
                f"Skill not found: {name}. "
                f"Use action='list' with include_system=True to see all available skills."
            )
        return (
            f"Name: {info.name}\n"
            f"Description: {info.description}\n"
            f"Source: {info.source}\n"
            f"Path: {info.path}"
        )

    else:
        return f"Unknown action: {action}. Use 'install', 'list', 'uninstall', or 'info'."


@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on research progress and decision-making.

    Use this tool after each search to analyze results and plan next steps systematically.
    This creates a deliberate pause in the research workflow for quality decision-making.

    When to use:
    - After receiving search results: What key information did I find?
    - Before deciding next steps: Do I have enough to answer comprehensively?
    - When assessing research gaps: What specific information am I still missing?
    - Before concluding research: Can I provide a complete answer now?

    Reflection should address:
    1. Analysis of current findings - What concrete information have I gathered?
    2. Gap assessment - What crucial information is still missing?
    3. Quality evaluation - Do I have sufficient evidence/examples for a good answer?
    4. Strategic decision - Should I continue searching or provide my answer?
    5. Skill leverage - Is there a relevant local skill to load that can accelerate this work?

    Args:
        reflection: Your detailed reflection on research progress, findings, gaps, and next steps

    Returns:
        Confirmation that reflection was recorded for decision-making
    """
    return f"Reflection recorded: {reflection}"


# Supported image extensions and their MIME types
_IMAGE_EXTENSIONS = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
}

# Max file size for image viewing (5MB)
_MAX_IMAGE_SIZE = 5 * 1024 * 1024


@tool(parse_docstring=True)
def view_image(image_path: str) -> "list | str":
    """View and analyze an image file.

    Use this tool when you need to see the visual content of an image file
    (PNG, JPEG, GIF, WebP). The image will be displayed so you can describe,
    analyze, or answer questions about it.

    Note: Use this instead of read_file for image files. read_file only
    returns binary data, while view_image lets you actually see the image.

    Args:
        image_path: Path to the image file (relative to workspace or absolute)

    Returns:
        Image content blocks that the model can visually process
    """
    # Resolve virtual workspace paths: /image.png → {workspace}/image.png
    resolved = image_path
    if not os.path.isfile(resolved):
        resolved = str(resolve_virtual_path(image_path))

    if not os.path.isfile(resolved):
        return f"Error: File not found: {image_path}"
    image_path = resolved

    ext = os.path.splitext(image_path)[1].lower()
    mime_type = _IMAGE_EXTENSIONS.get(ext)
    if not mime_type:
        # Fallback to mimetypes module
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith("image/"):
            return f"Error: Not a supported image format: {ext}"

    file_size = os.path.getsize(image_path)
    if file_size > _MAX_IMAGE_SIZE:
        size_mb = file_size / (1024 * 1024)
        return f"Error: Image too large ({size_mb:.1f}MB). Max is 5MB."

    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")

    size_kb = file_size / 1024
    filename = os.path.basename(image_path)

    return [
        {"type": "text", "text": f"Image: {filename} ({size_kb:.0f}KB, {mime_type})"},
        {"type": "image", "base64": data, "mime_type": mime_type},
    ]
