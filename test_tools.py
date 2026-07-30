import sys
import codecs
sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
from app.tools import (
    upload_lab_material,
    get_user_context,
    assign_task,
    track_group_progress,
    extend_deadline,
    fetch_peer_solution,
    parse_lab_requirements
)

print("--- 1. KIỂM THỬ DATABASE TOOLS ---")

# Test upload lab
success = upload_lab_material(
    lab_id="LAB_01",
    title="Test Lab",
    type="group",
    description="This is a test lab",
    lecture_files=["lecture.pdf"],
    codebase_repo_url="https://github.com/test/repo"
)
print(f"upload_lab_material: {'Thành công' if success else 'Thất bại'}")

# Test get context
context = get_user_context("user_123", "2026-07-30")
print(f"get_user_context: {context}")

# Test assign task
assign_success = assign_task(
    group_id="group_1",
    assignments=[
        {"task_id": "task_1", "user_id": "user_1", "deadline": "2026-08-01"},
        {"task_id": "task_2", "user_id": "user_2", "deadline": "2026-08-01"}
    ]
)
print(f"assign_task: {'Thành công' if assign_success else 'Thất bại'}")

# Test track progress
progress = track_group_progress("group_1")
print(f"track_group_progress: {progress}")

# Test extend deadline
ext_result = extend_deadline("task_1", "user_1", extra_minutes=60, reason="Máy tính hỏng")
print(f"extend_deadline (lần 1): {ext_result}")

# Test peer solution
peer = fetch_peer_solution("group_1", "task_1", "user_2")
print(f"fetch_peer_solution: {peer} (Dự kiến None vì chưa ai hoàn thành)")


print("\n--- 2. KIỂM THỬ AI TOOLS ---")
print("Lưu ý: API AI sẽ văng lỗi Authentication nếu bạn chưa điền GEMINI_API_KEY thật vào file .env")
try:
    reqs = parse_lab_requirements("LAB_01", 3)
    print(f"parse_lab_requirements: {reqs}")
except Exception as e:
    print(f"Lỗi gọi AI (có thể do chưa có KEY hợp lệ): {e}")

print("\nĐã chạy xong Script Test!")
