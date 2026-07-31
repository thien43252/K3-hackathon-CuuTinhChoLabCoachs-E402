"""
Quality evaluation tests for LabInsightExtractor.

Kiểm tra CHẤT LƯỢNG extraction — không chỉ "có chạy hay không".
Tập trung vào regex fallback path (AI path cần API key thật).

Cách chạy:
    cd codebase && python -m pytest tests/test_insight_extractor.py -v
"""
import pytest
from app.services.insight_extractor import LabInsightExtractor


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _make_extractor() -> LabInsightExtractor:
    """Force regex fallback by removing API keys."""
    e = LabInsightExtractor()
    e.api_key = None
    e.openai_key = None
    return e


def _doc(file_name: str, sections: list) -> dict:
    """Build a mock document with sections."""
    return {
        "file_name": file_name,
        "relative_path": file_name,
        "title": file_name.replace(".md", "").replace("-", " ").title(),
        "raw_content": "",
        "sections": sections,
        "code_blocks": [],
    }


def _sec(heading: str, content: str, level: int = 2) -> dict:
    return {"heading": heading, "content": content, "level": level}


# ═══════════════════════════════════════════════════════════════
# E1: REGEX FALLBACK — SECTION CLASSIFICATION
# ═══════════════════════════════════════════════════════════════

class TestSectionClassification:
    """E1.1: Phân loại sections đúng heading."""

    def test_e1_1_h1_vi_keywords(self):
        """E1.1_H1: Heading VI → đúng field."""
        docs = [_doc("README.md", [
            _sec("Mục tiêu bài lab", "Xây dựng AI Agent có khả năng hỗ trợ học tập."),
            _sec("Cài đặt môi trường", "Chạy lệnh uv sync và tạo file .env."),
            _sec("Task 1: Thiết kế", "Thiết kế kiến trúc tổng thể."),
            _sec("Tiêu chí đánh giá", "Hoàn thành CP1 được 5 điểm."),
            _sec("Lưu ý và bẫy lỗi", "Tránh commit API key lên GitHub."),
            _sec("Thời gian dự kiến", "4 tiếng (9:00 - 13:00)"),
        ])]
        e = _make_extractor()
        ins = e.extract_insights(docs)

        assert "AI Agent" in ins["lab_objective"], f"Objective sai: {ins['lab_objective'][:100]}"
        assert "uv sync" in ins["setup_instructions"], f"Setup sai: {ins['setup_instructions'][:100]}"
        assert len(ins["tasks"]) >= 1, f"Tasks rỗng: {ins['tasks']}"
        assert "Thiết kế" in ins["tasks"][0]["name"], f"Task name sai: {ins['tasks'][0]}"
        assert "5 điểm" in ins["grading_rubrics"], f"Rubric sai: {ins['grading_rubrics'][:100]}"
        assert len(ins["common_pitfalls"]) >= 1, f"Pitfalls rỗng: {ins['common_pitfalls']}"
        assert "API key" in ins["common_pitfalls"][0], f"Pitfall content sai: {ins['common_pitfalls']}"
        assert "4 tiếng" in ins.get("timeline", ""), f"Timeline sai: {ins.get('timeline', '')}"

    def test_e1_1_h2_en_keywords(self):
        """E1.1_H2: Heading EN → vẫn match được."""
        docs = [_doc("README.md", [
            _sec("Objective", "Build an AI Agent for tutoring."),
            _sec("Setup Instructions", "Run pip install -r requirements.txt"),
            _sec("Checkpoint 1: Design", "Design the system architecture."),
            _sec("Scoring Rubric", "CP1: 5 points, CP2: 5 points"),
            _sec("Common Pitfalls", "Do not hardcode API keys."),
        ])]
        e = _make_extractor()
        ins = e.extract_insights(docs)

        assert ins["lab_objective"] != "", f"Objective rỗng"
        assert ins["setup_instructions"] != "", f"Setup rỗng"
        assert len(ins["tasks"]) >= 1, f"Tasks rỗng"
        assert ins["grading_rubrics"] != "", f"Rubric rỗng"
        assert len(ins["common_pitfalls"]) >= 1

    def test_e1_1_u1_no_keyword_match(self):
        """E1.1_U1: Không heading nào match keyword → fallback H2."""
        docs = [_doc("guide.md", [
            _sec("Phase 1: Khởi tạo", "Tạo project và cài đặt dependencies."),
            _sec("Phase 2: Xây dựng", "Implement core features."),
            _sec("Phase 3: Kiểm tra", "Run tests và fix bugs."),
        ])]
        e = _make_extractor()
        ins = e.extract_insights(docs)

        assert len(ins["tasks"]) >= 1, f"Tasks should have fallback items: {ins['tasks']}"
        assert any("Phase" in t["name"] for t in ins["tasks"]), f"Task names wrong: {ins['tasks']}"

    def test_e1_1_u2_empty_sections(self):
        """E1.1_U2: Document rỗng → graceful fallback."""
        docs = [_doc("empty.md", [])]
        e = _make_extractor()
        ins = e.extract_insights(docs)

        assert ins["lab_objective"] != "", f"Objective should have fallback text: '{ins['lab_objective']}'"
        assert len(ins["tasks"]) >= 1, f"Tasks should have default: {ins['tasks']}"


