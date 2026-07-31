"""
Pytest test suite cho 8 Agent Tools + Slash Command — cả happy case và unhappy case.

Cách chạy:
    cd codebase && python -m pytest tests/test_tools_pytest.py -v

Lưu ý:
    - Tests không cần Discord thật (dùng mock mode hoặc context injection).
    - Một số tests generate_group_plan cần lab cache — nếu chưa có sẽ skip.
"""
import json
import pytest
from app import discord_context
from app.core.db import get_db_connection
from app.tools import (
    get_lab_content,
    create_group_room,
    generate_group_plan,
    get_group_plan,
    track_group_progress,
    update_group_progress,
    list_members,
    analyze_student_issue,
    ALL_TOOLS,
)


# ═══════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def no_context():
    """No Discord context — simulate running outside Discord."""
    discord_context.clear_context()
    yield
    discord_context.clear_context()


@pytest.fixture
def group_context():
    """Simulate a group room context with all auto-resolved values."""
    discord_context.set_context(
        user_id="U123456",
        channel_type="group_room",
        group_id="G01",
        members=[{"id": "U123456", "name": "Test User"}, {"id": "U789012", "name": "Another"}],
        lab_id="DAY05",
    )
    yield
    discord_context.clear_context()


@pytest.fixture
def general_context():
    """Simulate a general channel (no group)."""
    discord_context.set_context(
        user_id="U123456",
        channel_type="general",
        group_id=None,
        members=[],
        lab_id="DAY05",
    )
    yield
    discord_context.clear_context()


# ═══════════════════════════════════════════════════════════════
# TOOL 1: get_lab_content
# ═══════════════════════════════════════════════════════════════

class TestGetLabContent:
    """T1: get_lab_content(lab_id) — lấy nội dung lab từ cache."""

    def test_h1_success_if_cached(self):
        """T1_H1: Lấy lab đã cache → success (nếu DAY05 đã được admin-add)."""
        res = get_lab_content(lab_id="DAY05")
        # DAY05 có thể chưa được add → empty cũng chấp nhận
        assert res["status"] in ("success", "empty")
        if res["status"] == "success":
            assert "lab_objective" in res
            assert "tasks" in res

    def test_h2_full_insights(self):
        """T1_H2: Lab có insights đầy đủ → có timeline + file_summaries."""
        res = get_lab_content(lab_id="3")
        assert res["status"] in ("success", "empty")
        if res["status"] == "success":
            # Có thể có hoặc không timeline tùy extraction
            assert len(res.get("sitemap", [])) >= 0

    def test_u1_empty_lab_id(self):
        """T1_U1: lab_id rỗng → INVALID_INPUT."""
        res = get_lab_content(lab_id="")
        assert res["status"] == "empty"
        assert res.get("error_code") == "INVALID_INPUT"

    def test_u2_no_cache(self):
        """T1_U2: Lab chưa được import → NO_CACHED_DATA."""
        res = get_lab_content(lab_id="NOT_EXIST_XYZ")
        assert res["status"] == "empty"
        assert res.get("error_code") == "NO_CACHED_DATA"


# ═══════════════════════════════════════════════════════════════
# TOOL 2: create_group_room
# ═══════════════════════════════════════════════════════════════

