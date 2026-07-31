"""
Integration tests for the Agent Loop — single-turn & multi-turn scenarios.

Không cần API key thật: dùng MockProvider trả lời predefined.
Kiểm tra agent chọn tool đúng, gọi tool đúng, trả lời đúng theo context.

Cách chạy:
    cd codebase && python -m pytest tests/test_agent_flow.py -v
"""
import json
import pytest
from typing import Any
from dataclasses import dataclass
from app.agent.providers.base import ModelResponse, ToolCall
from app.agent.providers import make_provider
from app.chat import run_model_tool_loop
from app.tools import load_tool_declarations, to_openai_tools
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
# MOCK PROVIDER
# ═══════════════════════════════════════════════════════════════

@dataclass
class MockResponse:
    text: str | None = None
    tool_calls: list | None = None


class MockProvider:
    """Provider giả lập — trả về response predefined dựa vào pattern trong user message."""
    default_model = "mock-model"

    def __init__(self):
        self.call_history = []
        self.responses: list[MockResponse] = []

    def add_response(self, text: str = None, tool_calls: list = None):
        self.responses.append(MockResponse(text=text, tool_calls=tool_calls))

    def add_single_tool(self, name: str, args: dict, text: str = None):
        self.responses.append(MockResponse(
            text=text,
            tool_calls=[{"name": name, "args": args}],
        ))

    def add_multi_tool(self, calls: list[tuple[str, dict]], text: str = None):
        self.responses.append(MockResponse(
            text=text,
            tool_calls=[{"name": n, "args": a} for n, a in calls],
        ))

    def complete(self, messages, tools=None, *, model=None, temperature=0.0, tool_choice=None):
        self.call_history.append({"messages": messages, "tool_choice": tool_choice})
        if not self.responses:
            return ModelResponse(text="I don't know how to respond to this.")
        resp = self.responses.pop(0)
        tc = []
        if resp.tool_calls:
            for c in resp.tool_calls:
                tc.append(ToolCall(name=c["name"], args=c["args"]))
        return ModelResponse(text=resp.text, tool_calls=tc)


# ═══════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def provider():
    return MockProvider()


@pytest.fixture
def tools():
    tools_path = Path("app/prompt/tools.yaml")
    decls = load_tool_declarations(tools_path)
    return to_openai_tools(decls)


@pytest.fixture
def system():
    sp_path = Path("app/prompt/system_prompt.md")
    return sp_path.read_text(encoding="utf-8")


def _call(provider, system, tools, user_msg, history=None, max_rounds=4):
    """Helper: gọi agent loop với 1 user message."""
    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_msg})
    return run_model_tool_loop(
        provider=provider,
        messages=messages,
        tools=tools,
        model="mock",
        max_tool_rounds=max_rounds,
    )


# ═══════════════════════════════════════════════════════════════
# SIMPLE TESTS
# ═══════════════════════════════════════════════════════════════

class TestMockProviderSanity:
    """Mock provider hoạt động đúng."""

    def test_provider_returns_text(self, provider):
        provider.add_response(text="Hello! I'm an AI assistant.")
        resp = provider.complete([])
        assert resp.text == "Hello! I'm an AI assistant."
        assert resp.tool_calls == []

    def test_provider_returns_tool_call(self, provider):
        provider.add_single_tool("get_lab_content", {"lab_id": "DAY05"})
        resp = provider.complete([])
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "get_lab_content"
        assert resp.tool_calls[0].args == {"lab_id": "DAY05"}


# ═══════════════════════════════════════════════════════════════
# AGENT FLOW — SINGLE TURN
# ═══════════════════════════════════════════════════════════════

