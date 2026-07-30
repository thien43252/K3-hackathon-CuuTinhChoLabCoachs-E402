"""
Module chứa các công cụ Quản lý Nhiệm vụ & Tiến độ (Task Management Tools).
Sử dụng CSDL SQLite thực tế (`assignments`, `lab_materials`, `users`, `group_plans`).
Bao gồm:
1. generate_group_plan (Create / Update — xoá cũ + ghi mới)
2. get_group_plan (Read)
3. track_group_progress
4. update_group_progress
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.services.repo_service import LabContentService

from app.core.db import get_db_connection


class MemberRole(BaseModel):
    user_id: str = Field(..., description="ID học viên")
    role: str = Field(..., description="Vai trò trong nhóm (ví dụ: Frontend, Backend, PM)")
    custom_tasks: Optional[List[str]] = Field(default=None, description="Danh sách task cụ thể (nếu có)")


class GenerateGroupPlanInput(BaseModel):
    lab_id: str = Field(..., description="Mã bài lab")
    group_id: str = Field(..., description="Mã nhóm")
    members: List[MemberRole] = Field(..., description="Danh sách thành viên kèm vai trò")
    notes: Optional[str] = Field(default=None, description="Ghi chú thêm từ nhóm (ví dụ: công nghệ, hướng tiếp cận)")


class AssignmentItem(BaseModel):
    user_id: str = Field(..., description="ID học viên được phân công")
    task_id: str = Field(..., description="Mã task được phân công")
    deadline: Optional[str] = Field(default=None, description="Thời hạn hoàn thành (ISO string)")


class ParseLabRequirementsInput(BaseModel):
    lab_id: str = Field(..., description="Mã bài lab cần phân tích")
    member_count: int = Field(..., description="Số lượng thành viên trong nhóm")
    duration_hours: Optional[float] = Field(default=2.0, description="Thời lượng làm lab dự kiến (tính theo giờ)")


class AssignTaskInput(BaseModel):
    group_id: str = Field(..., description="Mã định danh nhóm")
    assignments: List[AssignmentItem] = Field(..., description="Danh sách phân công: [{ user_id, task_id, deadline }]")


class GetGroupPlanInput(BaseModel):
    group_id: str = Field(..., description="Mã nhóm cần lấy plan")


class TrackGroupProgressInput(BaseModel):
    group_id: str = Field(..., description="Mã nhóm cần kiểm tra tiến độ")


class UpdateGroupProgressInput(BaseModel):
    group_id: str = Field(..., description="Mã nhóm")
    user_id: str = Field(..., description="Mã học viên")
    task_id: str = Field(..., description="Mã task cần cập nhật")
    status: Optional[str] = Field(default=None, description="Trạng thái mới ('in_progress' hoặc 'completed')")
    completed_checklist: Optional[int] = Field(default=None, description="Số checklist đã hoàn thành")


class GenerateReflectionInput(BaseModel):
    user_id: str = Field(..., description="Mã học viên")
    lab_id: str = Field(..., description="Mã bài lab")


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def _extract_checklist_items(content: str) -> list:
    """Extract checklist từ markdown content (lines bắt đầu bằng -, *, [ ], 1.)."""
    items = []
    for line in content.split("\n"):
        s = line.strip()
        if not s:
            continue
        if s.startswith(("- ", "* ", "+ ")):
            clean = s[2:].strip()
            if len(clean) > 4:
                items.append(clean)
        elif s.startswith("[") and "] " in s[:4]:
            clean = s[s.index("]") + 1:].strip()
            if len(clean) > 4:
                items.append(clean)
        elif s[0].isdigit() and ". " in s[:4]:
            clean = s[s.index(". ") + 2:].strip()
            if len(clean) > 4:
                items.append(clean)
    return items[:8]


def _extract_deliverable(content: str) -> str:
    """Tìm deliverable / output / nộp từ content."""
    for kw in ["deliverable", "đầu ra", "output", "nộp", "submit", "kết quả"]:
        for line in content.split("\n"):
            if kw in line.lower():
                return line.strip().lstrip("-* 0123456789. ")[:200]
    return ""


def _split_into_checklist(description: str, task_name: str) -> list:
    """Chia description thành checklist items nếu có thể."""
    items = _extract_checklist_items(description)
    if not items:
        sentences = [s.strip() for s in description.replace(". ", ".\n").split("\n") if len(s.strip()) > 10]
        items = sentences[:4]
    if not items:
        items = [task_name]
    return items


def _gen_task_id(phases: list, existing: list) -> str:
    used = {t.get("task_id", "") for t in existing}
    i = 1
    while f"T{i}" in used:
        i += 1
    return f"T{i}"


# ═══════════════════════════════════════════════════════════════
# TOOL FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def parse_lab_requirements(
    lab_id: str,
    member_count: int,
    duration_hours: Optional[float] = 2.0
) -> Dict[str, Any]:
    """[DEPRECATED] Giữ lại để tránh lỗi import cũ, không export làm tool nữa."""
    return {"status": "empty", "message": "Tool này đã bị deprecate. Dùng get_lab_content + generate_group_plan."}


def assign_task(group_id: str, assignments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """[DEPRECATED] Giữ lại để tránh lỗi import cũ, không export làm tool nữa."""
    return {"status": "empty", "message": "Tool này đã bị deprecate. Dùng generate_group_plan để gán task."}


def generate_reflection(user_id: str, lab_id: str) -> Dict[str, Any]:
    """[DEPRECATED] Giữ lại để tránh lỗi import cũ, không export làm tool nữa."""
    return {"status": "empty", "message": "Tool này đã bị deprecate."}


# ═══════════════════════════════════════════════════════════════
# ACTIVE TOOLS
# ═══════════════════════════════════════════════════════════════

def generate_group_plan(
    lab_id: str,
    group_id: str,
    members: List[Dict[str, Any]],
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    1. generate_group_plan
    Mô tả: Tạo kế hoạch chi tiết cho nhóm làm lab, đào sâu vào toàn bộ
    nội dung lab từ cache để xây dựng plan có chiều sâu.

    Algorithm:
      1. Load toàn bộ dữ liệu lab từ cache (insights + documents + sitemap)
      2. Extract các HIGH-LEVEL phases từ document structure (chỉ H2) —
         mỗi phase tương ứng 1 giai đoạn chính của lab
      3. Với mỗi phase, từ nội dung document extract: mục tiêu, checklist gốc
      4. Phân công: dùng template-based role assignment — mỗi role type
         có một bộ trách nhiệm mẫu, áp vào từng phase
      5. Tự động tạo checklist chi tiết cho từng (role, phase)
      6. Ghi vào DB: group_plans + assignments
    """
    try:
        if not lab_id or not lab_id.strip() or not group_id or not group_id.strip():
            return {"status": "empty", "error_code": "INVALID_INPUT",
                    "message": "lab_id và group_id không được để trống."}
        if not members:
            return {"status": "empty", "error_code": "INVALID_MEMBERS",
                    "message": "Danh sách thành viên không được để trống."}

        # ═══════════════════════════════════════════════════════════
        # BƯỚC 1: Load toàn bộ dữ liệu lab từ cache
        # ═══════════════════════════════════════════════════════════
        service = LabContentService()
        lab_data = service.get_lab_data(lab_id)
        if not lab_data:
            return {"status": "empty", "error_code": "NO_LAB_DATA",
                    "message": f"Chưa có dữ liệu cho lab '{lab_id}'. Admin cần /admin-add-lab trước."}

        insights   = lab_data.get("insights", {})
        documents  = lab_data.get("documents", [])
        sitemap    = lab_data.get("sitemap", [])

        lab_objective      = insights.get("lab_objective", "")
        setup_instructions = insights.get("setup_instructions", "")
        grading_rubrics    = insights.get("grading_rubrics", "")
        common_pitfalls    = insights.get("common_pitfalls", [])
        draft_tasks        = insights.get("tasks", [])

        # ═══════════════════════════════════════════════════════════
        # BƯỚC 2: Build canonical 4-phase structure, inject lab content
        # ═══════════════════════════════════════════════════════════
        # Luôn dùng 4 phase canonical vì map tốt với mọi lab.
        # Content từ lab (insights + documents) được inject vào phase descriptions.

        # 2a. Merge nội dung từ insights và documents
        lab_full_text = lab_objective + "\n" + setup_instructions + "\n" + grading_rubrics
        if documents:
            for doc in documents[:3]:
                for sec in doc.get("sections", [])[:5]:
                    lab_full_text += "\n" + sec.get("heading", "") + "\n" + sec.get("content", "")[:300]

        # 2b. Extract key deliverables và requirements từ content
        grading_lines = []
        if grading_rubrics:
            grading_lines = [l.strip().lstrip("-* ") for l in grading_rubrics.split("\n")
                            if len(l.strip()) > 10][:5]

        setup_lines = []
        if setup_instructions:
            setup_lines = [l.strip().lstrip("-* ") for l in setup_instructions.split("\n")
                           if len(l.strip()) > 10][:4]

        # 2c. Canonical phases với content injection (tổng thời gian ~4h)
        phases = [
            {
                "task_id": "T1",
                "title": "🔍 Phân tích & Thiết kế",
                "description": (
                    f"Mục tiêu: {lab_objective[:200] if lab_objective else 'Hiểu rõ bài toán và thiết kế giải pháp'}.\n"
                    f"Giai đoạn này tập trung vào phân tích yêu cầu, xác định phạm vi, "
                    f"chọn công nghệ, thiết kế kiến trúc, và lập kế hoạch triển khai."
                ),
                "objective": "Phân tích yêu cầu và thiết kế giải pháp hoàn chỉnh",
                "phase_type": "design",
                "setup_tasks": setup_lines[:3],
            },
            {
                "task_id": "T2",
                "title": "🛠 Xây dựng & Tích hợp",
                "description": (
                    f"Implement core functionality: xây dựng UI/API, tích hợp AI pipeline, "
                    f"kết nối các thành phần. Đảm bảo mọi thứ chạy end-to-end."
                ),
                "objective": "Hoàn thành sản phẩm chạy được end-to-end",
                "phase_type": "build",
            },
            {
                "task_id": "T3",
                "title": "📊 Đo đạc & Validate",
                "description": (
                    f"Đánh giá chất lượng sản phẩm: chạy test suite, đo metrics, "
                    f"validate với người dùng thật, thu thập feedback và sửa lỗi.\n"
                    f"Tiêu chí: {'; '.join(grading_lines[:3]) if grading_lines else 'Đạt quality bar đã định'}"
                ),
                "objective": "Đảm bảo chất lượng đạt tiêu chuẩn",
                "phase_type": "validate",
                "setup_tasks": grading_lines[:4],
            },
            {
                "task_id": "T4",
                "title": "🎤 Demo & Nộp",
                "description": (
                    f"Chuẩn bị slide thuyết trình, chạy dry run, demo live trước giảng viên. "
                    f"Đảm bảo nộp bài đúng hạn và đầy đủ deliverables."
                ),
                "objective": "Trình bày thành quả và nộp bài hoàn chỉnh",
                "phase_type": "demo",
            },
        ]

        # ═══════════════════════════════════════════════════════════
        # BƯỚC 3: Role-specific task templates (dùng phase_type có sẵn)
        # ═══════════════════════════════════════════════════════════

        ROLE_RESPONSIBILITIES = {
            "frontend": {
                "design": (
                    "**Mục tiêu:** Biến yêu cầu lab thành thiết kế UI/UX cụ thể.\n\n"
                    "**Việc cần làm:**\n"
                    "• Đọc kỹ đề bài + rubric — xác định user thấy gì, làm gì trên màn hình\n"
                    "• Vẽ wireframe toàn bộ flow chính (Figma/Excalidraw): tối thiểu 3 màn hình Input → Processing → Output\n"
                    "• Thiết kế đủ trạng thái UI: loading, empty, error (AI fail/timeout), success\n"
                    "• Chọn component library (shadcn/ui, Ant Design, MUI, Tailwind...) — ưu tiên cái team quen\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• Người dùng mất mấy giây để hiểu cần làm gì trên màn hình?\n"
                    "• Nếu API/AI lỗi, UI hiển thị gì thay vì crash?\n"
                    "• Có cần dark mode / accessibility (ARIA, keyboard nav) không?\n\n"
                    "**📄 File tham khảo:** `README.md` (yêu cầu), `04-rubric.md` (cách chấm UI)\n\n"
                    "**🎯 Deliverable:** Wireframe + Component tree + Style guide (màu, font, spacing)"
                ),
                "build": (
                    "**Mục tiêu:** Dựng giao diện thật, kết nối API, xử lý mọi trạng thái.\n\n"
                    "**Việc cần làm:**\n"
                    "• Khởi tạo project, cài dependencies, setup router + global state\n"
                    "• Implement từng màn hình theo wireframe — flow chính trước, đẹp sau\n"
                    "• Kết nối API thật (hoặc mock nếu backend chưa sẵn sàng)\n"
                    "• Xử lý streaming response: hiển thị từng token, auto scroll, nút stop\n"
                    "• Retry logic khi API fail (3 lần, exponential backoff), timeout 30s\n"
                    "• Tối ưu UX: debounce input, optimistic update, skeleton loading\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• Khi AI đang generate, user có làm gì khác được không?\n"
                    "• Làm sao user copy kết quả nhanh nhất (1-click copy, export)?\n"
                    "• Nếu streaming bị ngắt, có lưu partial result không?\n\n"
                    "**📄 File tham khảo:** `02-guide.md` (flow), code blocks trong `README.md` (API contract)\n\n"
                    "**🎯 Deliverable:** UI hoàn chỉnh — mọi state, responsive, connected API"
                ),
                "validate": (
                    "**Mục tiêu:** Test UI kỹ lưỡng, sửa mọi lỗi giao diện.\n\n"
                    "**Việc cần làm:**\n"
                    "• Tự test toàn bộ flow 5+ lần — ghi lại mọi chỗ khó chịu\n"
                    "• Nhờ 2+ người ngoài nhóm dùng thử và feedback (UX testing)\n"
                    "• Test responsive: resize từ 320px → 1920px\n"
                    "• Test dark/light mode, accessibility (tab nav, ARIA labels)\n"
                    "• Fix tất cả: lệch layout, sai màu, text tràn, nút không bấm được\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• Người mới có hiểu cách dùng trong 10s đầu không?\n"
                    "• Animation có gây khó chịu không (chậm/nhanh/giật)?\n"
                    "• Text có đọc được không (contrast > 4.5:1)?\n\n"
                    "**📄 File tham khảo:** `04-rubric.md` (tiêu chí UI), feedback validator\n\n"
                    "**🎯 Deliverable:** UI polished — không bug, UX mượt, sẵn sàng demo"
                ),
                "demo": (
                    "**Mục tiêu:** UI hoàn hảo cho buổi demo.\n\n"
                    "**Việc cần làm:**\n"
                    "• Chuẩn bị data demo đẹp (example ấn tượng, không mock xấu)\n"
                    "• Đảm bảo mọi button, animation, transition mượt — không lag, không crash\n"
                    "• Chuẩn bị 1-2 fallback scenario: API chết → UI vẫn graceful error\n"
                    "• Chụp screenshot đẹp cho PM đưa vào slide\n"
                    "• Tham gia dry run, note thao tác UI để presenter không quên\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• Chỉ có 60s show UI — sẽ show gì trước?\n"
                    "• Có wow moment nào để người xem nhớ không?\n\n"
                    "**🎯 Deliverable:** UI demo-ready + Screenshots + Fallback plan"
                ),
            },
            "backend": {
                "design": (
                    "**Mục tiêu:** Thiết kế kiến trúc backend vững chắc trước khi code.\n\n"
                    "**Việc cần làm:**\n"
                    "• Đọc đề bài — liệt kê tất cả endpoints cần có (CRUD + AI endpoints)\n"
                    "• Thiết kế DB schema: ERD, relationships, indexes cần thiết\n"
                    "• Chọn stack (FastAPI/Flask/Express...) — cân nhắc async, ecosystem\n"
                    "• Thiết kế API contract: viết OpenAPI/Swagger spec trước (contract-first)\n"
                    "• Data flow: request → middleware → handler → service → AI → response\n"
                    "• Error handling pattern: HTTP codes, error format, logging\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• API bị gọi bao nhiêu lần/giây? Cần rate limiting không?\n"
                    "• Database chết hoặc AI timeout → API trả về gì?\n"
                    "• Cần auth không? JWT hay API key?\n\n"
                    "**📄 File tham khảo:** `README.md`, `02-guide.md`, `03-template-ai-spec.md`\n\n"
                    "**🎯 Deliverable:** Architecture diagram + ERD + API spec (OpenAPI)"
                ),
                "build": (
                    "**Mục tiêu:** Implement toàn bộ backend — endpoints, logic, DB, AI.\n\n"
                    "**Việc cần làm:**\n"
                    "• Khởi tạo project, cài dependencies, config (env, CORS, logging)\n"
                    "• Implement DB: migrations, seed data, models/entities\n"
                    "• Implement endpoints: validate input (Pydantic/Zod), business logic, errors\n"
                    "• Tích hợp AI provider: service gọi API, xử lý streaming response\n"
                    "• Retry logic (3 lần exponential backoff), circuit breaker nếu AI fail\n"
                    "• Middleware: logging request/response, global error handler, CORS\n"
                    "• Auto-generate Swagger docs từ code\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• AI provider rate limit → buffer request hay reject ngay?\n"
                    "• Có cache được response giống nhau không?\n"
                    "• Cần queue không? (nhiều user gọi AI cùng lúc)\n\n"
                    "**📄 File tham khảo:** API spec Design phase, `02-guide.md` (patterns)\n\n"
                    "**🎯 Deliverable:** Backend chạy được — endpoints + AI + Swagger docs"
                ),
                "validate": (
                    "**Mục tiêu:** Test backend kỹ, đảm bảo ổn định trước demo.\n\n"
                    "**Việc cần làm:**\n"
                    "• Unit test từng service/handler (target >80% coverage)\n"
                    "• Integration test: test API với database thật/test DB\n"
                    "• Load test: 50 requests liên tục, check response time, memory\n"
                    "• Error handling test: tắt AI, tắt DB → API trả lỗi rõ ràng?\n"
                    "• Code review: check SQL injection, XSS, hardcoded secrets\n"
                    "• Tối ưu slow queries: thêm index, eager loading\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• Worst-case latency của API này? Có memory leak không?\n"
                    "• Error message có lộ stack trace, DB schema không?\n\n"
                    "**📄 File tham khảo:** `04-rubric.md` (tiêu chí kỹ thuật), test results\n\n"
                    "**🎯 Deliverable:** Test suite xanh + Performance report + Security checklist"
                ),
                "demo": (
                    "**Mục tiêu:** Backend production-ready cho demo.\n\n"
                    "**Việc cần làm:**\n"
                    "• Backend chạy ổn định, không restart bất ngờ\n"
                    "• Fallback: AI không available → mock/static response\n"
                    "• Tắt debug mode, tắt verbose logging, bật rate limiting\n"
                    "• Script khởi động nhanh: 1 lệnh docker-compose up / python main.py\n"
                    "• Chuẩn bị giải thích ngắn gọn kiến trúc nếu giám khảo hỏi\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• Demo fail nếu cần restart server — có hot reload?\n"
                    "• Có endpoint /health, /ping cho presenter verify không?\n\n"
                    "**🎯 Deliverable:** Backend stable + Fallback + Health check endpoint"
                ),
            },
            "ai": {
                "design": (
                    "**Mục tiêu:** Thiết kế AI strategy — model, prompt, evaluation.\n\n"
                    "**Việc cần làm:**\n"
                    "• Đọc đề bài — xác định task AI: classify, generate, extract, reasoning, tool-use?\n"
                    "• So sánh models: GPT-4o vs Claude vs Gemini — tiêu chí: accuracy, latency, cost\n"
                    "  Recommend: GPT-4o-mini (nhanh+rẻ) cho simple tasks, Claude Sonnet cho complex reasoning\n"
                    "• Thiết kế system prompt: role, constraints, output format, anti-hallucination rules\n"
                    "• Thiết kế tool definitions (nếu function calling): schema rõ ràng\n"
                    "• Thiết kế eval strategy: metric (accuracy/precision/F1), golden set ≥20 cases\n"
                    "• Fallback plan: AI fail → rule-based / default response\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• Có thực sự cần AI không? Rule-based có giải được 80% không?\n"
                    "• Prompt injection risk: user hack được prompt không?\n"
                    "• Token cost: mỗi request bao nhiêu token? 1000 requests = $?\n\n"
                    "**📄 File tham khảo:** `03-template-ai-spec.md`, `README.md`\n\n"
                    "**🎯 Deliverable:** AI Spec — model choice + prompt design + eval plan + fallback"
                ),
                "build": (
                    "**Mục tiêu:** Implement AI pipeline hoàn chỉnh.\n\n"
                    "**Việc cần làm:**\n"
                    "• Setup AI provider SDK (OpenAI/Anthropic/Google) — API key qua env var\n"
                    "• Implement prompt template: load từ file, fill variables, validate output\n"
                    "• Implement tool calling loop: parse call → execute → feed → continue\n"
                    "• Xử lý edge cases:\n"
                    "  - Hallucination → validate output format, fact-check\n"
                    "  - Timeout → max 30s, retry 2 lần\n"
                    "  - Token limit → truncate input, summarize context\n"
                    "  - Refusal → detect, fallback graceful\n"
                    "  - Streaming → SSE/WebSocket cho real-time\n"
                    "• Response parsing: structured output (JSON/tool calls) → clean object\n"
                    "• Logging: mọi call (prompt, response, tokens, latency) để debug + cost\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• Cache response giống nhau? Save cost.\n"
                    "• Prompt versioning: rollback nếu prompt mới tệ hơn?\n"
                    "• AI call chiếm bao nhiêu % response time?\n\n"
                    "**📄 File tham khảo:** AI Spec, `02-guide.md`, prompt examples trong repo\n\n"
                    "**🎯 Deliverable:** AI pipeline — prompts + tool loop + edge cases + logging"
                ),
                "validate": (
                    "**Mục tiêu:** Đo lường & cải thiện chất lượng AI.\n\n"
                    "**Việc cần làm:**\n"
                    "• Chạy eval: golden set 20+ cases, đo accuracy/precision/recall/F1\n"
                    "• Phân loại lỗi: wrong format, hallucination, wrong tool call, refusal, latency cao\n"
                    "• Đo cost: mỗi request type tốn bao nhiêu token? Tổng cost golden set?\n"
                    "• Cải thiện prompt: sửa system prompt, thêm few-shot, điều chỉnh temperature\n"
                    "• Lặp eval sau mỗi lần sửa → track improvement\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• Case nào AI fail mà rule-based tốt hơn? → hybrid?\n"
                    "• Threshold chấp nhận AI output (confidence score)?\n"
                    "• Detect hallucination tự động? (cross-reference input)\n\n"
                    "**📄 File tham khảo:** Eval results, `04-rubric.md` (AI quality bar)\n\n"
                    "**🎯 Deliverable:** Eval report + Prompt improvement log + Cost analysis"
                ),
                "demo": (
                    "**Mục tiêu:** AI sẵn sàng tỏa sáng trong demo.\n\n"
                    "**Việc cần làm:**\n"
                    "• Chọn 2-3 test case ấn tượng để demo\n"
                    "• Viết script demo: user làm gì → AI trả gì → kết quả ra sao\n"
                    "• Fallback: AI fail trên sân khấu → show recording/pre-computed\n"
                    "• Giải thích: \"Tại sao model này?\", \"Prompt có gì đặc biệt?\"\n"
                    "• 1 slide về AI architecture (prompt flow, tool calls, eval)\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• Wow moment của AI là gì?\n"
                    "• Giám khảo hỏi \"tại sao không dùng model X?\" → trả lời sao?\n\n"
                    "**🎯 Deliverable:** Demo script + AI slide + Fallback recording"
                ),
            },
            "pm": {
                "design": (
                    "**Mục tiêu:** Tổ chức nhóm, lập kế hoạch, chuẩn bị canvas.\n\n"
                    "**Việc cần làm:**\n"
                    "• Gọi `generate_group_plan` để tạo plan hoặc tự phân công\n"
                    "• Điền Canvas: Job Story, Painpoint (bằng chứng), Solution, User, Outcome\n"
                    "• Timeline: phân bổ 4h thành các mốc, mỗi mốc có deliverable\n"
                    "• Book lịch gặp TA cho các checkpoint\n"
                    "• Risk assessment: thiếu skill? AI không ổn định? Thiếu data? → Mitigation\n"
                    "• Setup: Discord channel, task board (Linear/Trello/GitHub Issues)\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• Điểm mạnh nhất của nhóm? Leverage để làm gì khác biệt?\n"
                    "• Còn 2h thay vì 4h → cắt gì? (MVP scope)\n"
                    "• Có overlap/gap task không?\n\n"
                    "**📄 File tham khảo:** `01-de-bai.md`, `README.md`, `04-rubric.md`\n\n"
                    "**🎯 Deliverable:** Project plan + Canvas + Risk log + Task assignments"
                ),
                "build": (
                    "**Mục tiêu:** Điều phối team build, unblock, track tiến độ.\n\n"
                    "**Việc cần làm:**\n"
                    "• Check-in mỗi 30-45 phút: ai làm gì, có block không\n"
                    "• Dùng `track_group_progress(group_id)` xem tổng quan\n"
                    "• Member xong task → gọi `update_group_progress(...)` cập nhật\n"
                    "• Unblock: AI stuck prompt → pair. Frontend cần API → push backend\n"
                    "• Git flow: branch riêng, commit thường xuyên, PR review\n"
                    "• Note quyết định quan trọng (đổi stack, scope) cho báo cáo\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• Task nào critical path? Delay → team delay?\n"
                    "• Ai overload? Cần redistribute?\n"
                    "• Cần gọi TA không? (đừng đợi quá muộn)\n\n"
                    "**📄 File tham khảo:** Plan Design phase, `02-guide.md`\n\n"
                    "**🎯 Deliverable:** Status updates + Unblock log + Git repo organized"
                ),
                "validate": (
                    "**Mục tiêu:** Tổ chức validation, tổng hợp feedback, prioritize fix.\n\n"
                    "**Việc cần làm:**\n"
                    "• Tìm 3-5 người ngoài nhóm test (bạn học, TA...)\n"
                    "• Form feedback: UX dễ hiểu? AI chính xác? Bug?\n"
                    "• Ghi log: ai test, lúc nào, feedback gì\n"
                    "• Phân loại: Critical/Major/Minor → assign fix\n"
                    "• Verify fix: dev sửa xong → test lại\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• Pattern chung trong bugs? → fix root cause\n"
                    "• Feedback mâu thuẫn → quyết định thế nào?\n\n"
                    "**📄 File tham khảo:** Feedback logs, `04-rubric.md`\n\n"
                    "**🎯 Deliverable:** Validation report + Bug triage + Fix assignments"
                ),
                "demo": (
                    "**Mục tiêu:** Slide + Dry run + Demo hoàn hảo.\n\n"
                    "**Việc cần làm:**\n"
                    "• Slide 6 trang: Problem → Solution → Demo → Tech → Eval → Next\n"
                    "• Dry run đúng 5 phút, phân công ai nói, ai click\n"
                    "• Check: laptop sạc, trình duyệt sạch, font không lỗi\n"
                    "• Chuẩn bị trả lời câu hỏi thường gặp của giám khảo\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• 5 phút ngắn — phần nào quan trọng nhất?\n"
                    "• Demo fail → làm gì? (đừng hoảng, chuyển slide, giải thích)\n\n"
                    "**📄 File tham khảo:** `03-template-ai-spec.md`\n\n"
                    "**🎯 Deliverable:** Slide deck + Dry run + Demo checklist"
                ),
            },
            "qa": {
                "design": (
                    "**Mục tiêu:** Thiết kế test strategy từ đầu.\n\n"
                    "**Việc cần làm:**\n"
                    "• Đọc rubric: tiêu chí chấm điểm nào liên quan testing/chất lượng?\n"
                    "• Test cases: 10+ functional + 5 edge + 5 AI-specific\n"
                    "• Golden set 20+ cặp (input, expected), cover: happy path, edge, ambiguous, adversarial\n"
                    "• Test schedule: khi nào test gì, ai test, tool gì\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• \"Đúng\" với AI output nghĩa là gì?\n"
                    "• Test data có bias (toàn happy path) không?\n\n"
                    "**📄 File tham khảo:** `04-rubric.md`, `README.md`\n\n"
                    "**🎯 Deliverable:** Test plan + Golden set 20+ + Test schedule"
                ),
                "build": (
                    "**Mục tiêu:** Viết & chạy test liên tục khi build.\n\n"
                    "**Việc cần làm:**\n"
                    "• Automated test backend API: pytest/Jest, test từng endpoint\n"
                    "• Test frontend: component test + E2E (Playwright/Cypress)\n"
                    "• Test AI: mỗi lần update prompt → chạy golden set check regression\n"
                    "• CI pipeline: GitHub Actions chạy test khi push\n"
                    "• Báo bug ngay: steps to reproduce, expected vs actual\n"
                    "• Verify fix: dev sửa → test lại → close bug\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• Bug nào showstopper? Bug nào accept được?\n"
                    "• Prompt mới có giảm accuracy không? (regression)\n\n"
                    "**📄 File tham khảo:** API spec, wireframes, golden set\n\n"
                    "**🎯 Deliverable:** Test suite + Bug reports + CI pipeline"
                ),
                "validate": (
                    "**Mục tiêu:** Test toàn diện, báo cáo chất lượng.\n\n"
                    "**Việc cần làm:**\n"
                    "• Full test suite: unit + integration + E2E + AI eval\n"
                    "• Manual exploratory testing: dùng như user thật, cố \"phá\"\n"
                    "• Metrics: coverage >80%, AI accuracy >90%, response time (p50/p95/p99), Lighthouse >90\n"
                    "• Tổng hợp bug theo severity → assign fix → track\n"
                    "• Critical/major fixed → QA sign-off\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• Bug lặp lại? Root cause?\n"
                    "• Metric nào quan trọng nhất với giám khảo?\n\n"
                    "**📄 File tham khảo:** Test results, `04-rubric.md`\n\n"
                    "**🎯 Deliverable:** Test report + QA sign-off + Metrics"
                ),
                "demo": (
                    "**Mục tiêu:** Không bug showstopper khi demo.\n\n"
                    "**Việc cần làm:**\n"
                    "• Smoke test: chạy flow demo 3 lần, không crash\n"
                    "• Check môi trường: URL, API key, DB có data demo\n"
                    "• Known issues list cho presenter\n"
                    "• Bug nghiêm trọng → báo PM, quyết định fix/accept\n"
                    "• Sau demo: tổng kết bug tồn tại\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• Worst case: cái gì fail khi demo? Plan B?\n"
                    "• Giám khảo hỏi \"sao chưa fix?\" → trả lời?\n\n"
                    "**🎯 Deliverable:** Go/No-go + Known issues + Smoke test report"
                ),
            },
            "fullstack": {
                "design": (
                    "**Mục tiêu:** Thiết kế full-stack từ DB đến UI.\n\n"
                    "**Việc cần làm:**\n"
                    "• Thiết kế tổng thể: DB schema → API → UI components\n"
                    "• Chọn stack (ưu tiên cái quen nhất để code nhanh)\n"
                    "• Project structure: monorepo? Shared types/validation?\n"
                    "• Data flow: user action → API → logic → AI → response → UI\n"
                    "• Làm checklist Frontend Design + Backend Design (ở trên)\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• Reuse code giữa FE/BE (validation, types)?\n"
                    "• Làm gì trước để sớm có end-to-end?\n\n"
                    "**📄 File tham khảo:** `README.md`, `02-guide.md`\n\n"
                    "**🎯 Deliverable:** Full-stack architecture + Project scaffold"
                ),
                "build": (
                    "**Mục tiêu:** Build end-to-end — DB + API + AI + UI.\n\n"
                    "**Việc cần làm:**\n"
                    "• Build theo thứ tự: DB → API core → AI → UI connect\n"
                    "• Code cả FE + BE, dùng chung types nếu được\n"
                    "• Tích hợp AI vào API, UI hiển thị kết quả\n"
                    "• Test end-to-end liên tục khi build\n"
                    "• Commit thường xuyên, mỗi feature 1 commit\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• Module nào tốn thời gian nhất? Đơn giản hóa được không?\n"
                    "• Khi nào cần hỏi team giúp?\n\n"
                    "**📄 File tham khảo:** Architecture, API spec, wireframes\n\n"
                    "**🎯 Deliverable:** Full-stack app end-to-end"
                ),
                "validate": (
                    "**Mục tiêu:** Test toàn diện full-stack, fix bugs.\n\n"
                    "**Việc cần làm:**\n"
                    "• Test API: Postman/Bruno gọi từng endpoint\n"
                    "• Test UI: click-through flow, desktop + mobile\n"
                    "• Test AI: input khác nhau, check output\n"
                    "• Fix: crash → wrong result → UI glitch (theo priority)\n"
                    "• Error handling: tắt mạng, tắt DB, input sai\n\n"
                    "**🧠 Brainstorm:**\n"
                    "• 1 mình dễ bỏ sót → nhờ QA/team test giúp\n"
                    "• Tích hợp nào dễ vỡ nhất? (AI → UI)\n\n"
                    "**🎯 Deliverable:** Bug-free full-stack app"
                ),
                "demo": (
                    "**Mục tiêu:** Sẵn sàng demo full-stack.\n\n"
                    "**Việc cần làm:**\n"
                    "• App chạy mượt từ đầu đến cuối\n"
                    "• Data demo đẹp\n"
                    "• Backup code + DB lên GitHub\n"
                    "• Giải thích ngắn gọn FE lẫn BE nếu được hỏi\n\n"
                    "**🎯 Deliverable:** App production-ready + Backup"
                ),
            },
        }

        def _classify_member_role(role_str: str) -> str:
            """Map role description về 1 trong các canonical roles."""
            r = role_str.lower()
            if any(k in r for k in ("frontend", "front-end", "ui", "ux", "react", "vue")):
                return "frontend"
            if any(k in r for k in ("backend", "back-end", "api", "server", "database", "fastapi", "flask", "express")):
                return "backend"
            if any(k in r for k in ("ai", "ml", "llm", "prompt", "agent", "model")):
                return "ai"
            if any(k in r for k in ("pm", "scrum", "leader", "quản lý", "manager", "trưởng")):
                return "pm"
            if any(k in r for k in ("qa", "test", "tester", "quality", "kiểm thử")):
                return "qa"
            if any(k in r for k in ("fullstack", "full-stack", "full stack")):
                return "fullstack"
            return "fullstack"  # default

        # ═══════════════════════════════════════════════════════════
        # BƯỚC 4: Phân công & tạo task cho từng member
        # ═══════════════════════════════════════════════════════════
        plan_members = []
        assignment_rows = []

        for m in members:
            uid  = m.get("user_id") if isinstance(m, dict) else getattr(m, "user_id", None)
            role = m.get("role") if isinstance(m, dict) else getattr(m, "role", "member")
            custom_tasks = (m.get("custom_tasks") if isinstance(m, dict)
                            else getattr(m, "custom_tasks", None))

            if not uid:
                continue

            canonical = _classify_member_role(role)
            role_templates = ROLE_RESPONSIBILITIES.get(canonical, ROLE_RESPONSIBILITIES["fullstack"])

            member_tasks = []

            if custom_tasks:
                # Custom tasks từ leader — vẫn generate checklist
                for ct in custom_tasks:
                    member_tasks.append({
                        "task_id": _gen_task_id(phases, member_tasks),
                        "title": ct,
                        "description": "",
                        "checklist": _split_into_checklist("", ct),
                        "deliverable": "",
                    })
            else:
                # Template-based: mỗi phase sinh 1 task phù hợp với role
                for p in phases:
                    ptype = p["phase_type"]  # design / build / validate / demo
                    resp = role_templates.get(ptype, role_templates.get("build", ""))

                    # Extract checklist: chỉ lấy bullet points từ "Việc cần làm" section
                    checklist = []
                    in_todo_section = False
                    for line in resp.split("\n"):
                        s = line.strip()
                        # Detect "Việc cần làm" section
                        if "việc cần làm" in s.lower() or "cần làm" in s.lower():
                            in_todo_section = True
                            continue
                        # Stop at next section header
                        if in_todo_section and s.startswith("**") and s.endswith("**"):
                            if "việc" not in s.lower() and "làm" not in s.lower():
                                in_todo_section = False
                                continue
                        if in_todo_section and s.startswith("•"):
                            clean = s.lstrip("• ").strip()
                            if len(clean) > 6:
                                checklist.append(clean)

                    # Fallback: nếu ko extract được, dùng tất cả bullet points
                    if not checklist:
                        for line in resp.split("\n"):
                            s = line.strip()
                            if s.startswith("•") and len(s) > 6:
                                checklist.append(s.lstrip("• ").strip())
                    if not checklist:
                        checklist = ["Hoàn thành các yêu cầu của phase này"]

                    # Extract deliverable
                    deliverable = ""
                    for line in resp.split("\n"):
                        if "deliverable" in line.lower() and "**" in line:
                            deliverable = line.split("**")[-1].strip().lstrip(": ")[:200]
                            break
                    if not deliverable:
                        for line in resp.split("\n"):
                            if "🎯" in line and "deliverable" in line.lower():
                                deliverable = line.split(":", 1)[-1].strip()[:200]
                                break

                    member_tasks.append({
                        "task_id": p["task_id"],
                        "title": f"{p['title']} ({canonical})",
                        "description": p.get("description", "")[:300],
                        "checklist": checklist[:7],
                        "deliverable": deliverable,
                    })

            plan_members.append({
                "user_id": uid,
                "role": role,
                "canonical_role": canonical,
                "tasks": member_tasks,
            })

            for task in member_tasks:
                assignment_rows.append({
                    "group_id": group_id, "user_id": uid,
                    "task_id": task["task_id"], "task_title": task["title"],
                    "deadline": "", "status": "in_progress",
                    "completed_checklist": 0,
                    "total_checklist": max(len(task.get("checklist", [])), 1),
                    "extension_count": 0,
                })

        # ═══════════════════════════════════════════════════════════
        # BƯỚC 5: Tổng hợp references & lưu DB
        # ═══════════════════════════════════════════════════════════
        references = [f"📄 `{d.get('relative_path','')}` — {d.get('title','')}"
                      for d in sitemap[:10]]

        plan_data = {
            "lab_id": lab_id, "group_id": group_id,
            "lab_objective": lab_objective,
            "setup_instructions": setup_instructions,
            "grading_rubrics": grading_rubrics,
            "common_pitfalls": common_pitfalls,
            "phases": phases,
            "members": plan_members,
            "references": references,
            "notes": notes or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        now_iso = datetime.now(timezone.utc).isoformat()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM group_plans WHERE group_id = ? AND lab_id = ?",
                       (group_id, lab_id))
        cursor.execute(
            "INSERT INTO group_plans (group_id, lab_id, plan_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (group_id, lab_id, json.dumps(plan_data, ensure_ascii=False), now_iso, now_iso))
        cursor.execute("DELETE FROM assignments WHERE group_id = ?", (group_id,))
        for a in assignment_rows:
            cursor.execute(
                """INSERT INTO assignments
                   (group_id, user_id, task_id, task_title, deadline, status,
                    completed_checklist, total_checklist, extension_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (a["group_id"], a["user_id"], a["task_id"], a["task_title"],
                 a["deadline"], a["status"], a["completed_checklist"],
                 a["total_checklist"], a["extension_count"]))
        conn.commit()
        conn.close()

        # ═══════════════════════════════════════════════════════════
        # BƯỚC 6: Build response
        # ═══════════════════════════════════════════════════════════
        lines = []
        for pm in plan_members:
            role = pm["role"]
            uid  = pm["user_id"]
            task_strs = []
            for t in pm["tasks"]:
                cl_summary = ", ".join(t.get("checklist", [])[:4])
                if len(t.get("checklist", [])) > 4:
                    cl_summary += f" ... (+{len(t['checklist']) - 4})"
                task_strs.append(
                    f"  **{t['task_id']}:** {t['title']}\n"
                    f"     ☐ {cl_summary}"
                )
            lines.append(f"### {role} ({uid})\n" + "\n".join(task_strs))

        pitfall_text = ""
        if common_pitfalls:
            pf_items = common_pitfalls if isinstance(common_pitfalls, list) else [common_pitfalls]
            pitfall_text = "\n\n### ⚠️ Lưu ý quan trọng\n" + "\n".join(f"  • {p}" for p in pf_items[:5])

        phase_list = []
        for p in phases:
            phase_list.append(f"- **{p['task_id']} — {p['title']}**")

        plan_summary = (
            f"## 📋 Kế hoạch Lab `{lab_id}` — Nhóm {group_id}\n\n"
            f"**🎯 Mục tiêu:** {lab_objective or 'Hoàn thành bài lab đúng tiến độ'}\n\n"
            f"---\n"
            f"### 📊 Các Giai Đoạn\n" + "\n".join(phase_list) + "\n\n"
            f"---\n"
            f"### 👥 Phân Công Chi Tiết\n\n" + "\n\n".join(lines) + "\n\n"
            f"---\n"
            f"### 📚 Tài liệu tham khảo\n" + "\n".join(references[:8]) +
            pitfall_text +
            f"\n\n> 💡 *Dùng `track_group_progress` để xem tiến độ, `update_group_progress` để cập nhật task.*"
        )

        return {
            "status": "success", "group_id": group_id, "lab_id": lab_id,
            "lab_objective": lab_objective or "Mục tiêu bài lab",
            "setup_instructions": setup_instructions,
            "grading_rubrics": grading_rubrics,
            "common_pitfalls": common_pitfalls,
            "phases": phases,
            "members_plan": plan_members,
            "references": references,
            "summary": plan_summary,
            "note": "Dùng `track_group_progress` để xem tiến độ, `update_group_progress` để cập nhật.",
        }

    except Exception as e:
        return {"status": "error", "error_code": "PLAN_FAILED",
                "message": f"Không thể tạo kế hoạch nhóm: {e}"}

    except Exception as e:
        return {"status": "error", "error_code": "PLAN_FAILED",
                "message": f"Không thể tạo kế hoạch nhóm: {e}"}


def get_group_plan(group_id: str) -> Dict[str, Any]:
    """
    2. get_group_plan
    Mô tả: Đọc kế hoạch hiện tại của một nhóm từ DB.
    """
    try:
        if not group_id or not group_id.strip():
            return {"status": "empty", "error_code": "INVALID_INPUT",
                    "message": "group_id không được để trống."}

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM group_plans WHERE group_id = ? ORDER BY created_at DESC LIMIT 1",
            (group_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {"status": "empty", "error_code": "NO_PLAN_FOUND",
                    "message": f"Chưa có kế hoạch nào cho nhóm {group_id}. Dùng generate_group_plan để tạo."}

        plan_data = json.loads(row["plan_json"])
        return {
            "status": "success", "group_id": group_id,
            "lab_id": plan_data.get("lab_id", ""),
            "lab_objective": plan_data.get("lab_objective", ""),
            "setup_instructions": plan_data.get("setup_instructions", ""),
            "grading_rubrics": plan_data.get("grading_rubrics", ""),
            "common_pitfalls": plan_data.get("common_pitfalls", []),
            "phases": plan_data.get("phases", []),
            "members_plan": plan_data.get("members", []),
            "references": plan_data.get("references", []),
            "notes": plan_data.get("notes", ""),
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        }
    except Exception as e:
        return {"status": "error", "error_code": "GET_PLAN_FAILED",
                "message": f"Không thể đọc kế hoạch nhóm: {e}"}


def track_group_progress(group_id: str) -> Dict[str, Any]:
    """
    3. track_group_progress
    Mô tả: Tổng hợp tiến độ nhóm từ bảng `assignments`.
    """
    try:
        if not group_id or not group_id.strip():
            return {"status": "empty", "error_code": "INVALID_INPUT",
                    "message": "group_id không được để trống."}

        if "UNASSIGNED" in group_id:
            return {"status": "empty", "error_code": "NO_TASK_ASSIGNED",
                    "message": "Nhóm này chưa được phân công task nào."}

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM assignments WHERE group_id = ?", (group_id,))
        rows = cursor.fetchall()

        if not rows:
            if group_id == "G01" or group_id.startswith("G"):
                conn.close()
                return {
                    "status": "success", "group_id": group_id,
                    "overall_completion_percent": 0.0,
                    "members_progress": []
                }
            conn.close()
            return {"status": "empty", "error_code": "NO_TASK_ASSIGNED",
                    "message": "Nhóm này chưa được phân công task nào."}

        total_tasks = len(rows)
        completed_tasks = sum(1 for r in rows if r["status"] == "completed")
        overall_pct = round((completed_tasks / total_tasks) * 100.0, 1) if total_tasks > 0 else 0.0

        members_progress = [{
            "user_id": r["user_id"],
            "task_title": r["task_title"] or f"Task {r['task_id']}",
            "status": r["status"],
            "completed_checklist": r["completed_checklist"],
            "total_checklist": r["total_checklist"],
        } for r in rows]
        conn.close()

        return {
            "status": "success", "group_id": group_id,
            "overall_completion_percent": overall_pct,
            "members_progress": members_progress,
        }
    except Exception as e:
        return {"status": "error", "error_code": "TRACKING_FAILED",
                "message": f"Không thể lấy tiến độ nhóm: {e}"}


def update_group_progress(
    group_id: str, user_id: str, task_id: str,
    status: Optional[str] = None,
    completed_checklist: Optional[int] = None,
) -> Dict[str, Any]:
    """
    4. update_group_progress
    Mô tả: Cập nhật tiến độ của một thành viên trong nhóm.
    """
    try:
        if not group_id or not group_id.strip() or not user_id or not user_id.strip() or not task_id or not task_id.strip():
            return {"status": "empty", "error_code": "INVALID_INPUT",
                    "message": "group_id, user_id và task_id không được để trống."}

        if status and status not in ("in_progress", "completed"):
            return {"status": "empty", "error_code": "INVALID_STATUS",
                    "message": "status phải là 'in_progress' hoặc 'completed'."}

        if completed_checklist is not None and completed_checklist < 0:
            return {"status": "empty", "error_code": "INVALID_CHECKLIST",
                    "message": "completed_checklist không được âm."}

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM assignments WHERE group_id = ? AND user_id = ? AND task_id = ?",
            (group_id, user_id, task_id))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return {"status": "empty", "error_code": "NO_ASSIGNMENT_FOUND",
                    "message": f"Không tìm thấy assignment cho user {user_id} - {task_id} trong nhóm {group_id}."}

        updates, params = [], []
        if status:
            updates.append("status = ?"); params.append(status)
        if completed_checklist is not None:
            updates.append("completed_checklist = ?"); params.append(completed_checklist)

        if not updates:
            conn.close()
            return {"status": "success", "group_id": group_id, "user_id": user_id,
                    "task_id": task_id, "message": "Không có gì để cập nhật."}

        params.extend([group_id, user_id, task_id])
        cursor.execute(
            f"UPDATE assignments SET {', '.join(updates)} WHERE group_id = ? AND user_id = ? AND task_id = ?",
            tuple(params))
        conn.commit()

        cursor.execute(
            "SELECT status, completed_checklist, total_checklist FROM assignments "
            "WHERE group_id = ? AND user_id = ? AND task_id = ?",
            (group_id, user_id, task_id))
        updated = cursor.fetchone()
        conn.close()

        return {
            "status": "success", "group_id": group_id, "user_id": user_id,
            "task_id": task_id,
            "new_status": updated["status"] if updated else status,
            "completed_checklist": updated["completed_checklist"] if updated else completed_checklist,
            "total_checklist": updated["total_checklist"] if updated else 2,
            "message": "Đã cập nhật tiến độ thành công.",
        }
    except Exception as e:
        return {"status": "error", "error_code": "UPDATE_FAILED",
                "message": f"Không thể cập nhật tiến độ: {e}"}