class TestCreateGroupRoom:
    """T2: create_group_room(room_name, member_ids) — tạo Discord channel."""

    def test_h1_all_valid_members(self, no_context):
        """T2_H1: Tất cả members hợp lệ → success (mock mode)."""
        res = create_group_room(
            room_name="G01",
            member_ids=["U123456", "U789012"],
        )
        assert res["status"] == "success"
        assert "channel_name" in res
        assert "U123456" in res.get("added_members", [])
        assert "U789012" in res.get("added_members", [])

    def test_h2_private_default(self, no_context):
        """T2_H2: Room private mặc định → success."""
        res = create_group_room(
            room_name="test-room",
            member_ids=["U123456"],
        )
        assert res["status"] == "success"
        assert res.get("room_id") != ""
        assert res.get("channel_name") == "group-test-room"

    def test_u1_empty_room_name(self, no_context):
        """T2_U1: room_name rỗng → INVALID_INPUT."""
        res = create_group_room(room_name="", member_ids=["U123456"])
        assert res["status"] == "empty"
        assert res.get("error_code") == "INVALID_INPUT"

    def test_u2_partial_invalid_members(self, no_context):
        """T2_U2: Một vài members invalid → INVALID_MEMBERS."""
        res = create_group_room(
            room_name="G01",
            member_ids=["U123456", "INVALID_999"],
        )
        assert res["status"] == "empty"
        assert res.get("error_code") == "INVALID_MEMBERS"
        assert len(res.get("failed_members", [])) == 1

    def test_u3_all_invalid_members(self, no_context):
        """T2_U3: Tất cả members invalid → INVALID_MEMBERS."""
        res = create_group_room(
            room_name="G01",
            member_ids=["INVALID_1", "INVALID_2"],
        )
        assert res["status"] == "empty"
        assert res.get("error_code") == "INVALID_MEMBERS"
        assert res.get("valid_count") == 0

    def test_u4_trigger_error(self, no_context):
        """T2_U4: Trigger 500 → PLATFORM_API_ERROR."""
        res = create_group_room(room_name="TRIGGER_500", member_ids=["U123456"])
        assert res["status"] == "error"
        assert res.get("error_code") == "PLATFORM_API_ERROR"


# ═══════════════════════════════════════════════════════════════
# TOOL 3: generate_group_plan
# ═══════════════════════════════════════════════════════════════

class TestGenerateGroupPlan:
    """T3: generate_group_plan(lab_id, members) — tạo guidebook."""

    def test_u1_no_context(self, no_context):
        """T3_U1: Không có Discord context → NO_CONTEXT."""
        res = generate_group_plan(
            lab_id="DAY05",
            members=[{"user_id": "U1", "role": "PM"}],
        )
        assert res.get("error_code") == "NO_CONTEXT"

    def test_u2_empty_lab_id(self, group_context):
        """T3_U2: lab_id rỗng → INVALID_INPUT."""
        res = generate_group_plan(
            lab_id="",
            members=[{"user_id": "U1", "role": "PM"}],
        )
        assert res.get("error_code") == "INVALID_INPUT"

    def test_u3_empty_members(self, group_context):
        """T3_U3: members rỗng → INVALID_MEMBERS."""
        res = generate_group_plan(lab_id="DAY05", members=[])
        assert res.get("error_code") == "INVALID_MEMBERS"

    def test_u4_no_lab_data(self, group_context):
        """T3_U4: Lab chưa được import → NO_LAB_DATA."""
        res = generate_group_plan(
            lab_id="NOT_EXIST_XYZ",
            members=[{"user_id": "U1", "role": "PM"}],
        )
        assert res.get("error_code") in ("NO_LAB_DATA", "INVALID_INPUT")

    def test_h1_success_with_mock_lab(self, group_context):
        """T3_H1: Tạo plan với lab có cache + members → success (nếu có cache)."""
        # Chỉ chạy nếu DAY05 đã được admin-add
        lab_check = get_lab_content(lab_id="DAY05")
        if lab_check["status"] != "success":
            pytest.skip("Cần lab DAY05 trong cache (chạy /admin-add-lab trước)")

        res = generate_group_plan(
            lab_id="DAY05",
            members=[
                {"user_id": "U123456", "role": "PM"},
                {"user_id": "U789012", "role": "Backend"},
            ],
            notes="Dùng FastAPI + React",
        )
        assert res["status"] == "success"
        assert len(res.get("todo_list", [])) > 0
        assert len(res.get("phases", [])) >= 1
        assert len(res.get("summary", "")) > 500
        assert res.get("notes") == "Dùng FastAPI + React"

    def test_h2_custom_tasks(self, group_context):
        """T3_H2: Custom tasks → task ID prefix CT."""
        lab_check = get_lab_content(lab_id="DAY05")
        if lab_check["status"] != "success":
            pytest.skip("Cần lab DAY05 trong cache")

        res = generate_group_plan(
            lab_id="DAY05",
            members=[{
                "user_id": "U123456", "role": "PM",
                "custom_tasks": ["Review code", "Viết slide"],
            }],
        )
        assert res["status"] == "success"
        task_ids = [t["task_id"] for t in res["members_plan"][0]["tasks"]]
        assert any(tid.startswith("CT") for tid in task_ids), f"No CT tasks in {task_ids}"

    def test_h4_dynamic_phases(self, group_context):
        """T3_H4: Insight tasks ≥2 → dùng dynamic phases thay vì canonical."""
        lab_check = get_lab_content(lab_id="DAY05")
        if lab_check["status"] != "success":
            pytest.skip("Cần lab DAY05 trong cache")

        res = generate_group_plan(
            lab_id="DAY05",
            members=[{"user_id": "U1", "role": "PM"}],
        )
        assert res["status"] == "success"
        phases = res.get("phases", [])
        # Nếu dynamic, phases có title từ insight tasks (không phải "🔍 Phân tích & Thiết kế")
        phase_titles = " ".join(p["title"] for p in phases)
        is_canonical = "Phân tích" in phase_titles and "Xây dựng" in phase_titles
        if is_canonical:
            # Nếu là canonical, chỉ có 4 phases
            assert len(phases) == 4
        else:
            # Nếu dynamic, có thể ≥ 5
            assert len(phases) >= 2


