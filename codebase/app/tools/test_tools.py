"""
Script kiểm thử tự động toàn bộ 15 Agent Tools
"""

import sys
import os
from pathlib import Path

# Cấu hình UTF-8 cho stdout trên Windows
sys.stdout.reconfigure(encoding='utf-8')

# Thêm codebase vào PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.tools import (
    upload_lab_material,
    codebase_indexer,
    RAG_search,
    get_user_context,
    create_group_room,
    send_message,
    send_notification,
    parse_lab_requirements,
    assign_task,
    track_group_progress,
    generate_reflection,
    schedule_reminder,
    extend_deadline,
    analyze_student_issue,
    fetch_peer_solution,
    ALL_TOOLS
)

def run_tests():
    print("=" * 60)
    print("BAT DAU KIEM THU TOAN BO 15 AGENT TOOLS")
    print("=" * 60)

    # 1. upload_lab_material
    print("\n[1] Testing upload_lab_material...")
    res = upload_lab_material(lab_id="LAB05_TEST", title="Lab Test", type="group", description="Test desc")
    assert res["status"] == "success", f"Failed: {res}"
    res_err = upload_lab_material(lab_id="", title="", type="invalid", description="")
    assert res_err["status"] == "empty", f"Failed error case: {res_err}"
    print("  [OK] PASS: upload_lab_material")

    # 2. codebase_indexer
    print("\n[2] Testing codebase_indexer...")
    res = codebase_indexer(lab_id="LAB05_TEST")
    assert res["status"] == "success", f"Failed: {res}"
    res_err = codebase_indexer(lab_id="NON_EXISTENT_ID")
    assert res_err["status"] == "empty", f"Failed error case: {res_err}"
    print("  [OK] PASS: codebase_indexer")

    # 3. RAG_search
    print("\n[3] Testing RAG_search...")
    res = RAG_search(query="kết nối database", lab_id="LAB05_TEST")
    assert res["status"] in ["success", "empty"], f"Failed: {res}"
    res_err = RAG_search(query="TRIGGER_500", lab_id="LAB05_TEST")
    assert res_err["status"] == "error", f"Failed error case: {res_err}"
    print("  [OK] PASS: RAG_search")

    # 4. get_user_context
    print("\n[4] Testing get_user_context...")
    res = get_user_context(user_id="U123456")
    assert res["status"] == "success", f"Failed: {res}"
    res_err = get_user_context(user_id="TRIGGER_500")
    assert res_err["status"] == "error", f"Failed error case: {res_err}"
    print("  [OK] PASS: get_user_context")

    # 5. create_group_room
    print("\n[5] Testing create_group_room...")
    res = create_group_room(room_name="lab05-group-01", member_ids=["U123456", "U789012"])
    assert res["status"] == "success", f"Failed: {res}"
    res_part = create_group_room(room_name="lab05-group-01", member_ids=["U123456", "INVALID_999"])
    assert res_part["status"] == "partial_success", f"Failed partial case: {res_part}"
    print("  [OK] PASS: create_group_room")

    # 6. send_message
    print("\n[6] Testing send_message...")
    res = send_message(target_id="C998877", message="Hello Team")
    assert res["status"] == "success", f"Failed: {res}"
    res_err = send_message(target_id="BLOCKED_USER", message="Hi")
    assert res_err["status"] == "error", f"Failed error case: {res_err}"
    print("  [OK] PASS: send_message")

    # 7. send_notification
    print("\n[7] Testing send_notification...")
    res = send_notification(room_id="C998877", user_ids_to_tag=["U123456"], content="Urgent update")
    assert res["status"] == "success", f"Failed: {res}"
    print("  [OK] PASS: send_notification")

    # 8. parse_lab_requirements
    print("\n[8] Testing parse_lab_requirements...")
    res = parse_lab_requirements(lab_id="LAB05_GROUP", member_count=3)
    assert res["status"] == "success", f"Failed: {res}"
    res_err = parse_lab_requirements(lab_id="UNPARSEABLE", member_count=3)
    assert res_err["status"] == "empty", f"Failed error case: {res_err}"
    print("  [OK] PASS: parse_lab_requirements")

    # 9. assign_task
    print("\n[9] Testing assign_task...")
    res = assign_task(group_id="G01", assignments=[{"user_id": "U123456", "task_id": "T1"}])
    assert res["status"] == "success", f"Failed: {res}"
    res_err = assign_task(group_id="G01", assignments=[{"user_id": "U123456", "task_id": "T99"}])
    assert res_err["status"] == "empty", f"Failed error case: {res_err}"
    print("  [OK] PASS: assign_task")

    # 10. track_group_progress
    print("\n[10] Testing track_group_progress...")
    res = track_group_progress(group_id="G01")
    assert res["status"] == "success", f"Failed: {res}"
    res_err = track_group_progress(group_id="UNASSIGNED_G99")
    assert res_err["status"] == "empty", f"Failed error case: {res_err}"
    print("  [OK] PASS: track_group_progress")

    # 11. generate_reflection
    print("\n[11] Testing generate_reflection...")
    res = generate_reflection(user_id="U123456", lab_id="LAB05_GROUP")
    assert res["status"] == "success", f"Failed: {res}"
    res_err = generate_reflection(user_id="INCOMPLETE_U", lab_id="LAB05_GROUP")
    assert res_err["status"] == "empty", f"Failed error case: {res_err}"
    print("  [OK] PASS: generate_reflection")

    # 12. schedule_reminder
    print("\n[12] Testing schedule_reminder...")
    res = schedule_reminder(target_id="U123456", remind_at="2028-12-31T15:00:00Z", message="Deadline soon")
    assert res["status"] == "success", f"Failed: {res}"
    res_err = schedule_reminder(target_id="U123456", remind_at="2020-01-01T15:00:00Z", message="Past time")
    assert res_err["status"] == "error", f"Failed error case: {res_err}"
    print("  [OK] PASS: schedule_reminder")

    # 13. extend_deadline
    print("\n[13] Testing extend_deadline...")
    res = extend_deadline(task_id="T1", user_id="U123456", extra_minutes=30)
    assert res["status"] == "success", f"Failed: {res}"
    # Test extension limit
    extend_deadline(task_id="T_MAX", user_id="U123456", extra_minutes=30)
    extend_deadline(task_id="T_MAX", user_id="U123456", extra_minutes=30)
    res_limit = extend_deadline(task_id="T_MAX", user_id="U123456", extra_minutes=30)
    assert res_limit["status"] == "error", f"Failed limit case: {res_limit}"
    print("  [OK] PASS: extend_deadline")

    # 14. analyze_student_issue
    print("\n[14] Testing analyze_student_issue...")
    res = analyze_student_issue(user_id="U123456", task_id="T1", issue_description="Bị lỗi kết nối DATABASE_URL trong file env", error_log="MongoError: connection failed")
    assert res["status"] == "success", f"Failed: {res}"
    res_err = analyze_student_issue(user_id="U123456", task_id="T1", issue_description="Lỗi")
    assert res_err["status"] == "empty", f"Failed error case: {res_err}"
    print("  [OK] PASS: analyze_student_issue")

    # 15. fetch_peer_solution
    print("\n[15] Testing fetch_peer_solution...")
    res = fetch_peer_solution(group_id="G01", current_task_id="T2", requesting_user_id="U789012")
    assert res["status"] == "success", f"Failed: {res}"
    res_err = fetch_peer_solution(group_id="NO_PEER_G", current_task_id="T2", requesting_user_id="U789012")
    assert res_err["status"] == "empty", f"Failed error case: {res_err}"
    print("  [OK] PASS: fetch_peer_solution")

    print("\n" + "=" * 60)
    print(f"TAT CA {len(ALL_TOOLS)} TOOLS DA VUOT QUA TEST THANH CONG!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