class TestSingleTurn:
    """Single-turn: user hỏi → agent gọi tool → trả lời."""

    def test_s1_direct_answer(self, provider, system, tools):
        """S1: User hỏi, agent trả lời ngay (không tool)."""
        provider.add_response(text="Bài lab hôm nay về AI Agent.")
        result = _call(provider, system, tools, "Hôm nay học gì?")
        assert result["status"] == "answered"
        assert "AI Agent" in result["assistant_text"]

    def test_s2_lab_content_flow(self, provider, system, tools):
        """S2: User hỏi nội dung lab → agent gọi get_lab_content → trả lời."""
        provider.add_single_tool("get_lab_content", {"lab_id": "DAY05"},
                                 text="Let me look up the lab content.")
        provider.add_response(text="Bài lab DAY05: Xây dựng AI Agent.")
        result = _call(provider, system, tools, "Nội dung lab DAY05 là gì?")
        assert result["status"] == "answered"
        events = result.get("tool_events", [])
        assert any(e["tool"] == "get_lab_content" for e in events), \
            f"Missing get_lab_content call in {events}"

    def test_s3_create_room_flow(self, provider, system, tools):
        """S3: User yêu cầu tạo nhóm → agent gọi create_group_room."""
        provider.add_single_tool("create_group_room", {
            "room_name": "Nhom 1",
            "member_ids": ["U123", "U456"],
        })
        provider.add_response(text="Đã tạo phòng #group-nhom-1.")
        result = _call(provider, system, tools, "Tạo nhóm tên Nhom 1 gồm U123, U456")
        events = result.get("tool_events", [])
        assert any(e["tool"] == "create_group_room" for e in events)

    def test_s4_multi_tool_flow(self, provider, system, tools):
        """S4: User hỏi → agent gọi nhiều tool cùng lúc → tổng hợp."""
        provider.add_multi_tool([
            ("get_lab_content", {"lab_id": "DAY05"}),
        ])
        provider.add_response(text="Đây là tổng hợp nội dung từ các tài liệu.")
        result = _call(provider, system, tools, "Cho tôi xem toàn bộ nội dung lab DAY05")
        events = result.get("tool_events", [])
        assert len(events) >= 1

    def test_s5_empty_result(self, provider, system, tools):
        """S5: Tool trả về empty → agent nói không tìm thấy."""
        provider.add_single_tool("get_lab_content", {"lab_id": "NOT_EXIST"})
        provider.add_response(text="Rất tiếc, mình không tìm thấy thông tin này.")
        result = _call(provider, system, tools, "Cho xem lab NOT_EXIST")
        events = result.get("tool_events", [])
        assert any(e["tool"] == "get_lab_content" for e in events)
        content_result = events[0].get("result", {})
        assert content_result.get("status") in ("empty", "error")


# ═══════════════════════════════════════════════════════════════
# AGENT FLOW — MULTI TURN
# ═══════════════════════════════════════════════════════════════

class TestMultiTurn:
    """Multi-turn: hội thoại nhiều lượt, context được giữ."""

    def test_m1_two_questions_same_context(self, provider, system, tools):
        """M1: Hỏi 2 câu liên tiếp, context giữa các turn."""
        provider.add_single_tool("get_lab_content", {"lab_id": "DAY05"})
        provider.add_response(text="Bài lab DAY05 về AI Agent.")
        history = []
        r1 = _call(provider, system, tools, "Nội dung lab DAY05?", history=history)
        assert r1["status"] == "answered"
        history.append({"role": "user", "content": "Nội dung lab DAY05?"})
        history.append({"role": "assistant", "content": r1["assistant_text"]})

        provider.add_response(text="Cũng bài lab DAY05 đó thôi bạn.")
        r2 = _call(provider, system, tools, "Thế còn lab này?", history=history)
        assert r2["status"] == "answered"
        assert r2["assistant_text"] != ""

    def test_m2_create_room_then_plan(self, provider, system, tools):
        """M2: Tạo room → vào room → tạo plan (multi-turn flow)."""
        from app import discord_context

        discord_context.set_context(user_id="U1", channel_type="general", lab_id="3")
        provider.add_single_tool("create_group_room", {
            "room_name": "TeamA", "member_ids": ["U1", "U2", "U3"],
        })
        provider.add_response(text="Đã tạo phòng #group-teama.")
        r1 = _call(provider, system, tools, "Tạo nhóm TeamA gồm U1, U2, U3")
        assert r1["status"] == "answered"
        discord_context.clear_context()

        discord_context.set_context(
            user_id="U1", channel_type="group_room", group_id="G01",
            members=[{"id": "U1", "name": "A"}, {"id": "U2", "name": "B"},
                      {"id": "U3", "name": "C"}],
            lab_id="3",
        )
        provider.add_single_tool("generate_group_plan", {
            "lab_id": "3",
            "members": [
                {"user_id": "U1", "role": "PM"},
                {"user_id": "U2", "role": "Backend"},
                {"user_id": "U3", "role": "AI"},
            ],
        })
        provider.add_response(text="Đã tạo plan chi tiết cho nhóm.")
        history = [{"role": "user", "content": "Tạo plan cho nhóm"},
                   {"role": "assistant", "content": "OK"}]
        r2 = _call(provider, system, tools,
                   "Phân công: U1 PM, U2 Backend, U3 AI",
                   history=history)
        events = r2.get("tool_events", [])
        assert any(e["tool"] == "generate_group_plan" for e in events)
        discord_context.clear_context()

    def test_m3_progress_then_update(self, provider, system, tools):
        """M3: Hỏi tiến độ → update task → hỏi lại (3 turns)."""
        from app import discord_context
        discord_context.set_context(
            user_id="U1", channel_type="group_room", group_id="G01",
            members=[{"id": "U1", "name": "A"}], lab_id="3",
        )
        provider.add_single_tool("track_group_progress", {})
        provider.add_response(text="Tiến độ hiện tại: 50%.")
        history = []
        r1 = _call(provider, system, tools, "Nhóm tiến độ sao rồi?", history=history)
        assert r1["status"] == "answered"
        history.append({"role": "user", "content": "Nhóm tiến độ sao rồi?"})
        history.append({"role": "assistant", "content": r1["assistant_text"]})

        provider.add_single_tool("update_group_progress", {
            "task_id": "T1", "status": "completed",
        })
        provider.add_response(text="Đã cập nhật task T1 thành completed.")
        r2 = _call(provider, system, tools, "Mình làm xong T1 rồi", history=history)
        assert any(e["tool"] == "update_group_progress" for e in r2.get("tool_events", []))

        history += [
            {"role": "user", "content": "Mình làm xong T1 rồi"},
            {"role": "assistant", "content": r2["assistant_text"]},
        ]
        provider.add_single_tool("track_group_progress", {})
        provider.add_response(text="Sau update, tiến độ là 60%.")
        r3 = _call(provider, system, tools, "Kiểm tra lại tiến độ", history=history)
        assert any(e["tool"] == "track_group_progress" for e in r3.get("tool_events", []))
        discord_context.clear_context()