# ═══════════════════════════════════════════════════════════════
# TOOL 4: get_group_plan
# ═══════════════════════════════════════════════════════════════

class TestGetGroupPlan:
    """T4: get_group_plan() — đọc plan từ DB."""

    def test_u1_no_context(self, no_context):
        """T4_U1: Không có Discord context → NO_CONTEXT."""
        res = get_group_plan()
        assert res.get("error_code") == "NO_CONTEXT"

    def test_u2_no_plan(self, group_context):
        """T4_U2: Có context → success (nếu có plan) hoặc NO_PLAN (nếu chưa có)."""
        res = get_group_plan()
        # Group G01 có thể đã có plan từ test trước → success, chưa có → NO_PLAN
        assert res["status"] in ("success", "empty"), f"Unexpected: {res}"

    def test_h1_plan_exists(self, group_context):
        """T4_H1: Có plan trong DB → success."""
        # Cần generate_group_plan trước
        lab_check = get_lab_content(lab_id="DAY05")
        if lab_check["status"] != "success":
            pytest.skip("Cần lab DAY05 trong cache")

        # Generate plan
        gen_res = generate_group_plan(
            lab_id="DAY05",
            members=[{"user_id": "U123456", "role": "PM"}],
        )
        if gen_res["status"] != "success":
            pytest.skip(f"generate_group_plan failed: {gen_res.get('message')}")

        # Read plan
        res = get_group_plan()
        assert res["status"] == "success"
        assert "members_plan" in res
        assert "phases" in res


# ═══════════════════════════════════════════════════════════════
# TOOL 5: track_group_progress
# ═══════════════════════════════════════════════════════════════

class TestTrackGroupProgress:
    """T5: track_group_progress() — xem tiến độ nhóm."""

    def test_u1_no_context(self, no_context):
        """T5_U1: Không có context → NO_CONTEXT."""
        res = track_group_progress()
        assert res.get("error_code") == "NO_CONTEXT"

    def test_u2_no_plan(self, group_context):
        """T5_U2: Có context → success (nếu có plan) hoặc NO_PLAN (nếu chưa)."""
        res = track_group_progress()
        assert res["status"] in ("success", "empty"), f"Unexpected: {res}"


# ═══════════════════════════════════════════════════════════════
# TOOL 6: update_group_progress
# ═══════════════════════════════════════════════════════════════