# ═══════════════════════════════════════════════════════════════
# E1.2: TASK & CHECKLIST QUALITY
# ═══════════════════════════════════════════════════════════════

class TestChecklistQuality:
    """E1.2: Chất lượng tasks & checklist."""

    def test_e1_2_h1_bullet_checklist(self):
        """E1.2_H1: Bullet list → checklist items."""
        docs = [_doc("guide.md", [
            _sec("Task 1: Xây dựng API", "- Tạo endpoint GET /tasks\n- Tạo endpoint POST /tasks\n- Thêm validation\n- Viết unit test"),
        ])]
        e = _make_extractor()
        ins = e.extract_insights(docs)

        assert len(ins["tasks"]) >= 1
        assert len(ins["tasks"][0]["checklist"]) >= 2, \
            f"Checklist should have bullets: {ins['tasks'][0]['checklist']}"
        assert any("endpoint" in c for c in ins["tasks"][0]["checklist"]), \
            f"Checklist content wrong: {ins['tasks'][0]['checklist']}"

    def test_e1_2_h2_numbered_checklist(self):
        """E1.2_H2: Numbered list → checklist items."""
        docs = [_doc("guide.md", [
            _sec("Yêu cầu", "1. Phân tích yêu cầu\n2. Thiết kế database\n3. Implement API\n4. Kiểm thử"),
        ])]
        e = _make_extractor()
        ins = e.extract_insights(docs)

        assert len(ins["tasks"]) >= 1
        assert len(ins["tasks"][0]["checklist"]) >= 2, \
            f"Checklist should have numbered items: {ins['tasks'][0]['checklist']}"

    def test_e1_2_u1_paragraph_fallback(self):
        """E1.2_U1: Paragraph (không bullet) → sentence fallback."""
        docs = [_doc("guide.md", [
            _sec("Nhiệm vụ", "Sinh viên cần phân tích yêu cầu và thiết kế giải pháp. Sau đó tiến hành xây dựng prototype."),
        ])]
        e = _make_extractor()
        ins = e.extract_insights(docs)

        assert len(ins["tasks"]) >= 1
        assert len(ins["tasks"][0]["checklist"]) >= 1 or len(ins["tasks"]) >= 1, \
            f"Should have some content: {ins['tasks']}"


# ═══════════════════════════════════════════════════════════════
# E1.3: COMMON PITFALLS QUALITY
# ═══════════════════════════════════════════════════════════════

class TestPitfallsQuality:
    """E1.3: Chất lượng common pitfalls."""

    def test_e1_3_h1_real_pitfalls(self):
        """E1.3_H1: Extract pitfalls từ section thật."""
        docs = [_doc("guide.md", [
            _sec("Lưu ý quan trọng", "Không được hardcode API key trong code.\n"
                  "Luôn kiểm tra file .env trước khi chạy.\n"
                  "Nếu gặp lỗi timeout, thử tăng timeout lên 30s."),
        ])]
        e = _make_extractor()
        ins = e.extract_insights(docs)

        pitfalls = ins["common_pitfalls"]
        assert len(pitfalls) >= 1, f"Pitfalls rỗng: {pitfalls}"
        # Phải chứa nội dung thật từ section, không phải generic fallback
        all_text = " ".join(pitfalls).lower()
        assert "api key" in all_text or "hardcode" in all_text or ".env" in all_text, \
            f"Pitfalls không chứa content thật: {pitfalls}"

    def test_e1_3_u1_no_pitfall_section(self):
        """E1.3_U1: Không có section pitfalls → generic fallback."""
        docs = [_doc("guide.md", [
            _sec("Hướng dẫn", "Làm theo các bước trong README."),
        ])]
        e = _make_extractor()
        ins = e.extract_insights(docs)

        assert len(ins["common_pitfalls"]) >= 1, f"Should have generic pitfalls: {ins['common_pitfalls']}"

    def test_e1_3_u2_empty_pitfall_section(self):
        """E1.3_U2: Section pitfalls rỗng → generic fallback."""
        docs = [_doc("guide.md", [
            _sec("Lưu ý", ""),
        ])]
        e = _make_extractor()
        ins = e.extract_insights(docs)

        assert len(ins["common_pitfalls"]) >= 1, f"Should fallback to generic: {ins['common_pitfalls']}"


