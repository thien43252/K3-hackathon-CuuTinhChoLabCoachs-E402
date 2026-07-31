# 🧠 DEEP PLANNING PROMPT — DIVIDE & CONQUER ARCHITECTURE
# Kiến trúc: LangGraph-style Multi-Node Pipeline
# Mục đích: Phân rã kế hoạch lab thành subtask sâu, có giá trị thực tế

---

## 🏗️ KIẾN TRÚC NODE PIPELINE (LangGraph-style)

```
[INPUT: Lab Plan + Members + Tasks]
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  NODE 0 — PLANNER (Sequential, blocking)                            │
│  Phân tích toàn bộ plan, xác định danh sách task cần phân rã       │
│  Output: task_list[] với metadata (owner, complexity, type)         │
└───────────────────────────┬─────────────────────────────────────────┘
                            │  Fan-out → Parallel
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ NODE 1-A         │ │ NODE 1-B         │ │ NODE 1-C ... N   │
│ Task Decomposer  │ │ Task Decomposer  │ │ Task Decomposer  │
│ (per task)       │ │ (per task)       │ │ (per task)       │
│ Gọi DECOMPOSE    │ │ Gọi DECOMPOSE    │ │ Gọi DECOMPOSE    │
│ _TASK_PROMPT     │ │ _TASK_PROMPT     │ │ _TASK_PROMPT     │
└────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘
         │                    │                    │  Join (aggregator)
         └────────────────────┴────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  NODE 2 — DEPENDENCY MAPPER (Sequential)                            │
│  Gắn dependency giữa các subtask (A→B, parallel vs sequential)     │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  NODE 3 — RISK & QUALITY ANNOTATOR                                  │
│  Gắn: DoD (Definition of Done), failure modes, antipatterns        │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  NODE 4 — FORMATTER (Sequential, final output)                      │
│  Format thành Markdown checklist có chiều sâu                       │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
               [OUTPUT: Deep Plan với subtask phân rã]
```

---

## NODE 0 — PLANNER PROMPT

```
SYSTEM: Bạn là một Senior Engineering Lead chuyên phân tích kế hoạch và chia nhỏ công việc.

TASK: Đọc kế hoạch lab sau và trả về JSON danh sách task cần phân rã.

INPUT:
- Kế hoạch: {PLAN_CONTENT}
- Thành viên: {MEMBERS_LIST}
- Tài liệu tham khảo: {DOCS_LIST}
- Thời gian: {DURATION_MINUTES} phút

OUTPUT FORMAT (JSON array):
[
  {
    "task_id": "T1",
    "task_name": "Tên task gốc",
    "owner": "Tên thành viên",
    "complexity": "low|medium|high",
    "task_type": "analysis|implementation|testing|documentation|integration",
    "estimated_minutes": 20,
    "needs_decomposition": true,
    "key_deliverables": ["file1.py", "doc.md"],
    "depends_on": []
  }
]

RULES:
- Chỉ phân tích, KHÔNG phân rã ở bước này
- complexity=high → needs_decomposition=true bắt buộc
- Liệt kê đủ tất cả task từ plan, không bỏ sót
```

---

## NODE 1 — TASK DECOMPOSER PROMPT (Per-task, chạy PARALLEL)

> Mỗi task chạy 1 LLM call độc lập — tất cả chạy song song (fan-out).
> Join lại ở NODE 2 sau khi tất cả hoàn thành.