# ═══════════════════════════════════════════════════════════════
# TOOL SELECTION TESTS (dựa trên channel type)
# ═══════════════════════════════════════════════════════════════

class TestToolSelection:
    """Agent chọn tool đúng theo channel type."""

    def test_ts1_general_allow_get_lab_content(self, provider, system, tools):
        """General: agent gọi get_lab_content — được phép."""
        from app import discord_context
        discord_context.set_context(user_id="U1", channel_type="general", lab_id="3")

        provider.add_single_tool("get_lab_content", {"lab_id": "3"})
        provider.add_response(text="Nội dung lab 3 đây.")
        r = _call(provider, system, tools, "Lab 3 có gì?")
        assert any(e["tool"] == "get_lab_content" for e in r.get("tool_events", []))
        discord_context.clear_context()

    def test_ts2_general_blocked_group_tool(self, provider, system, tools):
        """General: generate_group_plan bị guardrail chặn."""
        from app import discord_context
        discord_context.set_context(user_id="U1", channel_type="general")

        provider.add_single_tool("generate_group_plan", {
            "lab_id": "3", "members": [{"user_id": "U1", "role": "PM"}],
        })
        provider.add_response(text="Có lỗi guardrail.")
        r = _call(provider, system, tools, "Tạo plan cho nhóm")
        for e in r.get("tool_events", []):
            if e["tool"] == "generate_group_plan":
                assert e.get("result", {}).get("error_code") in ("NO_CONTEXT", "INVALID_INPUT")
                break
        discord_context.clear_context()

    def test_ts3_group_room_list_members(self, provider, system, tools):
        """Group room: agent dùng list_members."""
        from app import discord_context
        discord_context.set_context(
            user_id="U1", channel_type="group_room", group_id="G01",
            members=[{"id": "U1", "name": "A"}], lab_id="3",
        )
        provider.add_single_tool("list_members", {})
        provider.add_response(text="Trong phòng có U1.")
        r = _call(provider, system, tools, "Có những ai trong nhóm?")
        assert any(e["tool"] == "list_members" for e in r.get("tool_events", []))
        discord_context.clear_context()


# ═══════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Agent xử lý các tình huống đặc biệt."""

    def test_e1_unknown_tool(self, provider, system, tools):
        """E1: Agent gọi tool không tồn tại → error result."""
        provider.add_single_tool("non_existent_tool", {"param": "value"})
        provider.add_response(text="Có lỗi xảy ra.")
        r = _call(provider, system, tools, "Làm gì đó với tool lạ")
        for e in r.get("tool_events", []):
            if e["tool"] == "non_existent_tool":
                assert "unknown_tool" in str(e.get("result", {}))
                break

    def test_e2_max_tool_rounds(self, provider, system, tools):
        """E2: Agent gọi tool liên tục → dừng sau max rounds."""
        for _ in range(6):
            provider.add_single_tool("get_lab_content", {"lab_id": "3"})
        r = _call(provider, system, tools, "Làm ơn giúp tôi", max_rounds=3)
        assert r["status"] in ("max_tool_rounds", "answered")

    def test_e3_empty_user_message(self, provider, system, tools):
        """E3: Tin nhắn rỗng → agent vẫn trả lời."""
        provider.add_response(text="Bạn cần mình giúp gì không?")
        r = _call(provider, system, tools, "")
        assert r["status"] == "answered"