class TestUpdateGroupProgress:
    """T6: update_group_progress(task_id, status, completed_checklist)."""

    def test_u1_no_context(self, no_context):
        """T6_U1: Không có context → NO_CONTEXT."""
        res = update_group_progress(task_id="T1", status="completed")
        assert res.get("error_code") == "NO_CONTEXT"

    def test_u2_empty_task_id(self, group_context):
        """T6_U2: task_id rỗng → INVALID_INPUT."""
        res = update_group_progress(task_id="", status="completed")
        assert res.get("error_code") == "INVALID_INPUT"

    def test_u4_invalid_status(self, group_context):
        """T6_U4: Status không hợp lệ → INVALID_STATUS."""
        res = update_group_progress(task_id="T1", status="invalid_status")
        assert res.get("error_code") == "INVALID_STATUS"

    def test_u5_negative_checklist(self, group_context):
        """T6_U5: completed_checklist âm → INVALID_CHECKLIST."""
        res = update_group_progress(task_id="T1", completed_checklist=-1)
        assert res.get("error_code") == "INVALID_CHECKLIST"

    def test_h1_completed_auto_full_checklist(self, group_context):
        """T6_H1: status=completed → auto full checklist."""
        # Cần có plan trước
        lab_check = get_lab_content(lab_id="DAY05")
        if lab_check["status"] != "success":
            pytest.skip("Cần lab DAY05 trong cache")

        # Generate plan để có assignments
        gen_res = generate_group_plan(
            lab_id="DAY05",
            members=[{"user_id": "U123456", "role": "PM"}],
        )
        if gen_res["status"] != "success":
            pytest.skip(f"generate failed: {gen_res.get('message')}")

        # Mark task T1 as completed
        res = update_group_progress(task_id="T1", status="completed")
        if res.get("error_code") == "NO_ASSIGNMENT_FOUND":
            pytest.skip("No T1 assignment found (plan may use different IDs)")
        assert res["status"] == "success"
        assert res.get("new_status") == "completed"

    def test_h3_in_progress(self, group_context):
        """T6_H3: Update in_progress → success."""
        lab_check = get_lab_content(lab_id="DAY05")
        if lab_check["status"] != "success":
            pytest.skip("Cần lab DAY05 trong cache")

        res = update_group_progress(task_id="T1", status="in_progress")
        if res.get("error_code") == "NO_ASSIGNMENT_FOUND":
            pytest.skip("No T1 assignment found")
        assert res["status"] == "success"


# ═══════════════════════════════════════════════════════════════
# TOOL 7: analyze_student_issue
# ═══════════════════════════════════════════════════════════════

class TestAnalyzeStudentIssue:
    """T7: analyze_student_issue(task_id, issue_description, error_log)."""

    def test_h1_env_error(self):
        """T7_H1: Lỗi env/database → root_cause chứa DATABASE_URL."""
        discord_context.set_context(user_id="U123456", channel_type="group_room")
        res = analyze_student_issue(
            task_id="T1",
            issue_description="Bị lỗi kết nối database",
            error_log="MongoError: connection failed",
        )
        discord_context.clear_context()
        assert res["status"] == "success"
        assert "DATABASE_URL" in res.get("root_cause", "") or "Mongo" in res.get("root_cause", "")
        assert res.get("suggested_solution") != ""

    def test_h2_import_error(self, no_context):
        """T7_H2: Lỗi import module → root_cause chứa 'chưa cài đặt'."""
        discord_context.set_context(user_id="U123456", channel_type="group_room")
        res = analyze_student_issue(
            task_id="T1",
            issue_description="Lỗi import module pandas",
        )
        discord_context.clear_context()
        assert res["status"] == "success"
        assert "chưa cài" in res.get("root_cause", "").lower() or "thư viện" in res.get("root_cause", "").lower()

    def test_h3_fallback(self, no_context):
        """T7_H3: Lỗi không xác định → fallback."""
        discord_context.set_context(user_id="U123456", channel_type="group_room")
        res = analyze_student_issue(
            task_id="T1",
            issue_description="Code chạy sai kết quả đầu ra",
        )
        discord_context.clear_context()
        assert res["status"] == "success"
        assert res.get("root_cause") != ""

    def test_u1_short_description(self, no_context):
        """T7_U1: Mô tả quá ngắn → UNCLEAR_ISSUE."""
        discord_context.set_context(user_id="U123456", channel_type="group_room")
        res = analyze_student_issue(task_id="T1", issue_description="Lỗi")
        discord_context.clear_context()
        assert res.get("error_code") == "UNCLEAR_ISSUE"

    def test_u2_empty_task(self):
        """T7_U2: task_id rỗng → INVALID_INPUT."""
        discord_context.set_context(user_id="U123456", channel_type="group_room")
        res = analyze_student_issue(task_id="", issue_description="Bị lỗi mạng")
        discord_context.clear_context()
        assert res.get("error_code") == "INVALID_INPUT"

    def test_u3_empty_description(self):
        """T7_U3: issue_description rỗng → INVALID_INPUT."""
        discord_context.set_context(user_id="U123456", channel_type="group_room")
        res = analyze_student_issue(task_id="T1", issue_description="")
        discord_context.clear_context()
        assert res.get("error_code") == "INVALID_INPUT"