```
SYSTEM: Bạn là một Agile Coach và Technical Lead chuyên phân rã task thành subtask có giá trị thực thi.

CONTEXT:
- Task đang phân rã: {TASK_ID} — {TASK_NAME}
- Owner: {OWNER_NAME}
- Task Type: {TASK_TYPE}
- Estimated time: {ESTIMATED_MINUTES} phút
- Key deliverables: {KEY_DELIVERABLES}
- Tài liệu tham khảo liên quan: {RELATED_DOCS}
- Lab content (relevant section): {LAB_CONTENT_EXCERPT}

MỤC TIÊU:
Phân rã task "{TASK_NAME}" thành 4-8 subtask cụ thể, có thứ tự ưu tiên rõ ràng.
Mỗi subtask phải có: mục đích rõ ràng, action step cụ thể, tiêu chí hoàn thành đo được.

OUTPUT FORMAT (JSON):
{
  "task_id": "T1",
  "task_name": "...",
  "subtasks": [
    {
      "subtask_id": "T1.1",
      "title": "Tiêu đề ngắn gọn (tối đa 10 từ)",
      "what": "Làm gì cụ thể (1-2 câu)",
      "why": "Tại sao cần bước này (mục đích trong big picture)",
      "how": [
        "Bước 1: ...",
        "Bước 2: ...",
        "Bước 3: ..."
      ],
      "input_needed": "Cần gì từ bước trước hoặc từ teammate",
      "output_artifact": "File/kết quả tạo ra (ví dụ: tools.py, table trong trace_eval.md)",
      "dod": "Definition of Done — tiêu chí pass/fail đo được",
      "antipattern": "Lỗi phổ biến cần tránh",
      "estimated_minutes": 10,
      "execution_mode": "solo|pair|review",
      "priority": "P0|P1|P2"
    }
  ],
  "parallel_groups": [
    ["T1.1", "T1.2"],
    ["T1.3"],
    ["T1.4", "T1.5"]
  ],
  "critical_path": ["T1.1", "T1.3", "T1.4"],
  "total_estimated_minutes": 60,
  "risk_flags": [
    "Nếu subtask T1.1 chậm, sẽ block T1.3"
  ]
}

RULES:
1. KHÔNG viết subtask kiểu "Làm task X" — phải viết ACTION cụ thể
2. Mỗi subtask hoàn thành được trong 5-20 phút
3. how[] phải có ít nhất 3 bước thực hiện cụ thể
4. dod phải là tiêu chí BINARY (pass/fail), không mơ hồ
5. Nếu task_type = "implementation": how[] phải có bước viết code + test
6. Nếu task_type = "analysis": how[] phải có bước điền vào bảng/matrix/doc cụ thể
7. antipattern phải dựa trên lỗi phổ biến thực tế của sinh viên
```

---

## NODE 2 — DEPENDENCY MAPPER PROMPT (Sequential, aggregator)

```
SYSTEM: Bạn là một Project Manager chuyên quản lý dependencies.

INPUT: Kết quả từ tất cả Node 1 (danh sách subtask của mọi task):
{ALL_SUBTASKS_JSON}

NHIỆM VỤ:
1. Xác định cross-task dependencies (subtask của Task A phụ thuộc subtask của Task B)
2. Phát hiện bottleneck (subtask nào block nhiều nhất)
3. Gợi ý luồng thực thi tối ưu (parallel vs sequential)

OUTPUT FORMAT:
{
  "execution_waves": [
    {
      "wave": 1,
      "description": "Setup & Analysis phase",
      "parallel_tasks": ["T1.1", "T2.1"],
      "sequential_after": null
    },
    {
      "wave": 2,
      "description": "Implementation phase",
      "parallel_tasks": ["T1.3", "T2.2"],
      "sequential_after": "wave_1",
      "note": "T2.2 chỉ bắt đầu sau khi T1.1 xong"
    }
  ],
  "critical_path": ["T1.1 → T2.2 → T3.4 → T4.1"],
  "bottlenecks": [
    {
      "subtask_id": "T2.3",
      "reason": "Block 3 subtask khác",
      "mitigation": "Ưu tiên hoàn thành trước, cần pair programming"
    }
  ],
  "sync_points": [
    {
      "after_wave": 2,
      "action": "Team review nhanh 5 phút: demo tools, review prompt"
    }
  ]
}
```

---

## NODE 3 — RISK & QUALITY ANNOTATOR PROMPT

```
SYSTEM: Bạn là một QA Lead và Risk Analyst.

INPUT:
- Thành viên: {MEMBER_NAME}
- Danh sách subtask của member: {MEMBER_SUBTASKS}
- Lab scoring rubric: {RUBRIC_CONTENT}

NHIỆM VỤ:
1. Map từng subtask vào tiêu chí chấm điểm (rubric)
2. Gắn cờ risk cho subtask có nguy cơ cao
3. Thêm quality gate checkpoint

OUTPUT FORMAT:
{
  "member": "...",
  "quality_gates": [
    {
      "after_subtask": "T1.2",
      "check": "Chạy python src/app.py không báo lỗi",
      "rubric_criterion": "1. Agentic Fit & Test Design (20%)"
    }
  ],
  "risk_items": [
    {
      "subtask_id": "T2.3",
      "risk_level": "HIGH",
      "risk_description": "Dễ nhúng sẵn kết quả tool vào chatbot baseline",
      "mitigation": "Verify: tool_calls = 0 trong baseline run"
    }
  ],
  "missing_coverage": ["subtask chưa cover rubric criterion nào"]
}
```

---

## NODE 4 — FORMATTER PROMPT (Final output)