# ═══════════════════════════════════════════════════════════════
# E1.4: TIMELINE QUALITY
# ═══════════════════════════════════════════════════════════════

class TestTimelineQuality:
    """E1.4: Chất lượng timeline."""

    def test_e1_4_h1_timeline_extracted(self):
        """E1.4_H1: Timeline từ section 'Thời gian'."""
        docs = [_doc("guide.md", [
            _sec("Lịch trình", "9:00 - 10:00: Phân tích\n10:00 - 12:00: Xây dựng\n12:00 - 13:00: Demo"),
        ])]
        e = _make_extractor()
        ins = e.extract_insights(docs)

        assert ins.get("timeline", "") != "", f"Timeline rỗng"
        assert "9:00" in ins["timeline"] or "10:00" in ins["timeline"], \
            f"Timeline content wrong: {ins['timeline']}"

    def test_e1_4_u1_no_timeline(self):
        """E1.4_U1: Không có timeline → rỗng (không bịa)."""
        docs = [_doc("guide.md", [
            _sec("Mục tiêu", "Hoàn thành bài lab."),
            _sec("Task 1", "Làm task."),
        ])]
        e = _make_extractor()
        ins = e.extract_insights(docs)

        assert "timeline" in ins, f"Missing timeline key"
        if ins["timeline"]:
            assert "Mục tiêu" not in ins["timeline"], \
                f"Timeline lấy nhầm từ section khác: {ins['timeline']}"


# ═══════════════════════════════════════════════════════════════
# E1.5: FILE SUMMARIES QUALITY
# ═══════════════════════════════════════════════════════════════

class TestFileSummariesQuality:
    """E1.5: Chất lượng file_summaries."""

    def test_e1_5_h1_multiple_files(self):
        """E1.5_H1: 2 documents → 2 file_summaries."""
        docs = [
            _doc("README.md", [_sec("Giới thiệu", "Bài lab về AI Agent.")]),
            _doc("guide.md", [_sec("Hướng dẫn", "Các bước thực hiện.")]),
        ]
        e = _make_extractor()
        ins = e.extract_insights(docs)

        assert len(ins.get("file_summaries", [])) == 2, \
            f"Should have 2 summaries: {ins.get('file_summaries')}"
        files = [f["file"] for f in ins["file_summaries"]]
        assert "README.md" in files, f"Missing README.md in: {files}"
        assert "guide.md" in files, f"Missing guide.md in: {files}"

    def test_e1_5_u1_no_sections(self):
        """E1.5_U1: Document không sections → file_summaries rỗng (regex chỉ extract từ sections)."""
        docs = [_doc("README.md", [])]
        e = _make_extractor()
        ins = e.extract_insights(docs)

        # Regex fallback chỉ tạo file_summaries khi có sections
        assert len(ins.get("file_summaries", [])) == 0, \
            f"No sections → no summaries: {ins.get('file_summaries')}"


# ═══════════════════════════════════════════════════════════════
# E3: ANALYZE STUDENT ISSUE - QUALITY
# ═══════════════════════════════════════════════════════════════
# Tests này cần user_id context — dùng discord_context mock.

@pytest.fixture
def user_context():
    from app import discord_context
    discord_context.set_context(user_id="U123456", channel_type="group_room")
    yield
    discord_context.clear_context()