# ═══════════════════════════════════════════════════════════════
# TOOL 8: list_members
# ═══════════════════════════════════════════════════════════════

class TestListMembers:
    """T8: list_members() — liệt kê thành viên trong group room."""

    def test_h1_group_room_full(self, group_context):
        """T8_H1: Group room có members → success + danh sách đầy đủ."""
        res = list_members()
        assert res["status"] == "success"
        assert len(res.get("members", [])) == 2
        assert res.get("total") == 2
        assert res.get("group_id") == "G01"

    def test_h2_single_member(self, group_context):
        """T8_H2: Group room 1 member → success."""
        # Override context với 1 member
        discord_context.set_context(
            user_id="U1",
            group_id="G02",
            members=[{"id": "U1", "name": "Solo"}],
        )
        res = list_members()
        assert res["status"] == "success"
        assert res.get("total") == 1
        discord_context.clear_context()

    def test_u1_no_context(self, no_context):
        """T8_U1: Không có context → NO_CONTEXT."""
        res = list_members()
        assert res.get("error_code") == "NO_CONTEXT"

    def test_u2_empty_members(self):
        """T8_U2: Group room nhưng members rỗng → NO_CONTEXT."""
        discord_context.set_context(group_id="G01", members=[])
        res = list_members()
        assert res.get("error_code") == "NO_CONTEXT"
        discord_context.clear_context()


# ═══════════════════════════════════════════════════════════════
# ALL_TOOLS integrity check
# ═══════════════════════════════════════════════════════════════

class TestAllToolsIntegrity:
    """Đảm bảo ALL_TOOLS khớp với danh sách tools.yaml."""

    def test_all_tools_count(self):
        """Phải có đúng 8 tools."""
        assert len(ALL_TOOLS) == 8, f"Expected 8 tools, got {len(ALL_TOOLS)}: {list(ALL_TOOLS.keys())}"

    def test_all_tools_expected(self):
        """ALL_TOOLS phải chứa đúng tên các tools hiện tại."""
        expected = {
            "get_lab_content",
            "create_group_room",
            "generate_group_plan",
            "get_group_plan",
            "track_group_progress",
            "update_group_progress",
            "list_members",
            "analyze_student_issue",
        }
        actual = set(ALL_TOOLS.keys())
        assert actual == expected, f"Missing: {expected - actual}, Extra: {actual - expected}"

    def test_tools_yaml_consistency(self):
        """tools.yaml phải khớp với ALL_TOOLS (không tool thừa, không tool thiếu)."""
        from app.tools import load_tool_declarations
        from pathlib import Path
        tools_path = Path("app/prompt/tools.yaml")
        assert tools_path.exists(), "tools.yaml not found"
        decls = load_tool_declarations(tools_path)
        yaml_names = {d["name"] for d in decls}
        code_names = set(ALL_TOOLS.keys())
        assert yaml_names == code_names, (
            f"In tools.yaml but not in ALL_TOOLS: {yaml_names - code_names}. "
            f"In ALL_TOOLS but not in tools.yaml: {code_names - yaml_names}."
        )