```
SYSTEM: Bạn là Technical Writer chuyên viết tài liệu kỹ thuật rõ ràng cho sinh viên.

INPUT:
- Kết quả NODE 1 (subtask đã phân rã): {DECOMPOSED_TASKS}
- Kết quả NODE 2 (dependency map): {DEPENDENCY_MAP}
- Kết quả NODE 3 (risks + quality gates): {RISK_ANNOTATIONS}
- Template format hiện tại: {CURRENT_PLAN_FORMAT}

OUTPUT FORMAT (Markdown):

### 📋 Kế hoạch Chi Tiết — {GROUP_NAME}

#### 🌊 Luồng Thực Thi (Execution Waves)
[Diagram wave 1, 2, 3...]

**🔗 Critical Path:** T1.1 → T2.2 → T3.4 → T4.1

---

#### 👤 [Tên thành viên] — Kế hoạch chi tiết

**📌 [Task ID] — [Task Name]**
> ⏱️ XX phút | 🎯 Rubric: [Tiêu chí chấm điểm]

**[P0] T1.1 — Tiêu đề subtask**
- 🎯 **Mục đích**: ...
- 📋 **Các bước thực hiện**:
  - ☐ ST-T1.1.1 Bước 1...
  - ☐ ST-T1.1.2 Bước 2...
  - ☐ ST-T1.1.3 Bước 3...
- 📥 **Input cần từ**: ...
- 📤 **Output tạo ra**: `file.py` — mô tả
- ✅ **Hoàn thành khi**: [DoD đo được]
- ⚠️ **Đừng mắc bẫy**: [Antipattern cụ thể]

---

**🚦 Quality Gates:**
- [ ] Sau T1.2: [Check cụ thể]

**🔴 Risk Flags:**
- [Subtask có risk cao + mitigate]

---

#### 📊 Bảng Coverage Rubric

| Tiêu chí | Trọng số | Subtask cover | Owner |
|----------|----------|---------------|-------|
| ...      | ...      | ...           | ...   |

RULES:
1. PHẢI xuất đầy đủ, không được viết "..." hay "xem thêm bên trên"
2. Mỗi subtask PHẢI có đủ 7 trường: Mục đích, Bước thực hiện, Input, Output, DoD, Antipattern, Priority
3. Checkbox đánh số để dễ track: ☐ ST-T1.1.1, ☐ ST-T1.1.2...
4. Giữ ngôn ngữ tiếng Việt, thuật ngữ kỹ thuật giữ tiếng Anh
```

---

## 🚀 CÁCH TÍCH HỢP VÀO generate_group_plan

### Cách 1: Sequential — 1 LLM call đơn giản

Dùng khi hệ thống chưa hỗ trợ parallel. Ghép tất cả node thành 1 mega-prompt:

```python
DEEP_PLAN_PROMPT = """
<node_0_planner>
{NODE_0_PROMPT}
Thực hiện xong node 0, output JSON task_list.
</node_0_planner>

<node_1_decomposer>
Với mỗi task trong task_list, thực hiện phân rã theo format NODE 1.
Xử lý tuần tự từng task (không cần parallel vì chỉ 1 LLM call).
{NODE_1_PROMPT}
</node_1_decomposer>

<node_2_dependency_mapper>
Dựa trên subtask đã phân rã, tạo execution waves và critical path.
{NODE_2_PROMPT}
</node_2_dependency_mapper>

<node_3_risk_annotator>
Gắn risk flags và quality gates cho từng member.
{NODE_3_PROMPT}
</node_3_risk_annotator>

<node_4_formatter>
Tổng hợp tất cả thành Markdown guidebook hoàn chỉnh.
QUAN TRỌNG: Output cuối cùng phải là Markdown, không phải JSON.
{NODE_4_PROMPT}
</node_4_formatter>

Thực hiện tuần tự NODE 0 → 1 → 2 → 3 → 4.
Chỉ hiển thị output của NODE 4 cho người dùng.
"""
```

### Cách 2: LangGraph parallel (nhiều LLM call, chất lượng cao hơn)

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PlanState(TypedDict):
    plan_content: str
    members: list
    task_list: list        # sau NODE 0
    decomposed_tasks: dict # sau NODE 1 (per task)
    dependency_map: dict   # sau NODE 2
    risk_annotations: dict # sau NODE 3
    final_plan: str        # sau NODE 4

graph = StateGraph(PlanState)

# NODE 0: Chạy 1 lần, sequential
graph.add_node("planner", run_node_0)

# NODE 1: Fan-out — mỗi task 1 node, chạy parallel
# LangGraph dùng Send API để fan-out dynamic
graph.add_node("task_decomposer", run_node_1_per_task)

# NODE 2: Join tất cả subtasks lại
graph.add_node("dependency_mapper", run_node_2)

