from EvoScientist.channels.agent_input import build_channel_agent_input


def test_group_chat_input_adds_chinese_reply_policy():
    result = build_channel_agent_input(
        "Could you summarize this result?",
        channel_name="feishu",
        is_group=True,
        metadata={"chat_type": "group"},
    )

    assert "[Channel Context]" in result
    assert "use natural Chinese by default" in result
    assert "Exceptions:" in result
    assert result.endswith("Could you summarize this result?")


def test_direct_message_input_is_unchanged():
    content = "Please answer in English."
    result = build_channel_agent_input(
        content,
        channel_name="feishu",
        is_group=False,
        metadata={"chat_type": "p2p"},
    )

    assert result == content
