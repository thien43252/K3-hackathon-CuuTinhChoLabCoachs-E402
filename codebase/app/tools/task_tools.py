"""
Module chứa các công cụ Quản lý Nhiệm vụ & Tiến độ (Task Management Tools).
Sử dụng CSDL SQLite thực tế (`assignments`, `lab_materials`, `users`, `group_plans`).
Bao gồm:
1. generate_group_plan (Create / Update — xoá cũ + ghi mới)
2. get_group_plan (Read)
3. track_group_progress
4. update_group_progress
5. list_members
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.services.repo_service import LabContentService

from app.core.db import get_db_connection
from app import discord_context


def _resolve_user_id() -> str:
    """Lấy user_id từ Discord context (auto-resolve, không cần param)."""
    ctx = discord_context.get()
    return ctx.user_id or ""


def _resolve_group_id() -> str:
    """Lấy group_id từ Discord context (auto-resolve, không cần param)."""
    ctx = discord_context.get()
    return ctx.group_id or ""


class MemberRole(BaseModel):
    user_id: str = Field(..., description="ID học viên")
    role: str = Field(..., description="Vai trò trong nhóm (ví dụ: Frontend, Backend, PM)")
    custom_tasks: Optional[List[str]] = Field(default=None, description="Danh sách task cụ thể (nếu có)")


class GenerateGroupPlanInput(BaseModel):
    lab_id: str = Field(..., description="Mã bài lab (có thể để trống để auto-resolve từ context)")
    members: List[MemberRole] = Field(..., description="Danh sách thành viên kèm vai trò (user_id auto từ context, leader @mention là AI tự điền)")
    notes: Optional[str] = Field(default=None, description="Ghi chú thêm từ nhóm (ví dụ: công nghệ, hướng tiếp cận)")


class GetGroupPlanInput(BaseModel):
    pass


class TrackGroupProgressInput(BaseModel):
    pass


class UpdateGroupProgressInput(BaseModel):
    task_id: str = Field(..., description="Mã task cần cập nhật (ví dụ: 'T1', 'T2')")
    status: Optional[str] = Field(default=None, description="Trạng thái mới ('in_progress' hoặc 'completed')")
    completed_checklist: Optional[int] = Field(default=None, description="Số checklist đã hoàn thành")


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


def _gen_custom_task_id(existing: list, phase_ids: set) -> str:
    """Generate custom task ID (CT1, CT2, ...) avoiding phase task IDs."""
    used = {t.get("task_id", "") for t in existing}
    used.update(phase_ids)
    i = 1
    while f"CT{i}" in used:
        i += 1
    return f"CT{i}"


# ═══════════════════════════════════════════════════════════════
# DEEP PLANNING — Divide & Conquer (Sequential, pure Python)
# Kiến trúc NODE PIPELINE chạy inline — không cần LangGraph/n8n
# NODE 0 → 1 → 2 → 3 → 4 trong 1 function call
# ═══════════════════════════════════════════════════════════════

# ── NODE 1 data: Subtask templates per phase_type + task_type ──────────────
_DEEP_SUBTASK_TEMPLATES: dict = {
    # key = (phase_type, canonical_role)
    # value = list of subtask dicts
    ("design", "ai"): [
        {
            "sid": ".1", "priority": "P0",
            "title": "Đọc tài liệu & điền Scoring Matrix",
            "why": "Chứng minh bài toán CẦN Agent, không chỉ Chatbot — đây là nền tảng tư duy cho toàn bộ lab",
            "how": [
                "Mở `docs/trace_eval.md`, tìm section Scoring Matrix",
                "Đọc README.md mục '4 Cấp Độ AI' — ghi chú tiêu chí Chatbot vs Agent",
                "Chấm 4 tiêu chí Agentic Fit (1–5đ mỗi tiêu chí): External Data, Multi-step, Actions, Unpredictable Input",
                "Điền bảng kèm giải thích 1 dòng cho mỗi điểm — tổng ≥12/20 mới đủ điều kiện Agent",
            ],
            "input_needed": "Quyết định chủ đề bài toán nhóm",
            "output_artifact": "Section Scoring Matrix trong `docs/trace_eval.md` điền đủ",
            "dod": "4 tiêu chí có điểm + giải thích, tổng điểm ghi rõ, file `git add` xong",
            "antipattern": "Chấm theo cảm tính — mỗi điểm PHẢI có câu giải thích từ bài toán nhóm",
            "estimated_minutes": 10,
        },
        {
            "sid": ".2", "priority": "P0",
            "title": "Viết bảng so sánh Chatbot vs ReAct Agent",
            "why": "Tạo 'north star' tư duy — hiểu TẠI SAO cần Agent trước khi code",
            "how": [
                "Tạo bảng 3 cột trong trace_eval.md: Câu hỏi / Chatbot xử lý được không / Agent xử lý thế nào",
                "Điền 5 test case vào bảng",
                "Với mỗi case: predict Chatbot output (hallucination risk?) và expected Agent trace",
                "Highlight ≥2 câu Chatbot sẽ hallucinate — đây là bằng chứng cần Agent",
            ],
            "input_needed": "5 test cases từ teammate",
            "output_artifact": "Bảng 'Chatbot vs Agent Analysis' trong trace_eval.md",
            "dod": "5 rows đầy đủ, classify output: correct/hallucinated/safe-fallback",
            "antipattern": "Dùng câu hỏi lý thuyết thuần — phải có ≥3 câu cần Tool/data thực tế",
            "estimated_minutes": 10,
        },
        {
            "sid": ".3", "priority": "P1",
            "title": "Phân tích Failure Modes của tools",
            "why": "Phòng thủ trước — biết tool fail ở đâu giúp code error handling tốt hơn",
            "how": [
                "Dựa trên tool list đã chọn, liệt kê failure mode cho mỗi tool",
                "Phân loại: Input Error / Logic Error / Edge Case",
                "Viết expected error string mà tool nên return thay vì crash",
                "Document vào docs/trace_eval.md section 'Failure Mode Analysis'",
            ],
            "input_needed": "Tool list từ teammate",
            "output_artifact": "Bảng Failure Modes trong trace_eval.md",
            "dod": "Mỗi tool có ≥2 failure mode với error string cụ thể",
            "antipattern": "Chỉ viết 'lỗi nhập sai' — phải viết cụ thể: khi input='xyz' → tool return 'LỖI: ...' ",
            "estimated_minutes": 10,
        },
        {
            "sid": ".4", "priority": "P1",
            "title": "Thiết kế Edge Case / câu bẫy",
            "why": "Chuẩn bị 'đạn' để test Agent nhóm mình và tấn công nhóm khác ở Mốc 4",
            "how": [
                "Thiết kế ≥2 câu bẫy nhắm Guardrail (ép Agent lặp vô hạn nếu thiếu MAX_ITERATIONS)",
                "Thiết kế ≥1 câu bẫy hallucination (Chatbot sẽ bịa đặt)",
                "Thiết kế ≥1 câu Prompt Injection (cố ý thay đổi behavior Agent)",
                "Thêm vào config/test_cases.json với type='edge_case'",
            ],
            "input_needed": "Hiểu tools đã được build (sau Mốc 2)",
            "output_artifact": "≥4 edge cases trong `config/test_cases.json`",
            "dod": "Mỗi edge case có: question + expected_agent_behavior + attack_vector_type",
            "antipattern": "Edge case không phải câu hỏi khó — là câu được thiết kế để phá hệ thống",
            "estimated_minutes": 10,
        },
    ],
    ("build", "ai"): [
        {
            "sid": ".1", "priority": "P0",
            "title": "Thiết kế Tool Contract (design-first)",
            "why": "'Design trước, code sau' — xác định contract trước khi implement tránh rework",
            "how": [
                "Liệt kê 3–5 tools cần thiết cho chủ đề nhóm",
                "Với mỗi tool, điền bảng 8 câu hỏi: Name, Purpose, Input, Output, Error, Side-effect, Example, Safety",
                "Thêm docstring chuẩn cho từng hàm trong src/tools.py",
                "Share danh sách tool với teammate để phân tích Failure Modes",
            ],
            "input_needed": "Quyết định chủ đề nhóm",
            "output_artifact": "Bảng Tool Contract trong docs/trace_eval.md section 'Tool Specs'",
            "dod": "≥3 tools, 8 trường đầy đủ, không trường nào để trống",
            "antipattern": "Code tools.py ngay khi chưa có contract — thiết kế contract trước",
            "estimated_minutes": 10,
        },
        {
            "sid": ".2", "priority": "P0",
            "title": "Implement src/tools.py với Error Handling",
            "why": "Tools pass test độc lập trước khi gắn Agent — isolate lỗi từ nguồn",
            "how": [
                "Implement từng hàm tool theo contract đã thiết kế",
                "Wrap try/except: lỗi return string 'LỖI: ...' KHÔNG raise Exception",
                "Register tất cả vào `AVAILABLE_TOOLS = {'tool_name': function}`",
                "Test thủ công từng tool với valid và invalid input",
            ],
            "input_needed": "Tool Contract đã thiết kế ở bước trước",
            "output_artifact": "`src/tools.py` với AVAILABLE_TOOLS dict + docstrings",
            "dod": "`AVAILABLE_TOOLS.keys()` in đúng tool names; mỗi tool với invalid input không crash",
            "antipattern": "`raise Exception(...)` thay vì `return 'LỖI: ...'` — tool phải return string",
            "estimated_minutes": 15,
        },
        {
            "sid": ".3", "priority": "P0",
            "title": "Viết CHATBOT_BASELINE_PROMPT",
            "why": "Baseline CÔNG BẰNG — prompt không biết về tools để so sánh trung thực với Agent",
            "how": [
                "Tạo `CHATBOT_BASELINE_PROMPT` trong src/prompts.py — không đề cập tools",
                "Implement `run_baseline_chatbot(question)` trong src/app.py: 1 LLM call",
                "Chạy 5 test cases, verify tool_calls=0 tất cả",
                "Share raw output với teammate để điền bảng so sánh",
            ],
            "input_needed": "Test cases từ config/test_cases.json",
            "output_artifact": "`CHATBOT_BASELINE_PROMPT` trong prompts.py + `run_baseline_chatbot()` trong app.py",
            "dod": "5 test cases chạy, tool_calls=0, kết quả ghi trong trace_eval.md",
            "antipattern": "Nhúng kết quả tool vào system prompt của baseline — đó là gian lận baseline",
            "estimated_minutes": 15,
        },
    ],
    ("validate", "ai"): [
        {
            "sid": ".1", "priority": "P0",
            "title": "Viết REACT_SYSTEM_PROMPT + Guardrails",
            "why": "Prompt là 'luật chơi' — ép Agent suy luận đúng format, không tự bịa Observation",
            "how": [
                "Tạo `REACT_SYSTEM_PROMPT` trong src/prompts.py với khung bắt buộc: Thought/Action/Observation",
                "Thêm rule: 'Chỉ Final Answer khi đã có Observation từ Tool thực tế'",
                "Thêm `MAX_ITERATIONS = 5` + xử lý khi đạt giới hạn",
                "Inject danh sách available tools vào prompt",
                "Test với 1 câu mẫu, verify output có Thought/Action đúng format",
            ],
            "input_needed": "AVAILABLE_TOOLS từ src/tools.py đã implement xong",
            "output_artifact": "`REACT_SYSTEM_PROMPT` + `MAX_ITERATIONS` trong src/prompts.py",
            "dod": "LLM sinh đúng 'Thought: ...\nAction: ...' cho ≥3 test queries",
            "antipattern": "LLM tự viết 'Observation:' — Application code phải điền, không phải LLM",
            "estimated_minutes": 15,
        },
        {
            "sid": ".2", "priority": "P0",
            "title": "Implement ReAct Loop trong src/app.py",
            "why": "Vòng lặp Thought→Action→Observation là trái tim Agent — phải chạy đúng logic",
            "how": [
                "Implement parser: extract tool_name + params từ 'Action: tool_name[params]'",
                "Implement executor: lookup AVAILABLE_TOOLS, gọi tool, bắt exception",
                "Implement loop: while iteration < MAX_ITERATIONS: [call LLM → parse → execute → append Observation]",
                "Handle 'Final Answer': khi output chứa 'Final Answer:' → break loop",
                "Handle MAX_ITERATIONS exceeded → return safe fallback message",
            ],
            "input_needed": "REACT_SYSTEM_PROMPT + AVAILABLE_TOOLS đã có",
            "output_artifact": "Hàm `run_react_agent(question)` trong src/app.py",
            "dod": "Multi-step → trace Thought→Action→Observation→Final; MAX_ITERATIONS ngắt đúng khi câu bẫy",
            "antipattern": "Application không append Observation — LLM không được tự viết Observation",
            "estimated_minutes": 20,
        },
        {
            "sid": ".3", "priority": "P0",
            "title": "Test 5 cases + fix Agent V1 → V2",
            "why": "Phát hiện lỗi có bằng chứng — V2 phải có trace before/after rõ ràng",
            "how": [
                "Chạy tất cả 5 test cases, ghi lại trace",
                "Cố tình trigger edge case — record failed trace",
                "RCA (Root Cause Analysis): Lỗi ở Parser? Executor? Prompt? Loop?",
                "Fix → Agent V2; chạy lại edge case, verify đã khắc phục",
            ],
            "input_needed": "Edge cases từ teammate + run_react_agent() đã implement",
            "output_artifact": "Agent V2 code + Failed trace + Fixed trace trong docs/trace_eval.md",
            "dod": "≥1 failed trace ghi kèm RCA; V2 pass edge case với safe fallback message",
            "antipattern": "Xóa failed trace — bằng chứng lỗi + sửa = đủ điểm observability",
            "estimated_minutes": 20,
        },
        {
            "sid": ".4", "priority": "P1",
            "title": "Ghi Trace Log + Bảng so sánh",
            "why": "Báo cáo phải có số liệu định lượng, không chỉ mô tả",
            "how": [
                "Chép 5 trace logs vào docs/trace_eval.md (cả Chatbot và Agent)",
                "Điền bảng rubric 0–2 điểm: 5 cases × 4 tiêu chí (Factual, Grounding, Tool selection, Termination)",
                "Tính tổng điểm Chatbot vs Agent, viết nhận xét 3–5 câu",
                "Share với teammate để vẽ Hybrid Flowchart",
            ],
            "input_needed": "Trace logs từ V2 test + Chatbot baseline output",
            "output_artifact": "`docs/trace_eval.md` đủ: Scoring Matrix + Tool Specs + Failure Modes + 5 Traces + Comparison Table",
            "dod": "trace_eval.md có đủ 5 sections, bảng rubric điền xong",
            "antipattern": "Trace thô chưa đủ — phải annotate: đâu là Thought, Observation, lỗi",
            "estimated_minutes": 15,
        },
    ],
    ("demo", "ai"): [
        {
            "sid": ".1", "priority": "P0",
            "title": "Chuẩn bị Attack Set tấn công liên nhóm",
            "why": "Gây failed trace ở Agent nhóm khác — bằng chứng hiểu sâu về guardrails",
            "how": [
                "Chọn 3 edge cases mạnh nhất từ bộ đã thiết kế",
                "Với mỗi câu: viết 'expected failure' (Agent nhóm kia fail thế nào nếu thiếu guardrail)",
                "Ghi biên bản cross-audit khi test Agent nhóm khác",
                "Điền section 'Cross-Audit Log' trong docs/trace_eval.md",
            ],
            "input_needed": "Edge cases đã thiết kế ở giai đoạn Design",
            "output_artifact": "Cross-Audit Log trong trace_eval.md",
            "dod": "3 câu tấn công ghi kết quả thực tế (pass/fail + trace path cụ thể)",
            "antipattern": "Chỉ ghi 'fail' — phải ghi trace path cụ thể: Thought→Action→Observation của họ",
            "estimated_minutes": 20,
        },
        {
            "sid": ".2", "priority": "P0",
            "title": "Vẽ Hybrid Decision Flowchart (Mermaid)",
            "why": "Tổng hợp học tập thành sơ đồ quyết định — khi nào Chatbot, khi nào ReAct Agent",
            "how": [
                "Xác định 4–5 tiêu chí: cần tool không, multi-step không, latency OK không",
                "Vẽ Mermaid flowchart: Chatbot path (fast/cheap) vs ReAct path (accurate/grounded)",
                "Thêm decision diamond: 'Cần dữ liệu real-time?' → Yes → ReAct / No → Chatbot",
                "Thêm cost annotation + save vào docs/hybrid_flowchart.mermaid",
            ],
            "input_needed": "Bảng so sánh Chatbot vs Agent + trace logs",
            "output_artifact": "`docs/hybrid_flowchart.mermaid` render được",
            "dod": "Render OK trên Mermaid Live Editor, ≥2 decision diamonds, 2 paths rõ",
            "antipattern": "Flowchart phải có nhánh IF/ELSE — không phải sequence steps thẳng",
            "estimated_minutes": 20,
        },
    ],
}

_RISK_BY_PHASE: dict = {
    "design": [
        {"risk": "Chấm Scoring Matrix theo cảm tính, thiếu giải thích cụ thể", "level": "MEDIUM",
         "mitigation": "Mỗi điểm phải kèm 1 câu giải thích từ bài toán nhóm chọn"},
    ],
    "build": [
        {"risk": "Tools.py raise Exception thay vì return string lỗi → Agent crash", "level": "HIGH",
         "mitigation": "Wrap tất cả tool trong try/except, return 'LỖI: ...' thay vì raise"},
        {"risk": "Nhúng kết quả tool vào Chatbot baseline → so sánh không công bằng", "level": "HIGH",
         "mitigation": "Verify tool_calls=0 sau mỗi lần chạy baseline"},
    ],
    "validate": [
        {"risk": "LLM tự viết Observation — hallucination vẫn xảy ra trong Agent", "level": "CRITICAL",
         "mitigation": "Code review: nếu 'Observation:' xuất hiện trong LLM output → sai"},
        {"risk": "Xóa failed trace vì xấu hổ → mất điểm observability", "level": "MEDIUM",
         "mitigation": "Giữ nguyên failed trace + thêm RCA annotation bên cạnh"},
    ],
    "demo": [
        {"risk": "Không có trace log cụ thể khi tấn công nhóm khác", "level": "MEDIUM",
         "mitigation": "Ghi lại Thought→Action→Observation của Agent nhóm bạn khi bị tấn công"},
    ],
}

_QUALITY_GATES_BY_PHASE: dict = {
    "design":   "Scoring Matrix điền xong, bảng so sánh Chatbot vs Agent có ≥5 rows",
    "build":    "AVAILABLE_TOOLS.keys() in đúng, `python -c 'from src.tools import AVAILABLE_TOOLS'` không lỗi; baseline tool_calls=0",
    "validate": "Multi-step trace đúng chuỗi Thought→Action→Observation→Final; MAX_ITERATIONS ngắt khi câu bẫy; V2 safe fallback",
    "demo":     "Hybrid Flowchart render OK trên Mermaid Live Editor; Cross-Audit Log có kết quả thực tế",
}

_RUBRIC_MAP: dict = {
    "design":   ("Agentic Fit & Test Design", "20%"),
    "build":    ("ReAct Implementation & Tools", "30%"),
    "validate": ("Guardrails & Observability", "20%"),
    "demo":     ("Inter-group Attack & Defense + Hybrid Flowchart", "30%"),
}


def _build_deep_subtasks(
    task: dict,
    canonical_role: str,
    lab_sections: list,
) -> list:
    """
    NODE 1 — Task Decomposer (inline, no extra LLM call).
    Phân rã task thành subtask sâu với Why/How/DoD/Antipattern.
    Ưu tiên dùng template _DEEP_SUBTASK_TEMPLATES, fallback phân rã từ checklist.
    """
    phase_type = task.get("phase_type", "build")
    task_id = task.get("task_id", "T?")
    checklist = task.get("checklist", [])

    # Lookup template
    template_key = (phase_type, canonical_role)
    templates = _DEEP_SUBTASK_TEMPLATES.get(template_key, [])

    # Nếu không có template → phân rã từ checklist
    if not templates:
        subtasks = []
        for i, item in enumerate(checklist):
            subtasks.append({
                "subtask_id": f"{task_id}.{i+1}",
                "priority": "P0" if i == 0 else ("P1" if i <= 2 else "P2"),
                "title": item[:60],
                "why": "Bước cần thiết để hoàn thành task này",
                "how": [f"Thực hiện: {item}", "Verify kết quả", "Commit lên git"],
                "input_needed": "Kết quả từ subtask trước",
                "output_artifact": "File/artifact liên quan đến task",
                "dod": f"Hoàn thành: {item}",
                "antipattern": "Bỏ qua bước này hoặc làm tắt",
                "estimated_minutes": 10,
            })
        return subtasks

    # Enrich templates với task context
    result = []
    for tpl in templates:
        sid = f"{task_id}{tpl['sid']}"
        result.append({
            "subtask_id": sid,
            "priority": tpl.get("priority", "P1"),
            "title": tpl["title"],
            "why": tpl["why"],
            "how": tpl["how"],
            "input_needed": tpl.get("input_needed", ""),
            "output_artifact": tpl.get("output_artifact", ""),
            "dod": tpl["dod"],
            "antipattern": tpl["antipattern"],
            "estimated_minutes": tpl.get("estimated_minutes", 10),
        })
    return result


def _render_subtask_block(st: dict) -> str:
    """Render 1 subtask thành Markdown block theo NODE 4 format."""
    how_lines = "\n".join(
        f"  - ☐ ST-{st['subtask_id']}.{i+1} {step}"
        for i, step in enumerate(st.get("how", []))
    )
    return (
        f"**[{st.get('priority', 'P1')}] {st['subtask_id']} — {st['title']}**\n"
        f"- 🎯 **Mục đích**: {st['why']}\n"
        f"- 📋 **Các bước thực hiện**:\n{how_lines}\n"
        f"- 📥 **Input cần từ**: {st.get('input_needed', '—')}\n"
        f"- 📤 **Output tạo ra**: {st.get('output_artifact', '—')}\n"
        f"- ✅ **Hoàn thành khi**: {st['dod']}\n"
        f"- ⚠️ **Đừng mắc bẫy**: {st['antipattern']}\n"
    )


def _render_deep_plan_summary(
    group_id: str,
    lab_id: str,
    lab_objective: str,
    plan_members: list,
    phases: list,
    references: list,
    common_pitfalls: list,
) -> str:
    """
    NODE 2 + 3 + 4 — Dependency Map, Risk Annotator, Formatter (all inline).
    Tạo deep plan summary dạng Markdown guidebook hoàn chỉnh.
    """
    lines: list[str] = []
    lines.append(f"## 📋 Kế hoạch Lab `{lab_id}` — Nhóm {group_id}\n")
    lines.append(f"**🎯 Mục tiêu:** {lab_objective or 'Hoàn thành bài lab đúng tiến độ'}\n")
    lines.append("---\n")

    # ── NODE 2: Execution Waves (infer từ phase_type order) ─────────────────
    phase_type_order = ["design", "build", "validate", "demo"]
    wave_labels = {
        "design":   "🔍 Wave 1 — Phân tích & Thiết kế",
        "build":    "🛠 Wave 2 — Xây dựng & Tích hợp",
        "validate": "📊 Wave 3 — Kiểm thử & Validate",
        "demo":     "🎤 Wave 4 — Demo & Tương tác liên nhóm",
    }

    # Xác định ai làm gì trong mỗi wave
    wave_assignments: dict[str, list[str]] = {pt: [] for pt in phase_type_order}
    for pm in plan_members:
        for t in pm.get("tasks", []):
            pt = t.get("phase_type", "build")
            if pt in wave_assignments:
                tid = t.get("task_id", "?")
                uid = pm.get("user_id", "?")
                role = pm.get("role", "")
                wave_assignments[pt].append(f"[{uid} · {role}] {tid}: {t.get('title', '')}")

    lines.append("### 🌊 Luồng Thực Thi (Execution Waves)\n")
    lines.append("```")
    active_waves = [pt for pt in phase_type_order if wave_assignments[pt]]
    for pt in active_waves:
        label = wave_labels.get(pt, pt)
        lines.append(f"{label}:")
        for item in wave_assignments[pt]:
            lines.append(f"  ├── {item}")
    # Critical path: task_id sequence across waves
    cp_ids = []
    for pt in active_waves:
        for pm in plan_members:
            for t in pm.get("tasks", []):
                if t.get("phase_type") == pt:
                    cp_ids.append(t.get("task_id", ""))
                    break
    lines.append("")
    lines.append(f"🔗 Critical Path: {' → '.join(cp_ids)}")
    lines.append("```\n")
    lines.append("---\n")

    # ── NODE 4: Per-member deep plan ─────────────────────────────────────────
    lines.append("### 👥 Phân Công Chi Tiết\n")

    for pm in plan_members:
        uid = pm.get("user_id", "?")
        role = pm.get("role", "Member")
        canonical = pm.get("canonical_role", "fullstack")
        lines.append(f"#### 👤 {role} ({uid})\n")

        member_rubric_rows: list[str] = []
        member_risk_rows: list[str] = []
        member_quality_gates: list[str] = []

        for t in pm.get("tasks", []):
            tid = t.get("task_id", "?")
            title = t.get("title", "")
            phase_type = t.get("phase_type", "build")
            est_min = t.get("estimated_minutes") or 30

            rubric_name, rubric_weight = _RUBRIC_MAP.get(phase_type, ("Hoàn thành task", "?"))

            lines.append(f"**📌 {tid} — {title}**")
            lines.append(f"> ⏱️ ~{est_min} phút | 🎯 Rubric: {rubric_name} ({rubric_weight})\n")

            # NODE 1: Render subtasks
            subtasks = t.get("_deep_subtasks", [])
            if subtasks:
                for st in subtasks:
                    lines.append(_render_subtask_block(st))
            else:
                # Fallback: render checklist với format đơn giản hơn
                for i, item in enumerate(t.get("checklist", [])):
                    priority = "P0" if i == 0 else ("P1" if i <= 2 else "P2")
                    lines.append(
                        f"**[{priority}] {tid}.{i+1} — {item[:60]}**\n"
                        f"- 📋 Thực hiện: {item}\n"
                        f"- ✅ Hoàn thành khi: kết quả được commit lên git\n"
                    )

            # Quality gate cho phase
            gate = _QUALITY_GATES_BY_PHASE.get(phase_type, "")
            if gate:
                member_quality_gates.append(f"Sau {tid} ({phase_type}): {gate}")

            # Risk items
            risks = _RISK_BY_PHASE.get(phase_type, [])
            for r in risks:
                member_risk_rows.append(
                    f"| {r['risk'][:60]} | {r['level']} | {r['mitigation'][:60]} |"
                )

            # Rubric row
            subtask_ids = " + ".join(
                st["subtask_id"] for st in subtasks
            ) if subtasks else tid
            member_rubric_rows.append(
                f"| {rubric_name} | {rubric_weight} | {subtask_ids} | {role} |"
            )

            lines.append("")

        # Quality Gates block
        if member_quality_gates:
            lines.append("**🚦 Quality Gates:**")
            for gate in member_quality_gates:
                lines.append(f"- [ ] {gate}")
            lines.append("")

        # Risk Flags block
        if member_risk_rows:
            lines.append("**🔴 Risk Flags:**")
            lines.append("| Risk | Level | Mitigate |")
            lines.append("|------|-------|----------|")
            for row in member_risk_rows:
                lines.append(row)
            lines.append("")

        lines.append("---\n")

    # ── NODE 3: Rubric coverage table ─────────────────────────────────────
    lines.append("### 📊 Coverage Rubric\n")
    lines.append("| Tiêu chí | Trọng số | Subtask cover | Owner |")
    lines.append("|----------|----------|---------------|-------|")
    for pm in plan_members:
        for t in pm.get("tasks", []):
            phase_type = t.get("phase_type", "build")
            rubric_name, rubric_weight = _RUBRIC_MAP.get(phase_type, ("Hoàn thành task", "?"))
            subtasks = t.get("_deep_subtasks", [])
            cover = " + ".join(st["subtask_id"] for st in subtasks) if subtasks else t.get("task_id", "?")
            lines.append(f"| {rubric_name} | {rubric_weight} | {cover} | {pm.get('role', '?')} |")
    lines.append("")

    # References & pitfalls
    if references:
        lines.append("### 📚 Tài liệu tham khảo\n")
        lines.extend(references[:8])
        lines.append("")

    if common_pitfalls:
        pf_items = common_pitfalls if isinstance(common_pitfalls, list) else [common_pitfalls]
        lines.append("### ⚠️ Lưu ý quan trọng\n")
        for p in pf_items[:5]:
            lines.append(f"- {p}")
        lines.append("")

    lines.append("> 💡 *Dùng `track_group_progress` để xem tiến độ, `update_group_progress` để cập nhật task.*")

    return "\n".join(lines)


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
    members: List[Dict[str, Any]],
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    1. generate_group_plan
    Mô tả: Tạo kế hoạch chi tiết cho nhóm làm lab, đào sâu vào toàn bộ
    nội dung lab từ cache để xây dựng plan có chiều sâu.
    group_id được auto-resolve từ Discord context (chỉ dùng được trong group room).

    Algorithm:
      1. Load toàn bộ dữ liệu lab từ cache (insights + documents + sitemap)
      2. Build phases từ insight tasks (hoặc fallback canonical 4 phase)
      3. Với mỗi member, score từng phase dựa trên role → chọn top 6
      4. Search tài liệu lab tìm context match role+phase
      5. Inject lab-specific file references vào role templates
      6. Ghi vào DB: group_plans + assignments
    """
    try:
        group_id = _resolve_group_id()
        if not group_id:
            return {"status": "empty", "error_code": "NO_CONTEXT",
                    "message": "Tool chỉ dùng được trong group room Discord. Hãy tạo phòng nhóm trước."}
        if not lab_id or not lab_id.strip():
            return {"status": "empty", "error_code": "INVALID_INPUT",
                    "message": "lab_id không được để trống."}
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
        # BƯỚC 2: Build phases — ưu tiên từ insight tasks, fallback canonical
        # ═══════════════════════════════════════════════════════════

        # 2a. Extract grading & setup lines cho inject vào phases
        grading_lines = [l.strip().lstrip("-* ") for l in grading_rubrics.split("\n")
                        if len(l.strip()) > 10][:5] if grading_rubrics else []
        setup_lines = [l.strip().lstrip("-* ") for l in setup_instructions.split("\n")
                      if len(l.strip()) > 10][:4] if setup_instructions else []

        # 2b. Phase type detection
        def _detect_phase_type(title: str, desc: str = "") -> str:
            t = (title + " " + desc).lower()
            if any(k in t for k in ("phân tích", "thiết kế", "khám phá", "canvas", "spec", "kiến trúc",
                                     "định hình", "chọn", "ý tưởng", "brainstorm", "planning",
                                     "bảng chấm", "scoring matrix", "phân vai", "phân công")):
                return "design"
            if any(k in t for k in ("build", "xây dựng", "tích hợp", "implement", "code", "lắp", "cài đặt",
                                     "setup", "dựng", "agent", "tool", "prompt", "api",
                                     "chatbot", "react agent", "baseline", "loop")):
                return "build"
            if any(k in t for k in ("đo", "validate", "kiểm thử", "test", "eval", "chấm", "audit",
                                     "quality", "rubric", "đánh giá", "golden", "failed trace",
                                     "so sánh", "phản hồi")):
                return "validate"
            if any(k in t for k in ("demo", "nộp", "trình bày", "slide", "report", "tổng kết", "báo cáo")):
                return "demo"
            return "build"  # default

        # 2c. Build phases: dùng insight tasks nếu có, nếu không → canonical 4
        phases = []
        if draft_tasks and len(draft_tasks) >= 2:
            for idx, t in enumerate(draft_tasks):
                name = t.get("name", f"Task {idx+1}")
                desc = t.get("description", "")
                checklist = t.get("checklist", [])
                ptype = _detect_phase_type(name, desc)
                phases.append({
                    "task_id": f"T{idx+1}",
                    "title": name,
                    "description": desc[:400] if desc else "",
                    "objective": desc[:200] if desc else name,
                    "phase_type": ptype,
                    "checklist": checklist,
                    "deliverable": t.get("deliverable", ""),
                    "estimated_minutes": t.get("estimated_minutes"),
                })
        else:
            phases = [
                {"task_id": "T1", "title": "🔍 Phân tích & Thiết kế",
                 "description": f"Mục tiêu: {lab_objective[:200] if lab_objective else 'Hiểu rõ bài toán và thiết kế giải pháp'}.",
                 "objective": "Phân tích yêu cầu và thiết kế giải pháp", "phase_type": "design",
                 "checklist": setup_lines[:3] or ["Phân tích yêu cầu", "Thiết kế kiến trúc", "Lập kế hoạch"]},
                {"task_id": "T2", "title": "🛠 Xây dựng & Tích hợp",
                 "description": "Implement core: UI/API, tích hợp AI, kết nối các thành phần.",
                 "objective": "Hoàn thành sản phẩm end-to-end", "phase_type": "build",
                 "checklist": ["Implement core logic", "Tích hợp AI", "Xây dựng API/UI"]},
                {"task_id": "T3", "title": "📊 Đo đạc & Validate",
                 "description": f"Đánh giá chất lượng: test suite, metrics, validate với người dùng thật.\nTiêu chí: {'; '.join(grading_lines[:3]) if grading_lines else 'Đạt quality bar'}",
                 "objective": "Đảm bảo chất lượng đạt tiêu chuẩn", "phase_type": "validate",
                 "checklist": grading_lines[:4] or ["Chạy test suite", "Validate với users", "Sửa lỗi"]},
                {"task_id": "T4", "title": "🎤 Demo & Nộp",
                 "description": "Chuẩn bị slide, dry run, demo live, nộp bài.",
                 "objective": "Trình bày thành quả và nộp bài", "phase_type": "demo",
                 "checklist": ["Chuẩn bị slide", "Dry run", "Demo", "Nộp bài"]},
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
        # BƯỚC 2.5: Build lab-specific search index từ documents
        # ═══════════════════════════════════════════════════════════
        # Gom toàn bộ sections từ tất cả documents để search
        all_doc_sections = []
        for doc in documents:
            for sec in doc.get("sections", []):
                all_doc_sections.append({
                    "file": doc.get("relative_path", ""),
                    "heading": sec.get("heading", ""),
                    "content": sec.get("content", ""),
                })

        def _find_lab_specific_context(role_canonical: str, phase_type: str) -> dict:
            """Tìm sections + files trong lab khớp với role + phase."""
            ROLE_SEARCH_KW = {
                "frontend": ["ui", "ux", "giao diện", "frontend", "react", "component", "html", "css", "screen"],
                "backend":  ["api", "backend", "endpoint", "server", "database", "db", "schema", "model", "fastapi", "flask"],
                "ai":       ["prompt", "agent", "tool", "model", "llm", "gpt", "openai", "claude", "gemini", "react agent", "guardrail"],
                "pm":       ["plan", "canvas", "spec", "slide", "demo", "timeline", "checkpoint", "nộp"],
                "qa":       ["test", "eval", "golden", "kiểm thử", "đánh giá", "rubric", "scoring", "metric"],
                "fullstack": ["fullstack", "end-to-end", "full-stack"],
            }
            PHASE_KW = {
                "design":   ["thiết kế", "design", "phân tích", "canvas", "spec", "kiến trúc", "architecture"],
                "build":    ["build", "xây dựng", "implement", "code", "cài đặt", "setup", "tool spec", "prompt"],
                "validate": ["test", "eval", "validate", "đo", "kiểm thử", "rubric", "đánh giá", "golden"],
                "demo":     ["demo", "trình bày", "slide", "nộp", "present", "dry run"],
            }

            role_kw = ROLE_SEARCH_KW.get(role_canonical, [])
            phase_kw = PHASE_KW.get(phase_type, ["build"])

            matched_sections = []
            matched_files = set()

            for sec in all_doc_sections:
                text = (sec["heading"] + " " + sec["content"]).lower()
                role_match = any(kw in text for kw in role_kw)
                phase_match = any(kw in text for kw in phase_kw)

                if role_match or phase_match:
                    score = (1 if role_match else 0) + (1 if phase_match else 0)
                    matched_sections.append({
                        "file": sec["file"],
                        "heading": sec["heading"],
                        "content": sec["content"][:400],
                        "score": score,
                    })
                    matched_files.add(sec["file"])

            # Sort by score, dedup by heading
            seen_h = set()
            unique = []
            for s in sorted(matched_sections, key=lambda x: x["score"], reverse=True):
                key = s["heading"].lower()
                if key not in seen_h:
                    seen_h.add(key)
                    unique.append(s)

            return {
                "sections": unique[:5],
                "files": sorted(matched_files)[:6],
            }

        # ═══════════════════════════════════════════════════════════
        # BƯỚC 4: Phân công & tạo task cho từng member
        # ═══════════════════════════════════════════════════════════
        # Helper: score phase relevance cho role
        def _score_phase_for_role(phase: dict, canonical_role: str, templates: dict) -> int:
            """Điểm càng cao = phase càng phù hợp với role."""
            ptype = phase.get("phase_type", "build")
            # Bonus nếu phase_type match với role's primary phase
            ROLE_PRIMARY = {"frontend": "build", "backend": "build", "ai": "build",
                           "pm": "design", "qa": "validate", "fullstack": "build"}
            score = 10 if ROLE_PRIMARY.get(canonical_role, "build") == ptype else 5
            # Bonus nếu có template cho phase type này
            if templates.get(ptype):
                score += 5
            # Bonus dựa trên keyword trong phase title
            role_kw = {"frontend": ["ui", "giao diện", "frontend"],
                       "backend": ["api", "backend", "tool", "server"],
                       "ai": ["ai", "agent", "prompt", "model", "react"],
                       "pm": ["plan", "phân vai", "checklist", "báo cáo", "nộp"],
                       "qa": ["test", "eval", "chấm", "validate", "golden"],
                       "fullstack": []}
            for kw in role_kw.get(canonical_role, []):
                if kw in phase.get("title", "").lower():
                    score += 3
            return score

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

            phase_ids = {p["task_id"] for p in phases}
            if custom_tasks:
                # Custom tasks từ leader — match với phases có sẵn để lấy context
                phase_lookup = {p["title"].lower(): p for p in phases}
                for ct in custom_tasks:
                    ct_lower = ct.lower()
                    # Thử match custom task với phase có sẵn
                    matched_phase = None
                    for key, p in phase_lookup.items():
                        if any(word in ct_lower for word in key.split()) or any(word in key for word in ct_lower.split()):
                            matched_phase = p
                            break
                    if not matched_phase:
                        matched_phase = next(iter(phase_lookup.values()), None)

                    ptype = matched_phase.get("phase_type", "build") if matched_phase else "build"
                    phase_title = matched_phase.get("title", ct) if matched_phase else ct

                    # Tìm lab context cho custom task
                    lab_ctx = _find_lab_specific_context(canonical, ptype)

                    # Gắn deep subtasks dựa trên matched phase + role
                    matched_task = {
                        "task_id": _gen_custom_task_id(member_tasks, phase_ids),
                        "phase_type": ptype,
                        "checklist": _split_into_checklist("", ct),
                    }
                    deep_subtasks = _build_deep_subtasks(
                        task=matched_task,
                        canonical_role=canonical,
                        lab_sections=lab_ctx.get("sections", []),
                    ) if lab_ctx else []

                    # Inject lab file references
                    file_refs = ""
                    lab_files = lab_ctx.get("files", []) if lab_ctx else []
                    if lab_files:
                        file_refs = "\n".join(f"    • `{f}`" for f in lab_files[:4])

                    lab_recs_text = ""
                    if lab_ctx:
                        lab_recs = []
                        for s in lab_ctx.get("sections", [])[:3]:
                            rec = s["content"][:200].strip()
                            if len(rec) > 20:
                                lab_recs.append(f"    • [{s['file']}] {s['heading']}: {rec}...")
                        if lab_recs:
                            lab_recs_text = "\n\n**🔍 Nội dung từ tài liệu:**\n" + "\n".join(lab_recs)

                    enriched_desc = f"**[{canonical.upper()}]** {phase_title[:200]}{file_refs}{lab_recs_text}"

                    member_tasks.append({
                        "task_id": matched_task["task_id"],
                        "title": ct,
                        "description": enriched_desc,
                        "checklist": _split_into_checklist("", ct),
                        "deliverable": "",
                        "phase_type": ptype,
                        "estimated_minutes": None,
                        "_deep_subtasks": deep_subtasks,
                        "lab_files": lab_files[:4] if lab_files else [],
                    })
            else:
                # Template-based: chọn top phases phù hợp với role (max 6)
                scored_phases = []
                for p in phases:
                    s = _score_phase_for_role(p, canonical, role_templates)
                    scored_phases.append((s, p))
                scored_phases.sort(key=lambda x: x[0], reverse=True)
                max_phases = min(6, len(phases))
                selected_phases = [p for _, p in scored_phases[:max_phases]]

                for p in selected_phases:
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

                    # Search lab documents for context relevant to this role+phase
                    lab_ctx = _find_lab_specific_context(canonical, ptype)

                    # Build lab-specific file references
                    lab_files = lab_ctx.get("files", [])
                    file_refs = "\n".join(f"    • `{f}`" for f in lab_files[:4]) if lab_files else ""

                    # Build lab-specific recommendations từ document sections
                    lab_recs = []
                    for s in lab_ctx.get("sections", [])[:3]:
                        rec = s["content"][:250].strip()
                        if len(rec) > 20:
                            lab_recs.append(f"    • [{s['file']}] {s['heading']}: {rec}...")

                    lab_context_block = ""
                    if file_refs or lab_recs:
                        lab_context_block = (
                            f"\n\n**📄 Files cụ thể trong bài lab này:**\n{file_refs}"
                            + ("\n\n**🔍 Nội dung liên quan từ tài liệu lab:**\n" + "\n".join(lab_recs) if lab_recs else "")
                        )

                    role_tag = f"**[{canonical.upper()}]** "
                    enriched_description = (role_tag + p.get("description", "")[:300] + lab_context_block)

                    # NODE 1: Phân rã task thành deep subtasks
                    deep_subtasks = _build_deep_subtasks(
                        task={"task_id": p["task_id"], "phase_type": ptype, "checklist": checklist},
                        canonical_role=canonical,
                        lab_sections=lab_ctx.get("sections", []),
                    )

                    member_tasks.append({
                        "task_id": p["task_id"],
                        "title": p['title'],
                        "description": enriched_description,
                        "checklist": checklist[:7],
                        "deliverable": deliverable,
                        "lab_files": lab_files[:4],
                        "lab_recommendations": lab_recs[:3],
                        "phase_type": ptype,
                        "estimated_minutes": p.get("estimated_minutes"),
                        "_deep_subtasks": deep_subtasks,
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
        # BƯỚC 6: Build response — Deep Plan (Divide & Conquer)
        # NODE 2+3+4 inline: Dependency Map + Risk Annotator + Formatter
        # ═══════════════════════════════════════════════════════════
        plan_summary = _render_deep_plan_summary(
            group_id=group_id,
            lab_id=lab_id,
            lab_objective=lab_objective,
            plan_members=plan_members,
            phases=phases,
            references=references,
            common_pitfalls=common_pitfalls,
        )

        # Build todo_list: flattened tasks for tracking
        # Dùng _deep_subtasks để tạo granular checklist nếu có
        todo_list = []
        for pm in plan_members:
            for t in pm["tasks"]:
                deep = t.get("_deep_subtasks", [])
                if deep:
                    # Flatten subtasks thành checklist items
                    cl = [f"{st['subtask_id']}: {st['title']}" for st in deep]
                else:
                    cl = t.get("checklist", [])
                todo_list.append({
                    "group_id": group_id,
                    "user_id": pm["user_id"],
                    "role": pm["role"],
                    "task_id": t["task_id"],
                    "title": t["title"],
                    "checklist": cl,
                    "deliverable": t.get("deliverable", ""),
                    "status": "in_progress",
                })

        return {
            "status": "success", "group_id": group_id, "lab_id": lab_id,
            "lab_objective": lab_objective or "Mục tiêu bài lab",
            "setup_instructions": setup_instructions,
            "grading_rubrics": grading_rubrics,
            "common_pitfalls": common_pitfalls,
            "phases": phases,
            "members_plan": plan_members,
            "todo_list": todo_list,
            "references": references,
            "summary": plan_summary,
            "note": "Dùng `track_group_progress` để xem tiến độ, `update_group_progress` để cập nhật.",
        }

    except Exception as e:
        return {"status": "error", "error_code": "PLAN_FAILED",
                "message": f"Không thể tạo kế hoạch nhóm: {e}"}


def get_group_plan() -> Dict[str, Any]:
    """
    2. get_group_plan
    Mô tả: Đọc kế hoạch hiện tại của một nhóm từ DB.
    group_id được auto-resolve từ Discord context (chỉ dùng được trong group room).
    """
    try:
        group_id = _resolve_group_id()
        if not group_id:
            return {"status": "empty", "error_code": "NO_CONTEXT",
                    "message": "Tool chỉ dùng được trong group room Discord."}

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


def track_group_progress() -> Dict[str, Any]:
    """
    3. track_group_progress
    Mô tả: Xem tiến độ làm lab của nhóm. KIỂM TRA PLAN TRƯỚC — nếu team chưa chốt plan thì báo.
    group_id được auto-resolve từ Discord context (chỉ dùng được trong group room).
    """
    try:
        group_id = _resolve_group_id()
        if not group_id:
            return {"status": "empty", "error_code": "NO_CONTEXT",
                    "message": "Tool chỉ dùng được trong group room Discord."}

        # ── Bước 1: Kiểm tra team đã chốt plan chưa ──
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT plan_json FROM group_plans WHERE group_id = ? ORDER BY created_at DESC LIMIT 1",
            (group_id,))
        plan_row = cursor.fetchone()

        if not plan_row:
            conn.close()
            return {"status": "empty", "error_code": "NO_PLAN",
                    "message": f"Nhóm {group_id} chưa chốt kế hoạch. Hãy yêu cầu leader gọi `generate_group_plan` để tạo plan trước."}

        # ── Bước 2: Load plan để biết todo_list ──
        plan_data = json.loads(plan_row["plan_json"])
        todo_list = plan_data.get("todo_list", [])

        # ── Bước 3: Track từ assignments ──
        cursor.execute("SELECT * FROM assignments WHERE group_id = ?", (group_id,))
        rows = cursor.fetchall()

        if not rows:
            conn.close()
            # Có plan nhưng chưa có assignment (chưa generate) → báo
            overall_pct = 0.0
            total_tasks = len(todo_list)
            members_progress = []
            for item in todo_list:
                members_progress.append({
                    "user_id": item["user_id"],
                    "role": item.get("role", ""),
                    "task_id": item["task_id"],
                    "task_title": item["title"],
                    "checklist_count": len(item.get("checklist", [])),
                    "status": "in_progress",
                    "completed_checklist": 0,
                    "total_checklist": max(len(item.get("checklist", [])), 1),
                })
            conn.close()
            return {
                "status": "success", "group_id": group_id,
                "overall_completion_percent": overall_pct,
                "total_tasks": total_tasks,
                "completed_tasks": 0,
                "members_progress": members_progress,
            }

        total_tasks = len(rows)
        completed_tasks = sum(1 for r in rows if r["status"] == "completed")
        overall_pct = round((completed_tasks / total_tasks) * 100.0, 1) if total_tasks > 0 else 0.0

        # ── Bước 4: Build progress bar ──
        bar_len = 20
        filled = int(bar_len * overall_pct / 100)
        bar = "█" * filled + "░" * (bar_len - filled)

        members_progress = []
        for r in rows:
            ck = r["completed_checklist"]
            tk = r["total_checklist"]
            pct_task = round((ck / tk) * 100, 1) if tk > 0 else 0
            members_progress.append({
                "user_id": r["user_id"],
                "task_id": r["task_id"],
                "task_title": r["task_title"] or f"Task {r['task_id']}",
                "status": r["status"],
                "completed_checklist": ck,
                "total_checklist": tk,
                "task_completion_pct": pct_task,
            })

        conn.close()

        return {
            "status": "success", "group_id": group_id,
            "overall_completion_percent": overall_pct,
            "progress_bar": f"[{bar}] {overall_pct}%",
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "members_progress": members_progress,
        }
    except Exception as e:
        return {"status": "error", "error_code": "TRACKING_FAILED",
                "message": f"Không thể lấy tiến độ nhóm: {e}"}


def update_group_progress(
    task_id: str,
    status: Optional[str] = None,
    completed_checklist: Optional[int] = None,
) -> Dict[str, Any]:
    """
    4. update_group_progress
    Mô tả: Cập nhật tiến độ của một thành viên trong nhóm dựa trên task_id từ plan.
    group_id + user_id được auto-resolve từ Discord context.
    Nếu status=completed, tự động set completed_checklist=total_checklist.
    """
    try:
        group_id = _resolve_group_id()
        user_id = _resolve_user_id()
        if not group_id or not user_id:
            return {"status": "empty", "error_code": "NO_CONTEXT",
                    "message": "Tool chỉ dùng được trong Discord group room."}
        if not task_id or not task_id.strip():
            return {"status": "empty", "error_code": "INVALID_INPUT",
                    "message": "task_id không được để trống."}

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
                    "message": f"Không tìm thấy assignment cho user {user_id} - {task_id} trong nhóm {group_id}. Cần leader tạo plan trước."}

        # ── Auto-logic: completed → full checklist ──
        total_checklist = row["total_checklist"]
        if status == "completed":
            completed_checklist = total_checklist

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

        # ── Tính tiến độ tổng sau update ──
        cursor.execute("SELECT COUNT(*) as total, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as done "
                       "FROM assignments WHERE group_id = ?", (group_id,))
        agg = cursor.fetchone()
        total_all = agg["total"] or 0
        done_all = agg["done"] or 0
        overall_pct = round((done_all / total_all) * 100, 1) if total_all > 0 else 0
        conn.close()

        return {
            "status": "success", "group_id": group_id, "user_id": user_id,
            "task_id": task_id,
            "new_status": updated["status"] if updated else status,
            "completed_checklist": updated["completed_checklist"] if updated else completed_checklist,
            "total_checklist": updated["total_checklist"] if updated else total_checklist,
            "overall_team_progress_pct": overall_pct,
            "message": "Đã cập nhật tiến độ thành công.",
        }
    except Exception as e:
        return {"status": "error", "error_code": "UPDATE_FAILED",
                "message": f"Không thể cập nhật tiến độ: {e}"}


def list_members() -> Dict[str, Any]:
    """
    5. list_members
    Mô tả: Liệt kê danh sách thành viên trong group room hiện tại (id + tên).
    Dùng khi leader không @mention thành viên — agent tự identify ai là ai.
    Chỉ dùng được trong group room.
    """
    try:
        ctx = discord_context.get()
        if not ctx or not ctx.group_id:
            return {"status": "empty", "error_code": "NO_CONTEXT",
                    "message": "Tool chỉ dùng được trong group room Discord."}

        members = ctx.members or []
        return {
            "status": "success",
            "group_id": ctx.group_id,
            "channel_type": ctx.channel_type or "group_room",
            "members": members,
            "total": len(members),
            "note": "Dùng các ID này để truyền vào generate_group_plan. Ưu tiên @mention nếu có thể.",
        }
    except Exception as e:
        return {"status": "error", "error_code": "LIST_FAILED",
                "message": f"Không thể lấy danh sách thành viên: {e}"}
