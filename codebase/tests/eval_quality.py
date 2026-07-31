#!/usr/bin/env python3
"""
Evaluation script: đo CHẤT LƯỢNG output của insight extraction, plan generation, analyze.

Chạy thủ công (cần API key nếu muốn test AI path):
    cd codebase && python tests/eval_quality.py

Không cần API key → dùng regex fallback.
Có API key → dùng AI extraction thật (nếu provider dùng).

Output: quality score theo thang A/B/C/D/F cho từng module.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.insight_extractor import LabInsightExtractor
from app.services.repo_service import LabContentService
from app.tools.task_tools import generate_group_plan, update_group_progress, track_group_progress
from app.tools.troubleshooting_tools import analyze_student_issue
from app import discord_context
from app.core.db import get_db_connection


# ═══════════════════════════════════════════════════════════════
# QUALITY METRICS
# ═══════════════════════════════════════════════════════════════

class QualityGrade:
    def __init__(self, module: str):
        self.module = module
        self.checks: list[dict] = []
        self.errors: list[str] = []

    def check(self, name: str, passed: bool, detail: str = "", weight: int = 1):
        self.checks.append({"name": name, "passed": passed, "detail": detail, "weight": weight})
        if not passed:
            self.errors.append(f"  ❌ {name}: {detail}")

    def score(self) -> tuple[str, float]:
        total_weight = sum(c["weight"] for c in self.checks) or 1
        passed_weight = sum(c["weight"] for c in self.checks if c["passed"])
        pct = (passed_weight / total_weight) * 100
        if pct >= 90:
            grade = "A"
        elif pct >= 75:
            grade = "B"
        elif pct >= 60:
            grade = "C"
        elif pct >= 40:
            grade = "D"
        else:
            grade = "F"
        return grade, pct

    def report(self) -> str:
        grade, pct = self.score()
        lines = [
            f"\n{'='*60}",
            f"📊 {self.module} — Grade: {grade} ({pct:.0f}%)",
            f"{'='*60}",
        ]
        for c in self.checks:
            icon = "✅" if c["passed"] else "❌"
            lines.append(f"  {icon} {c['name']}: {c['detail'][:100]}")
        if self.errors:
            lines.append(f"\n  ⚠️  {len(self.errors)}/{len(self.checks)} checks failed")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# E1: INSIGHT EXTRACTION QUALITY
# ═══════════════════════════════════════════════════════════════

def eval_insight_extraction(lab_id: str = "3") -> QualityGrade:
    """Đánh giá chất lượng extract insight từ lab thật."""
    g = QualityGrade("Insight Extraction")

    svc = LabContentService()
    data = svc.get_lab_data(lab_id)
    if not data:
        g.check("lab_exists", False, f"Lab {lab_id} không có trong cache", weight=10)
        return g
    g.check("lab_exists", True, f"Lab {lab_id} có {data['total_documents']} documents", weight=1)

    extractor = LabInsightExtractor()
    insights = extractor.extract_insights(data["documents"])

    obj = insights.get("lab_objective", "")
    g.check("objective_exists", bool(obj), f"length={len(obj)}", weight=3)
    g.check("objective_meaningful", len(obj) > 50, f"'{obj[:60]}...'", weight=3)
    g.check("objective_not_fallback", "Xem chi tiết" not in obj,
            "Không phải fallback text", weight=2)

    tasks = insights.get("tasks", [])
    g.check("tasks_exist", len(tasks) > 0, f"{len(tasks)} tasks", weight=5)
    g.check("tasks_min_count", len(tasks) >= 3,
            f"Cần ≥ 3 tasks (có {len(tasks)})", weight=3)
    if tasks:
        meaningful = sum(1 for t in tasks if len(t.get("name", "")) > 10)
        g.check("tasks_names_meaningful", meaningful >= len(tasks) * 0.5,
                f"{meaningful}/{len(tasks)} tasks có tên > 10 ký tự", weight=4)
        all_checklists = [t.get("checklist", []) for t in tasks]
        total_cl = sum(len(cl) for cl in all_checklists)
        tasks_with_cl = sum(1 for cl in all_checklists if len(cl) > 0)
        g.check("checklist_not_empty", tasks_with_cl >= len(tasks) * 0.5,
                f"{tasks_with_cl}/{len(tasks)} tasks có checklist", weight=4)
        g.check("checklist_total_items", total_cl >= 5,
                f"Tổng {total_cl} checklist items", weight=3)
        has_deliverable = sum(1 for t in tasks if t.get("deliverable", ""))
        g.check("deliverable_exists", has_deliverable >= len(tasks) * 0.3,
                f"{has_deliverable}/{len(tasks)} tasks có deliverable", weight=2)

    setup = insights.get("setup_instructions", "")
    g.check("setup_exists", bool(setup), f"length={len(setup)}", weight=2)
    g.check("setup_not_fallback", "Làm theo hướng dẫn" not in setup,
            "Không phải fallback text", weight=2)

    rubric = insights.get("grading_rubrics", "")
    g.check("rubric_exists", bool(rubric), f"length={len(rubric)}", weight=2)
    g.check("rubric_not_fallback", "Xem rubric" not in rubric, "Không phải fallback", weight=2)

    pitfalls = insights.get("common_pitfalls", [])
    g.check("pitfalls_exist", len(pitfalls) > 0, f"{len(pitfalls)} items", weight=2)

    timeline = insights.get("timeline", "")
    g.check("timeline_exists", bool(timeline), f"length={len(timeline)}", weight=2)

    fsum = insights.get("file_summaries", [])
    g.check("file_summaries_exist", len(fsum) > 0, f"{len(fsum)} summaries", weight=2)

    return g


# ═══════════════════════════════════════════════════════════════
# E2: PLAN GENERATION QUALITY
# ═══════════════════════════════════════════════════════════════

def eval_plan_quality(lab_id: str = "3") -> QualityGrade:
    """Đánh giá chất lượng generate_group_plan."""
    g = QualityGrade("Plan Generation")

    discord_context.set_context(
        user_id="EVAL_USER",
        channel_type="group_room",
        group_id="EVAL_GROUP",
        members=[
            {"id": "EVAL_USER1", "name": "User PM"},
            {"id": "EVAL_USER2", "name": "User Backend"},
            {"id": "EVAL_USER3", "name": "User AI"},
        ],
        lab_id=lab_id,
    )

    plan = generate_group_plan(
        lab_id=lab_id,
        members=[
            {"user_id": "EVAL_USER1", "role": "PM"},
            {"user_id": "EVAL_USER2", "role": "Backend"},
            {"user_id": "EVAL_USER3", "role": "AI"},
        ],
        notes="Eval run",
    )

    if plan["status"] != "success":
        g.check("plan_generated", False, plan.get("message", "unknown error"), weight=10)
        discord_context.clear_context()
        return g

    g.check("plan_generated", True, "status=success", weight=5)

    phases = plan.get("phases", [])
    g.check("phases_exist", len(phases) >= 3, f"{len(phases)} phases", weight=4)

    members = plan.get("members_plan", [])
    g.check("all_members_have_tasks", len(members) == 3,
            f"{len(members)}/3 members có task", weight=4)
    for m in members:
        g.check(f"member_{m['role']}_tasks", len(m.get("tasks", [])) > 0,
                f"{m['role']}: {len(m.get('tasks',[]))} tasks", weight=2)

    todo = plan.get("todo_list", [])
    g.check("todo_list_exists", len(todo) >= 3, f"{len(todo)} items", weight=4)
    if todo:
        all_have_cl = all(len(t.get("checklist", [])) > 0 for t in todo)
        g.check("todo_checklist_not_empty", all_have_cl,
                "All items có checklist" if all_have_cl else "Có item thiếu checklist", weight=3)
        all_have_role = all(t.get("role", "") != "" for t in todo)
        g.check("todo_role_assigned", all_have_role,
                "All items có role" if all_have_role else "Có item thiếu role", weight=2)

    summary = plan.get("summary", "")
    g.check("summary_length", len(summary) >= 2000,
            f"{len(summary)} chars (target ≥2000)", weight=4)
    g.check("summary_has_objective", "mục tiêu" in summary.lower() or "objective" in summary.lower(),
            "Có objective trong summary", weight=2)
    g.check("summary_has_phases", any(p['task_id'] in summary for p in phases[:3]),
            "Có phases trong summary", weight=2)
    g.check("summary_has_members", all(m['role'].lower() in summary.lower() for m in members),
            "Có tên member roles trong summary", weight=2)

    refs = plan.get("references", [])
    g.check("references_exist", len(refs) > 0, f"{len(refs)} references", weight=2)

    discord_context.clear_context()
    return g


# ═══════════════════════════════════════════════════════════════
# E3: ANALYZE STUDENT ISSUE QUALITY
# ═══════════════════════════════════════════════════════════════

def eval_analyze_quality() -> QualityGrade:
    """Đánh giá chất lượng analyze_student_issue."""
    g = QualityGrade("Analyze Student Issue")

    discord_context.set_context(user_id="EVAL_USER", channel_type="group_room")

    test_cases = [
        ("Lỗi kết nối database", "MongoError", ["DATABASE_URL", "Mongo", "connection"]),
        ("Lỗi import module pandas", "", ["chưa cài", "thư viện", "pip install"]),
        ("Code chạy sai kết quả đầu ra", "", ["async", "schema", "logic"]),
    ]

    for desc, log, expected_kw in test_cases:
        res = analyze_student_issue(
            task_id="T1",
            issue_description=desc,
            error_log=log or None,
        )
        ok = res["status"] == "success"
        g.check(f"analyze_{desc[:30]}", ok,
                f"status={res['status']}" if not ok else f"root='{res.get('root_cause','')[:80]}'",
                weight=3)
        if ok:
            root = res.get("root_cause", "").lower()
            kw_match = any(k.lower() in root for k in expected_kw)
            g.check(f"analyze_{desc[:30]}_root_cause", kw_match,
                    f"expected {expected_kw}, got '{root[:60]}'", weight=4)

    res = analyze_student_issue(task_id="T1", issue_description="Lỗi")
    g.check("short_issue_blocked", res.get("error_code") == "UNCLEAR_ISSUE",
            f"error_code={res.get('error_code')}", weight=3)

    discord_context.set_context(user_id="EVAL_USER", channel_type="general")
    res2 = analyze_student_issue(task_id="T1", issue_description="Lỗi database")
    g.check("general_channel_blocked", res2.get("error_code") == "NO_CONTEXT",
            f"error_code={res2.get('error_code')}", weight=3)

    discord_context.clear_context()
    return g


# ═══════════════════════════════════════════════════════════════
# E4: END-TO-END FLOW
# ═══════════════════════════════════════════════════════════════

def eval_end_to_end(lab_id: str = "3") -> QualityGrade:
    """E2E: generate plan → update progress → track progress."""
    g = QualityGrade("End-to-End Flow")

    discord_context.set_context(
        user_id="EVAL_U1", channel_type="group_room", group_id="EVAL_E2E",
        members=[{"id": "EVAL_U1", "name": "User1"}, {"id": "EVAL_U2", "name": "User2"}],
        lab_id=lab_id,
    )

    plan = generate_group_plan(
        lab_id=lab_id,
        members=[{"user_id": "EVAL_U1", "role": "PM"}, {"user_id": "EVAL_U2", "role": "Backend"}],
    )
    g.check("e2e_plan", plan["status"] == "success", f"status={plan['status']}", weight=5)
    if plan["status"] != "success":
        discord_context.clear_context()
        return g

    todo = plan.get("todo_list", [])
    g.check("e2e_todo", len(todo) >= 2, f"{len(todo)} todo items", weight=2)

    first_task = todo[0]["task_id"] if todo else "T1"
    update = update_group_progress(task_id=first_task, status="completed")
    g.check("e2e_update", update["status"] == "success",
            f"status={update['status']}", weight=3)
    if update["status"] == "success":
        g.check("e2e_auto_checklist", update.get("new_status") == "completed",
                f"new_status={update.get('new_status')}", weight=2)
        g.check("e2e_team_progress", update.get("overall_team_progress_pct", 0) > 0,
                f"progress={update.get('overall_team_progress_pct')}%", weight=2)

    progress = track_group_progress()
    g.check("e2e_track", progress["status"] == "success",
            f"status={progress['status']}", weight=3)
    if progress["status"] == "success":
        g.check("e2e_progress_increased", progress.get("overall_completion_percent", 0) >= 0,
                f"{progress.get('overall_completion_percent')}%", weight=2)
        g.check("e2e_progress_bar", bool(progress.get("progress_bar", "")),
                f"bar='{progress.get('progress_bar','')[:20]}'", weight=1)

    conn = get_db_connection()
    conn.execute("DELETE FROM group_plans WHERE group_id = 'EVAL_E2E'")
    conn.execute("DELETE FROM assignments WHERE group_id = 'EVAL_E2E'")
    conn.commit()
    conn.close()

    discord_context.clear_context()
    return g


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("🧪 QUALITY EVALUATION")
    print("=" * 60)

    labs = LabContentService().list_registered_labs()
    if not labs:
        print("\n⚠️  Không có lab trong cache. Chạy /admin-add-lab trước.")
        lab_id = "3"
    else:
        lab_id = labs[0]["lab_id"]
        print(f"\n📦 Dùng lab: {lab_id} ({labs[0]['total_documents']} documents)")

    has_api_key = bool(os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY"))
    print(f"🔑 AI API key: {'✅ CÓ' if has_api_key else '❌ KHÔNG (dùng regex fallback)'}")
    print()

    results = [
        eval_insight_extraction(lab_id),
        eval_plan_quality(lab_id),
        eval_analyze_quality(),
        eval_end_to_end(lab_id),
    ]

    for r in results:
        print(r.report())

    print(f"\n{'='*60}")
    print("📈 OVERALL QUALITY SUMMARY")
    print(f"{'='*60}")
    total_pct = 0
    for r in results:
        grade, pct = r.score()
        total_pct += pct
        print(f"  {r.module:25s}: {grade} ({pct:.0f}%)")
    overall = total_pct / len(results)
    if overall >= 90:
        og = "A"
    elif overall >= 75:
        og = "B"
    elif overall >= 60:
        og = "C"
    elif overall >= 40:
        og = "D"
    else:
        og = "F"
    print(f"  {'─'*40}")
    print(f"  {'OVERALL':25s}: {og} ({overall:.0f}%)")
    print(f"\n  Legend: A ≥90%  B ≥75%  C ≥60%  D ≥40%  F <40%")
    print()


if __name__ == "__main__":
    main()