# NODE 3 + 4: Parallel
graph.add_node("risk_annotator", run_node_3)
graph.add_node("formatter", run_node_4)

# Edges
graph.set_entry_point("planner")
graph.add_conditional_edges(
    "planner",
    lambda state: [Send("task_decomposer", {"task": t}) for t in state["task_list"]]
)
graph.add_edge("task_decomposer", "dependency_mapper")
graph.add_edge("dependency_mapper", "risk_annotator")
graph.add_edge("dependency_mapper", "formatter")
graph.add_edge(["risk_annotator", "formatter"], END)
```

### Cách 3: n8n Workflow

```
Trigger: Webhook (POST /generate-plan)
  ↓
Node "Plan Analyzer" (LLM Call, NODE_0_PROMPT)
  → Output: JSON task_list
  ↓
"SplitInBatches" node: tách mỗi task thành 1 item
  ↓
"Task Decomposer" (LLM Call, NODE_1_PROMPT) → chạy parallel với concurrency=N
  ↓
"Merge" node: gom tất cả kết quả
  ↓
"Dependency Mapper" (LLM Call, NODE_2_PROMPT)
  ↓
"Risk Annotator" (LLM Call, NODE_3_PROMPT)
  ↓
"Formatter" (LLM Call, NODE_4_PROMPT)
  ↓
Output: Markdown plan → Discord webhook
```

---

## 📝 VÍ DỤ FULL OUTPUT — Lab 3 Team-CD

### 📋 Kế hoạch Chi Tiết — Nhóm team-cd

#### 🌊 Luồng Thực Thi

```
Wave 1 (Song song — 20 phút):
├── [Chiến] T1.1: Đọc tài liệu + điền Scoring Matrix
└── [Duy]   T2.1: Phân tích tool contract (danh sách 3-5 tools)

Wave 2 (Song song — 30 phút):
├── [Chiến] T1.2 → T1.3: Bảng so sánh Chatbot vs Agent + Failure Modes
└── [Duy]   T2.2 → T2.3: Implement tools.py + CHATBOT_BASELINE_PROMPT

Wave 3 (Sequential — 60 phút):
├── [Duy]   T3.1 → T3.2 → T3.3: ReAct loop + Guardrails (block đến Wave 2 xong)
└── [Chiến] T1.4 (parallel): Design edge case test questions

Wave 4 (Sequential — 40 phút):
├── [Chiến] T4.1 → T4.2: Attack set + Hybrid Flowchart
└── [Duy]   T3.4: Trace log + bảng so sánh

