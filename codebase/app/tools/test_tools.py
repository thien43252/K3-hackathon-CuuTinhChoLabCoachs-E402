"""
Script kiểm thử tự động toàn bộ Agent Tools (7 tools hiện tại)
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.tools import (
    get_lab_content,
    create_group_room,
    generate_group_plan,
    get_group_plan,
    track_group_progress,
    update_group_progress,
    analyze_student_issue,
    ALL_TOOLS,
)


def run_tests():
    print("=" * 60)
    print(f"BAT DAU KIEM THU {len(ALL_TOOLS)} AGENT TOOLS")
    print("=" * 60)

    # ── 1. get_lab_content ──
    print("\n[1] Testing get_lab_content...")
    res = get_lab_content(lab_id="DAY05")
    assert res["status"] in ("success", "empty"), f"Failed: {res}"
    res_err = get_lab_content(lab_id="")
    assert res_err.get("error_code") == "INVALID_INPUT", f"Failed empty: {res_err}"
    print(f"  [OK] PASS: get_lab_content (status={res['status']})")

    # ── 2. create_group_room ──
    print("\n[2] Testing create_group_room...")
    res = create_group_room(room_name="lab05-group-01", member_ids=["U123456", "U789012"])
    assert res["status"] == "success", f"Failed: {res}"
    assert "channel_name" in res
    res_part = create_group_room(room_name="lab05-group-01", member_ids=["U123456", "INVALID_999"])
    assert res_part["status"] == "empty"
    assert res_part.get("error_code") == "INVALID_MEMBERS"
    print("  [OK] PASS: create_group_room")

    # ── 3. generate_group_plan ──
    print("\n[3] Testing generate_group_plan (no context → NO_CONTEXT)...")
    res = generate_group_plan(
        lab_id="DAY05",
        members=[],
    )
    # Không có Discord context → NO_CONTEXT là đúng
    assert res.get("error_code") in ("NO_CONTEXT", "INVALID_MEMBERS"), f"Unexpected: {res}"
    print(f"  [OK] PASS: generate_group_plan (error_code={res.get('error_code')})")

    # ── 4. get_group_plan ──
    print("\n[4] Testing get_group_plan (no context → NO_CONTEXT)...")
    res = get_group_plan()
    assert res.get("error_code") == "NO_CONTEXT", f"Unexpected: {res}"
    print(f"  [OK] PASS: get_group_plan (error_code={res.get('error_code')})")

    # ── 5. track_group_progress ──
    print("\n[5] Testing track_group_progress (no context → NO_CONTEXT)...")
    res = track_group_progress()
    assert res.get("error_code") == "NO_CONTEXT", f"Unexpected: {res}"
    print(f"  [OK] PASS: track_group_progress (error_code={res.get('error_code')})")

    # ── 6. update_group_progress ──
    print("\n[6] Testing update_group_progress (no context → NO_CONTEXT)...")
    res = update_group_progress(task_id="T1", status="completed")
    assert res.get("error_code") == "NO_CONTEXT", f"Unexpected: {res}"
    print(f"  [OK] PASS: update_group_progress (error_code={res.get('error_code')})")

    # ── 7. analyze_student_issue ──
    print("\n[7] Testing analyze_student_issue (no context → INVALID_INPUT)...")
    res = analyze_student_issue(task_id="T1",
                                issue_description="Bị lỗi kết nối database")
    # Không có user_id context → INVALID_INPUT
    assert res.get("error_code") in ("INVALID_INPUT", "success"), f"Unexpected: {res}"
    print(f"  [OK] PASS: analyze_student_issue (error_code={res.get('error_code')})")

    # ── Summary ──
    print("\n" + "=" * 60)
    print(f"TAT CA {len(ALL_TOOLS)} TOOLS DA KIEM TRA (khong crash)!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
