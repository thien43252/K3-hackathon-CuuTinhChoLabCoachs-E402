"""
Module chứa các công cụ Tri thức & Tra cứu nội dung Lab (Knowledge Tools).
Bao gồm:
1. get_lab_content
"""

from typing import Any, Dict, List, Optional
from app.services.repo_service import LabContentService

# Singleton service
_LAB_SERVICE = LabContentService()

# Keywords phát hiện sections quan trọng
_IMPORTANT_KW = [
    "yêu cầu", "requirement", "checklist", "rubric", "chấm", "nghiệm thu",
    "hướng dẫn", "guide", "cài đặt", "setup", "install", "prerequisite",
    "lưu ý", "note", "pitfall", "bẫy", "cảnh báo", "warning",
    "nộp", "submit", "deadline", "timeline", "lịch trình",
    "tool", "function", "api", "spec", "schema",
]


def get_lab_content(lab_id: str = "") -> Dict[str, Any]:
    """
    1. get_lab_content
    Trả về TOÀN BỘ nội dung lab từ cache: insights + documents + code + key sections.
    Nếu lab_id để trống, tự động resolve từ Discord context (lab hôm nay).
    Dùng context này để trả lời learner CHI TIẾT, không bỏ sót file .md nào.
    """
    try:
        if not lab_id or not lab_id.strip():
            # Auto-resolve từ Discord context
            from app import discord_context
            ctx = discord_context.get()
            if ctx and ctx.lab_id:
                lab_id = ctx.lab_id
            else:
                return {"status": "empty", "error_code": "INVALID_INPUT",
                        "message": "lab_id không được để trống và không có lab trong context hôm nay."}

        data = _LAB_SERVICE.get_lab_data(lab_id)
        if not data:
            return {"status": "empty", "error_code": "NO_CACHED_DATA",
                    "message": f"Không tìm thấy nội dung lab '{lab_id}'. Admin cần /admin-add-lab trước."}

        insights  = data.get("insights", {})
        documents = data.get("documents", [])
        sitemap   = data.get("sitemap", [])

        # ── 1. Insights ──
        lab_objective      = insights.get("lab_objective", "")
        setup_instructions = insights.get("setup_instructions", "")
        grading_rubrics    = insights.get("grading_rubrics", "")
        common_pitfalls    = insights.get("common_pitfalls", [])
        draft_tasks        = insights.get("tasks", [])
        timeline           = insights.get("timeline", "")
        file_summaries     = insights.get("file_summaries", [])

        # ── 2. Documents summary ──
        docs_list = []
        for doc in documents:
            sections = []
            for sec in doc.get("sections", [])[:10]:
                sections.append({
                    "heading": sec.get("heading", ""),
                    "level": sec.get("level", 2),
                    "content": sec.get("content", "")[:300],
                })
            docs_list.append({
                "file": doc.get("relative_path", ""),
                "title": doc.get("title", ""),
                "section_count": len(doc.get("sections", [])),
                "sections": sections,
            })

        # ── 3. Code examples (top 8) ──
        code_examples = []
        for doc in documents:
            for cb in doc.get("code_blocks", []):
                code = cb.get("code", "").strip()
                if len(code) > 15 and len(code_examples) < 8:
                    code_examples.append({
                        "file": doc.get("relative_path", ""),
                        "language": cb.get("language", "text"),
                        "code": code[:500],
                    })

        # ── 4. Key sections ──
        key_sections = []
        for doc in documents:
            for sec in doc.get("sections", []):
                h = sec.get("heading", "").lower()
                if any(kw in h for kw in _IMPORTANT_KW):
                    key_sections.append({
                        "file": doc.get("relative_path", ""),
                        "heading": sec.get("heading", ""),
                        "content": sec.get("content", "")[:500],
                    })

        # ── 5. Sitemap ──
        sitemap_detail = [{"file": s.get("relative_path", ""), "title": s.get("title", "")}
                          for s in sitemap[:15]]

        return {
            "status": "success",
            "lab_id": lab_id,
            # Insights
            "lab_objective": lab_objective,
            "timeline": timeline,
            "setup_instructions": setup_instructions,
            "tasks": draft_tasks,
            "grading_rubrics": grading_rubrics,
            "common_pitfalls": common_pitfalls,
            "file_summaries": file_summaries,
            # Documents
            "total_documents": data.get("total_documents", 0),
            "sitemap": sitemap_detail,
            "documents": docs_list,
            "code_examples": code_examples,
            "key_sections": key_sections,
        }
    except Exception as e:
        return {"status": "error", "error_code": "CONTENT_LOOKUP_FAILED",
                "message": f"Không thể truy xuất nội dung lab: {e}"}