🔗 Critical Path: T2.1 → T2.2 → T3.1 → T3.2 → T3.3 → T4.2
```

---

#### 👤 Trần Công Chiến — Task 1 & Task 4

**📌 T1 — Định hình & Đánh giá Agentic Fit**
> ⏱️ 20 phút | 🎯 Rubric: 20% Agentic Fit & Test Design

**[P0] T1.1 — Điền Scoring Matrix từ tài liệu lab**
- 🎯 **Mục đích**: Chứng minh bài toán CẦN Agent — đây là nền tảng tư duy cho toàn bộ lab
- 📋 **Các bước thực hiện**:
  - ☐ ST-T1.1.1 Mở `docs/trace_eval.md`, tìm section "Scoring Matrix"
  - ☐ ST-T1.1.2 Đọc README.md mục "4 Cấp Độ AI" — ghi chú tiêu chí phân biệt Chatbot vs Agent
  - ☐ ST-T1.1.3 Chấm 4 tiêu chí Agentic Fit (1-5 điểm): External Data, Multi-step, Actions, Unpredictable Input
  - ☐ ST-T1.1.4 Điền bảng kèm giải thích 1 dòng cho mỗi điểm
  - ☐ ST-T1.1.5 Tổng điểm >= 12/20 → bài toán đủ điều kiện cần Agent
- 📥 **Input cần từ**: Duy xác nhận chủ đề bài toán (cần trước khi chấm điểm)
- 📤 **Output tạo ra**: Section "Scoring Matrix" trong `docs/trace_eval.md` đã điền đủ
- ✅ **Hoàn thành khi**: 4 tiêu chí có điểm + giải thích, tổng điểm ghi rõ, file `git add` xong
- ⚠️ **Đừng mắc bẫy**: Không chấm theo cảm tính — mỗi điểm PHẢI có câu giải thích cụ thể từ bài toán nhóm

**[P0] T1.2 — Viết bảng so sánh Chatbot vs ReAct Agent**
- 🎯 **Mục đích**: Tạo "north star" tư duy — hiểu TẠI SAO cần Agent trước khi code
- 📋 **Các bước thực hiện**:
  - ☐ ST-T1.2.1 Tạo bảng 3 cột trong `docs/trace_eval.md`: Câu hỏi / Chatbot xử lý được không / Agent xử lý thế nào
  - ☐ ST-T1.2.2 Điền 5 test case vào bảng (dùng test cases từ Duy)
  - ☐ ST-T1.2.3 Với mỗi case: predict Chatbot output (hallucination risk?) và expected Agent trace
  - ☐ ST-T1.2.4 Highlight >=2 câu Chatbot sẽ hallucinate — đây là bằng chứng cần Agent
- 📥 **Input cần từ**: Duy's 5 test cases (song song, sau T2.1)
- 📤 **Output tạo ra**: Bảng "Chatbot vs Agent Analysis" trong trace_eval.md
- ✅ **Hoàn thành khi**: 5 rows đầy đủ, classify output: correct/hallucinated/safe-fallback
- ⚠️ **Đừng mắc bẫy**: Không dùng câu hỏi lý thuyết thuần — phải có >=3 câu cần Tool/data thực tế

**[P1] T1.3 — Phân tích Failure Modes của tools**
- 🎯 **Mục đích**: Phòng thủ trước — biết tool fail ở đâu giúp Duy code error handling tốt hơn
- 📋 **Các bước thực hiện**:
  - ☐ ST-T1.3.1 Dựa trên tool list của Duy (T2.1), liệt kê failure mode mỗi tool
  - ☐ ST-T1.3.2 Phân loại: Input Error / Logic Error / Edge Case
  - ☐ ST-T1.3.3 Viết expected error string mà tool nên trả về thay vì crash
  - ☐ ST-T1.3.4 Document vào `docs/trace_eval.md` section "Failure Mode Analysis"
- 📥 **Input cần từ**: Duy's tool list từ T2.1
- 📤 **Output tạo ra**: Bảng Failure Modes trong trace_eval.md
- ✅ **Hoàn thành khi**: Mỗi tool có >=2 failure mode với error string cụ thể
- ⚠️ **Đừng mắc bẫy**: Phải viết cụ thể: "Khi location='xyz' → tool trả về 'LỖI: Không tìm thấy xyz'"

**[P1] T1.4 — Thiết kế Edge Case (câu bẫy)**
- 🎯 **Mục đích**: Chuẩn bị "đạn" để test Agent nhóm mình và tấn công nhóm khác ở T4
- 📋 **Các bước thực hiện**:
  - ☐ ST-T1.4.1 Thiết kế >=2 câu bẫy nhắm Guardrail (ép Agent lặp vô hạn nếu thiếu MAX_ITERATIONS)
  - ☐ ST-T1.4.2 Thiết kế >=1 câu bẫy hallucination (Chatbot sẽ bịa đặt)
  - ☐ ST-T1.4.3 Thiết kế >=1 câu Prompt Injection (cố tình thay đổi behavior Agent)
  - ☐ ST-T1.4.4 Thêm vào `config/test_cases.json` với type="edge_case"
- 📥 **Input cần từ**: Hiểu tools của Duy (sau Wave 2)
- 📤 **Output tạo ra**: >=4 edge cases trong `config/test_cases.json`
- ✅ **Hoàn thành khi**: Mỗi edge case có: question + expected_agent_behavior + attack_vector_type
- ⚠️ **Đừng mắc bẫy**: Edge case không phải câu hỏi khó — là câu được thiết kế để phá hệ thống

---

**📌 T4 — Tương tác liên nhóm & Hybrid Flowchart**
> ⏱️ 40 phút | 🎯 Rubric: 20% Inter-group + 10% Flowchart

**[P0] T4.1 — Chuẩn bị Attack Set**
- 🎯 **Mục đích**: Gây failed trace ở Agent nhóm khác — bằng chứng hiểu sâu về guardrails
- 📋 **Các bước thực hiện**:
  - ☐ ST-T4.1.1 Lấy edge cases từ T1.4, chọn 3 câu mạnh nhất
  - ☐ ST-T4.1.2 Với mỗi câu: viết "expected failure" (Agent nhóm kia fail thế nào)
  - ☐ ST-T4.1.3 Chuẩn bị biên bản cross-audit: ghi observation khi test Agent nhóm khác
  - ☐ ST-T4.1.4 Điền vào section "Cross-Audit Log" trong `docs/trace_eval.md`
- 📥 **Input cần từ**: Edge cases T1.4
- 📤 **Output tạo ra**: Cross-Audit section trong trace_eval.md
- ✅ **Hoàn thành khi**: 3 câu tấn công ghi kết quả thực tế (pass/fail + trace path cụ thể)
- ⚠️ **Đừng mắc bẫy**: Phải ghi trace path cụ thể, không chỉ ghi "fail"

**[P0] T4.2 — Vẽ Hybrid Decision Flowchart (Mermaid)**
- 🎯 **Mục đích**: Tổng hợp học tập thành sơ đồ quyết định — khi nào Chatbot, khi nào Agent
- 📋 **Các bước thực hiện**:
  - ☐ ST-T4.2.1 Xác định 4-5 tiêu chí: cần tool không, multi-step không, latency OK không
  - ☐ ST-T4.2.2 Vẽ Mermaid flowchart: Chatbot path (fast/cheap) vs ReAct path (accurate/grounded)
  - ☐ ST-T4.2.3 Thêm decision diamond: "Cần dữ liệu real-time?" → Yes → ReAct / No → Chatbot
  - ☐ ST-T4.2.4 Thêm cost annotation: Chatbot = 1 LLM call, ReAct = N calls + M tools
  - ☐ ST-T4.2.5 Save vào `docs/hybrid_flowchart.mermaid`
- 📥 **Input cần từ**: Bảng so sánh T1.2 + trace logs từ Duy T3.4
- 📤 **Output tạo ra**: `docs/hybrid_flowchart.mermaid` render được
- ✅ **Hoàn thành khi**: Render OK trên Mermaid Live Editor, >=2 decision diamonds, 2 paths rõ
- ⚠️ **Đừng mắc bẫy**: Flowchart phải có nhánh IF/ELSE — không phải sequence steps thẳng

---

#### 👤 Phạm Khắc Duy — Task 2 & Task 3

**📌 T2 — Baseline Chatbot & Khai báo Tool Specs**
> ⏱️ 30 phút | 🎯 Rubric: 30% ReAct Implementation & Tools

**[P0] T2.1 — Thiết kế Tool Contract (design-first)**
- 🎯 **Mục đích**: "Design trước, code sau" — xác định contract trước tránh rework
- 📋 **Các bước thực hiện**:
  - ☐ ST-T2.1.1 Đọc `docs/DANH_SACH_DE_TAI.md` — chốt chủ đề nhóm
  - ☐ ST-T2.1.2 Liệt kê 3-5 tools cần thiết (VD: get_weather, search_flights, convert_currency)
  - ☐ ST-T2.1.3 Điền bảng 8 câu hỏi Tool Contract cho mỗi tool: Name, Purpose, Input, Output, Error, Side-effect, Example, Safety
  - ☐ ST-T2.1.4 Share danh sách tool với Chiến (input cho T1.3)
- 📥 **Input cần từ**: Quyết định chủ đề nhóm (Wave 1, song song với T1.1)
- 📤 **Output tạo ra**: Bảng Tool Contract trong `docs/trace_eval.md` section "Tool Specs"
- ✅ **Hoàn thành khi**: >=3 tools, 8 trường đầy đủ, không trường nào để trống
- ⚠️ **Đừng mắc bẫy**: Đừng code tools.py ngay — thiết kế contract trước

**[P0] T2.2 — Implement src/tools.py với Error Handling**
- 🎯 **Mục đích**: Tools pass test độc lập trước khi gắn Agent — isolate lỗi từ nguồn
- 📋 **Các bước thực hiện**:
  - ☐ ST-T2.2.1 Mở `src/tools.py`, implement từng hàm theo contract T2.1
  - ☐ ST-T2.2.2 Docstring đầy đủ mỗi hàm: name, description, params, returns, raises
  - ☐ ST-T2.2.3 Wrap try/except: lỗi return string "LỖI: ..." KHÔNG raise Exception
  - ☐ ST-T2.2.4 Register tất cả vào `AVAILABLE_TOOLS = {"tool_name": function}`
  - ☐ ST-T2.2.5 Test thủ công từng tool với valid và invalid input
- 📥 **Input cần từ**: Tool Contract từ T2.1
- 📤 **Output tạo ra**: `src/tools.py` với AVAILABLE_TOOLS dict + docstrings
- ✅ **Hoàn thành khi**: `python -c "from src.tools import AVAILABLE_TOOLS; print(AVAILABLE_TOOLS.keys())"` in đúng tools; mỗi tool với invalid input không crash
- ⚠️ **Đừng mắc bẫy**: `return "LỖI: ..."` KHÁC với `raise Exception(...)` — tool phải return string

**[P1] T2.3 — Viết CHATBOT_BASELINE_PROMPT**
- 🎯 **Mục đích**: Baseline CÔNG BẰNG — prompt không biết về tools để so sánh trung thực
- 📋 **Các bước thực hiện**:
  - ☐ ST-T2.3.1 Mở `src/prompts.py`, tạo `CHATBOT_BASELINE_PROMPT`
  - ☐ ST-T2.3.2 System prompt trả lời tự nhiên, KHÔNG đề cập tools
  - ☐ ST-T2.3.3 Implement `run_baseline_chatbot(question)` trong `src/app.py`: 1 LLM call, tool_calls=0
  - ☐ ST-T2.3.4 Chạy 5 test cases, verify tool_calls=0 tất cả
  - ☐ ST-T2.3.5 Share raw output với Chiến cho T1.2
- 📥 **Input cần từ**: Test cases từ config/test_cases.json
- 📤 **Output tạo ra**: `CHATBOT_BASELINE_PROMPT` + `run_baseline_chatbot()` trong app.py
- ✅ **Hoàn thành khi**: 5 test cases chạy, tool_calls=0, kết quả trong trace_eval.md
- ⚠️ **Đừng mắc bẫy**: Đừng nhúng kết quả tool vào system prompt — đó là gian lận baseline

---

**📌 T3 — ReAct Loop & Safeguards**
> ⏱️ 60 phút | 🎯 Rubric: 30% Implementation + 20% Guardrails

**[P0] T3.1 — Viết REACT_SYSTEM_PROMPT + Guardrails**
- 🎯 **Mục đích**: Prompt là "luật chơi" — ép Agent suy luận đúng format, không tự bịa Observation
- 📋 **Các bước thực hiện**:
  - ☐ ST-T3.1.1 Tạo `REACT_SYSTEM_PROMPT` trong `src/prompts.py`
  - ☐ ST-T3.1.2 Viết khung bắt buộc: "PHẢI theo format: Thought: ...\nAction: tool_name[param]\nObservation: (system điền)"
  - ☐ ST-T3.1.3 Thêm rule: "Chỉ Final Answer khi đã có Observation từ Tool thực tế"
  - ☐ ST-T3.1.4 Thêm `MAX_ITERATIONS = 5` + rule xử lý khi đạt giới hạn
  - ☐ ST-T3.1.5 Inject danh sách tools: f"Tools: {list(AVAILABLE_TOOLS.keys())}"
  - ☐ ST-T3.1.6 Test với 1 câu mẫu, verify output có Thought/Action đúng format
- 📥 **Input cần từ**: AVAILABLE_TOOLS từ T2.2 (phải xong trước)
- 📤 **Output tạo ra**: `REACT_SYSTEM_PROMPT` + `MAX_ITERATIONS` trong prompts.py
- ✅ **Hoàn thành khi**: LLM sinh đúng "Thought: ...\nAction: ..." cho >=3 test queries
- ⚠️ **Đừng mắc bẫy**: LLM KHÔNG được tự viết "Observation:" — application code phải điền

**[P0] T3.2 — Implement ReAct Loop trong src/app.py**
- 🎯 **Mục đích**: Vòng lặp Thought→Action→Observation phải chạy đúng logic
- 📋 **Các bước thực hiện**:
  - ☐ ST-T3.2.1 Implement parser: extract tool_name + params từ "Action: tool_name[params]"
  - ☐ ST-T3.2.2 Implement executor: lookup AVAILABLE_TOOLS, gọi tool, bắt exception
  - ☐ ST-T3.2.3 Implement loop: while iteration < MAX_ITERATIONS: [call LLM → parse → execute → append Observation]
  - ☐ ST-T3.2.4 Handle "Final Answer": khi output chứa "Final Answer:" → break, return
  - ☐ ST-T3.2.5 Handle MAX_ITERATIONS exceeded: return safe fallback message
  - ☐ ST-T3.2.6 Test với multi-step case, verify trace đúng
- 📥 **Input cần từ**: REACT_SYSTEM_PROMPT (T3.1) + AVAILABLE_TOOLS (T2.2)
- 📤 **Output tạo ra**: Hàm `run_react_agent(question)` trong src/app.py
- ✅ **Hoàn thành khi**: Multi-step → trace Thought→Action→Observation→Final; MAX_ITERATIONS ngắt đúng
- ⚠️ **Đừng mắc bẫy**: Application append "Observation: [kết quả thật]" — LLM không tự viết Observation

**[P0] T3.3 — Test 5 cases + fix Agent V1 → V2**
- 🎯 **Mục đích**: Phát hiện lỗi có bằng chứng — V2 phải có trace before/after
- 📋 **Các bước thực hiện**:
  - ☐ ST-T3.3.1 Chạy 5 test cases, ghi lại trace
  - ☐ ST-T3.3.2 Trigger edge case từ T1.4 — record failed trace
  - ☐ ST-T3.3.3 RCA: Lỗi ở Parser? Executor? Prompt? Loop?
  - ☐ ST-T3.3.4 Fix → Agent V2
  - ☐ ST-T3.3.5 Chạy lại edge case với V2, verify đã fix
- 📥 **Input cần từ**: Edge cases từ Chiến (T1.4)
- 📤 **Output tạo ra**: V2 code + Failed trace + Fixed trace trong trace_eval.md
- ✅ **Hoàn thành khi**: >=1 failed trace ghi kèm RCA; V2 pass edge case với safe fallback
- ⚠️ **Đừng mắc bẫy**: Đừng xóa failed trace — bằng chứng lỗi + sửa = đủ điểm observability

**[P1] T3.4 — Ghi Trace Log + Bảng so sánh**
- 🎯 **Mục đích**: Báo cáo phải có số liệu định lượng, không chỉ mô tả
- 📋 **Các bước thực hiện**:
  - ☐ ST-T3.4.1 Chép 5 trace logs vào `docs/trace_eval.md` (cả Chatbot và Agent)
  - ☐ ST-T3.4.2 Điền bảng rubric 0-2 điểm: 5 cases × 4 tiêu chí (Factual, Grounding, Tool selection, Termination)
  - ☐ ST-T3.4.3 Tính tổng điểm, viết nhận xét 3-5 câu
  - ☐ ST-T3.4.4 Share với Chiến để vẽ Flowchart (T4.2)
- 📥 **Input cần từ**: Trace logs T3.3 + Chatbot output T2.3
- 📤 **Output tạo ra**: `docs/trace_eval.md` đủ: Scoring Matrix + Tool Specs + Failure Modes + 5 Traces + Comparison Table
- ✅ **Hoàn thành khi**: trace_eval.md có đủ 5 sections trên, bảng rubric điền xong
- ⚠️ **Đừng mắc bẫy**: Trace thô chưa đủ — phải annotate: đâu là Thought, Observation, lỗi

---

#### 🚦 Quality Gates

| Sau bước | Người check | Điều kiện pass |
|----------|-------------|----------------|
| Wave 1 xong | Cả nhóm 5 phút | Duy có tool list, Chiến có Scoring Matrix |
| T2.2 xong | Duy self-check | `AVAILABLE_TOOLS.keys()` in đúng tool names |
| T2.3 xong | Chiến verify | Baseline với 1 câu → tool_calls = 0 |
| T3.1 xong | Duy test | LLM output có "Thought:" + "Action:" đúng format |
| T3.2 xong | Cả nhóm | Multi-step trace: Thought→Action→Observation→Final |
| T3.3 xong | Chiến attack | Câu bẫy → Agent V2 fallback lịch sự, không crash |
| Final submit | Cả nhóm | `.env` không trong git status, app.py không lỗi |

---

#### 🔴 Risk Flags

| Risk | Subtask | Level | Mitigate |
|------|---------|-------|----------|
| Duy code tools, Chiến không biết tool list → T1.3 block | T2.1 ↔ T1.3 | HIGH | Duy share tool contract ngay sau T2.1 |
| Baseline có tool_calls > 0 → so sánh không công bằng | T2.3 | HIGH | Verify tool_calls = 0 ngay sau run |
| ReAct loop để LLM tự viết Observation | T3.2 | CRITICAL | Code review: nếu "Observation:" có trong LLM output → sai |
| Chiến không có trace logs khi vẽ Flowchart | T4.2 ↔ T3.4 | MEDIUM | Duy commit trace_eval.md, Chiến git pull trước T4.2 |

---

#### 📊 Coverage Rubric

| Tiêu chí | Trọng số | Subtask cover | Owner |
|----------|----------|---------------|-------|
| Agentic Fit & Test Design | 20% | T1.1, T1.2, T1.3, T1.4 | Chiến |
| ReAct Implementation & Tools | 30% | T2.1, T2.2, T3.1, T3.2 | Duy |
| Guardrails & Observability | 20% | T3.1 (MAX_ITERATIONS), T3.3, T3.4 | Duy |
| Inter-group Attack & Defense | 20% | T1.4, T4.1 | Chiến |
| Hybrid Decision Flowchart | 10% | T4.2 | Chiến |
| 🎁 BONUS Autonomous Agent | +10% | Cải tiến T3.2 thêm Planning layer | Duy (optional) |
