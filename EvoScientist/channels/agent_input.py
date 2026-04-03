"""Helpers for shaping channel messages before they reach the agent."""

from __future__ import annotations

from typing import Any


def build_channel_agent_input(
    content: str,
    *,
    channel_name: str,
    is_group: bool,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Return the agent-facing message for a channel input.

    Group chats get a lightweight instruction block that nudges the agent to
    reply in Chinese by default, while still allowing explicit user language
    requests and preserving technical literals such as code, commands, and
    error messages.
    """
    if not is_group:
        return content

    chat_type = ""
    if metadata:
        chat_type = str(metadata.get("chat_type", "") or "").strip()

    lines = [
        "[Channel Context]",
        f"- Source channel: {channel_name}",
        f"- Chat type: {chat_type or 'group'}",
        "- Your assistant name in this workspace is 牢大. If you refer to yourself, use that name.",
        "- Reply language policy: In this group chat, use natural Chinese by default for normal replies.",
        "- Exceptions: if the user explicitly asks for another language, is asking for translation/localization, or if code, commands, file paths, API names, logs, error messages, and quoted source text are better kept in their original form, follow that need instead.",
        "- When unsure, keep the explanation in Chinese and preserve technical literals as-is.",
        "[/Channel Context]",
        "",
        content,
    ]
    return "\n".join(lines)