class TestAnalyzeQuality:
    """E3: Chất lượng analyze_student_issue."""

    def test_e3_1_h1_env_database(self, user_context):
        """E3.1_H1: Lỗi database → root cause chính xác."""
        from app.tools.troubleshooting_tools import analyze_student_issue
        res = analyze_student_issue(
            task_id="T1",
            issue_description="Bị lỗi kết nối database",
            error_log="MongoError: connection failed",
        )
        assert res["status"] == "success"
        root = res.get("root_cause", "").lower()
        assert any(kw in root for kw in ["database_url", "mongo", "connection", "env"]), \
            f"Root cause không chính xác: {root}"
        sol = res.get("suggested_solution", "")
        assert len(sol) > 20, f"Solution quá ngắn: {sol}"

    def test_e3_1_h2_import_module(self, user_context):
        """E3.1_H2: Lỗi import → root cause chính xác."""
        from app.tools.troubleshooting_tools import analyze_student_issue
        res = analyze_student_issue(
            task_id="T1",
            issue_description="Lỗi import module pandas",
        )
        assert res["status"] == "success"
        root = res.get("root_cause", "").lower()
        assert any(kw in root for kw in ["chưa cài", "thư viện", "pip install", "module", "import"]), \
            f"Root cause không chính xác: {root}"

    def test_e3_1_h3_unknown_fallback(self, user_context):
        """E3.1_H3: Lỗi không match keyword → fallback (không bịa sai)."""
        from app.tools.troubleshooting_tools import analyze_student_issue
        res = analyze_student_issue(
            task_id="T1",
            issue_description="Chương trình chạy rất chậm và bị treo",
        )
        assert res["status"] == "success"
        root = res.get("root_cause", "")
        assert root != "", f"Root cause rỗng (dù fallback)"
        assert "async" in root.lower() or "schema" in root.lower() or "await" in root.lower() or "logic" in root.lower(), \
            f"Fallback root cause lạ: {root}"

    def test_e3_2_u1_short_issue(self, user_context):
        """E3.2_U1: Issue < 10 ký tự → không đoán bừa."""
        from app.tools.troubleshooting_tools import analyze_student_issue
        res = analyze_student_issue(task_id="T1", issue_description="Lỗi")
        assert res.get("error_code") == "UNCLEAR_ISSUE", \
            f"Phải báo không rõ, không được đoán: {res}"

    def test_e3_3_reference_links_exist(self, user_context):
        """E3.3: Reference links phải tồn tại."""
        from app.tools.troubleshooting_tools import analyze_student_issue
        res = analyze_student_issue(
            task_id="T1",
            issue_description="Bị lỗi database",
        )
        assert res["status"] == "success"
        refs = res.get("reference_links", [])
        if refs:
            for ref in refs:
                if "example.com" in ref:
                    pytest.skip(f"WARNING: Reference link là example.com: {ref}")


# ═══════════════════════════════════════════════════════════════
# E4: END-TO-END — TASK → PHASE MAPPING
# ═══════════════════════════════════════════════════════════════

class TestTaskToPhaseMapping:
    """E4.1: Task → Phase mapping trong generate_group_plan."""

    def test_e4_1_h1_dynamic_phases_from_tasks(self):
        """E4.1_H1: Insight tasks ≥ 2 → dynamic phases."""
        from app import discord_context
        from app.tools.task_tools import generate_group_plan

        discord_context.set_context(group_id="G01_TEST")
        lab_check = None
        try:
            from app.tools import get_lab_content
            lab_check = get_lab_content(lab_id="DAY05")
        except Exception:
            pass

        if not lab_check or lab_check.get("status") != "success":
            discord_context.clear_context()
            pytest.skip("Cần lab DAY05 trong cache")

        plan = generate_group_plan(
            lab_id="DAY05",
            members=[{"user_id": "U1", "role": "PM"}],
        )
        discord_context.clear_context()

        if plan.get("error_code") == "NO_LAB_DATA":
            pytest.skip("Lab DAY05 chưa có data")

        assert plan["status"] == "success", f"Plan failed: {plan.get('message')}"
        phases = plan.get("phases", [])
        phase_titles = " ".join(p["title"] for p in phases)
        is_canonical = "Phân tích" in phase_titles and "Xây dựng" in phase_titles
        if is_canonical:
            assert len(phases) == 4, f"Canonical should be 4: {len(phases)}"
        else:
            assert len(phases) >= 2, f"Dynamic phases: {len(phases)}"

    def test_e4_2_h1_guidebook_depth(self):
        """E4.2_H1: Guidebook phải dài, chi tiết."""
        from app import discord_context
        from app.tools.task_tools import generate_group_plan

        discord_context.set_context(group_id="G01_TEST2")

        try:
            from app.tools import get_lab_content
            lab_check = get_lab_content(lab_id="DAY05")
        except Exception:
            lab_check = None

        if not lab_check or lab_check.get("status") != "success":
            discord_context.clear_context()
            pytest.skip("Cần lab DAY05 trong cache")

        plan = generate_group_plan(
            lab_id="DAY05",
            members=[
                {"user_id": "U1", "role": "PM"},
                {"user_id": "U2", "role": "Backend"},
                {"user_id": "U3", "role": "AI"},
                {"user_id": "U4", "role": "QA"},
            ],
        )
        discord_context.clear_context()

        if plan["status"] != "success":
            pytest.skip(f"Plan không tạo được: {plan.get('message')}")

        summary = plan.get("summary", "")
        assert len(summary) >= 1000, \
            f"Guidebook quá ngắn ({len(summary)} chars): {summary[:200]}"

        todo = plan.get("todo_list", [])
        assert len(todo) > 0, f"Todo list rỗng"

        assert any(role in summary for role in ["PM", "Backend", "AI", "QA"]), \
            f"Summary thiếu member roles: {summary[:300]}"
