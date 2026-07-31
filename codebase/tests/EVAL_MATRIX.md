# Ma Trận Đánh Giá Chất Lượng (Eval Matrix)

> Cập nhật: 2026-07-31  
> Mục đích: Kiểm tra **chất lượng dữ liệu output** — không phải "có chạy hay không" mà là "chạy có đúng không".

## Cách đọc

| Column | Ý nghĩa |
|---|---|
| **Case** | Mã: `E{nhóm}_{H|U}_{N}` (Eval · Nhóm · Happy/Unhappy · STT) |
| **Input** | Dữ liệu đầu vào (mock documents, issue mô tả) |
| **Quality Criteria** | Tiêu chí đánh giá output — PASS nếu ĐÚNG hết |
| **Expected signal** | Dấu hiệu cho thấy chất lượng TỐT (extract đúng, không bịa) |
| **Anti-signal** | Dấu hiệu cho thấy chất lượng KÉM (generic, bịa, thiếu) |

---

## Nhóm E1: `LabInsightExtractor` — Regex Fallback Path

> Kiểm tra extraction khi KHÔNG có AI key (dùng regex/keyword fallback).

### E1.1: Phân loại sections đúng heading

| Case | Input | Quality Criteria | Expected signal | Anti-signal |
|---|---|---|---|---|
| **E1.1_H1** | Document có heading "Mục tiêu", "Cài đặt", "Task 1", "Rubric", "Lưu ý" | Mỗi section được gán vào đúng field | `lab_objective` chứa nội dung từ "Mục tiêu"; `setup_instructions` từ "Cài đặt" | Objective bị rỗng hoặc lấy nhầm từ heading khác |
| **E1.1_H2** | Document có heading "Objective", "Setup", "Checkpoint 1", "Scoring" (tiếng Anh) | Keyword matching hoạt động với cả EN + VI | `lab_objective` ≠ "" ; `tasks` ≥ 1 item | Tasks rỗng vì không match keyword VI |
| **E1.1_U1** | Document không có heading nào match keyword | Fallback: dùng H2 sections làm tasks | `tasks` ≥ 1 (từ tất cả H2) | Crash / trả về rỗng |
| **E1.1_U2** | Document không có sections (rỗng) | Graceful fallback | `lab_objective` ≠ "" (fallback text), `tasks` có 1 task mặc định | Crash |

### E1.2: Chất lượng tasks & checklist

| Case | Input | Quality Criteria | Expected signal | Anti-signal |
|---|---|---|---|---|
| **E1.2_H1** | Section có bullet list `- Bước 1: ...\n- Bước 2: ...` | Checklist được extract từ bullet items | `tasks[0].checklist` có ≥ 2 items, không trùng | Checklist rỗng |
| **E1.2_H2** | Section có numbered list `1. ...\n2. ...` | Checklist extract từ numbered items | `tasks[0].checklist` có ≥ 2 items | Checklist rỗng |
| **E1.2_U1** | Section content là paragraph (không bullet) | Fallback: dùng sentences làm checklist | `tasks[0].checklist` có ≥ 1 item | Checklist rỗng hoặc chỉ là heading lặp lại |

### E1.3: Chất lượng common pitfalls

| Case | Input | Quality Criteria | Expected signal | Anti-signal |
|---|---|---|---|---|
| **E1.3_H1** | Document có section "Lưu ý" hoặc "Bẫy lỗi thường gặp" | Pitfalls được extract từ đúng section | `common_pitfalls` ≥ 1, chứa nội dung từ section đó | Pitfalls là generic text mặc định |
| **E1.3_U1** | Document không có section nào match pitfalls | Fallback về generic warnings | `common_pitfalls` có 3 item generic (kiểm tra .env, không commit key, đọc rubric) | Crash |
| **E1.3_U2** | Section pitfalls nhưng content rỗng | Graceful fallback | `common_pitfalls` có generic items | Rỗng |

### E1.4: Chất lượng timeline

| Case | Input | Quality Criteria | Expected signal | Anti-signal |
|---|---|---|---|---|
| **E1.4_H1** | Section có heading "Thời gian" hoặc "Timeline" | Timeline content được extract | `timeline` ≠ "" | Timeline rỗng |
| **E1.4_U1** | Document không có timeline section | Timeline rỗng (không bịa) | `timeline` = "" | Timeline có nội dung bịa |

### E1.5: Chất lượng file_summaries

| Case | Input | Quality Criteria | Expected signal | Anti-signal |
|---|---|---|---|---|
| **E1.5_H1** | 2 documents, mỗi doc có sections | File summaries được tạo từ heading đầu tiên + content preview | `file_summaries` có 2 items, mỗi item có `file` + `summary` | File_summaries rỗng |
| **E1.5_U1** | Document không có sections | File summary dùng file_name làm heading | `file_summaries` có item với `file` đúng tên | Crash |

---

## Nhóm E2: `LabInsightExtractor` — AI Extraction Path

> Kiểm tra AI extraction quality khi CÓ API key (Gemini/OpenAI).

### E2.1: Schema compliance

| Case | Input | Quality Criteria | Expected signal | Anti-signal |
|---|---|---|---|---|
| **E2.1_H1** | 3-5 file .md với nội dung lab đầy đủ | AI trả về JSON đúng schema | Tất cả required fields: lab_objective, setup_instructions, tasks, grading_rubrics, common_pitfalls | Thiếu field, sai kiểu |
| **E2.1_H2** | Lab có timeline rõ ràng | Field timeline không rỗng | `timeline` ≠ "" | Timeline rỗng / bịa |
| **E2.1_H3** | Lab có file_summaries cụ thể | File summaries có nội dung mô tả đúng từng file | `file_summaries[i].summary` chứa nội dung liên quan đến file đó | Summary generic kiểu "File hướng dẫn" |

### E2.2: Task quality

| Case | Input | Quality Criteria | Expected signal | Anti-signal |
|---|---|---|---|---|
| **E2.2_H1** | Lab có 5 task rõ ràng | AI trích xuất đúng số lượng task | `tasks` có 5 items | Tasks khác 5 hoặc task name generic "Task 1", "Task 2" |
| **E2.2_H2** | Task có checklist cụ thể | Checklist không rỗng, tối thiểu 2 items/task | Mỗi task có `checklist` ≥ 2 | Checklist rỗng |
| **E2.2_H3** | Task có deliverable được nêu | Deliverable được extract | `tasks[i].deliverable` ≠ "" | Deliverable rỗng |

### E2.3: Anti-hallucination

| Case | Input | Quality Criteria | Expected signal | Anti-signal |
|---|---|---|---|---|
| **E2.3_H1** | Lab không có AI section nào | AI không được thêm nội dung AI vào output | Không có mention "AI" không có thật | AI bịa thêm task/checklist |
| **E2.3_H2** | Lab không có thông tin timeline | AI thành thật bỏ trống | `timeline` có thể rỗng hoặc nói "không có" | Timeline bịa số liệu |

---

## Nhóm E3: `analyze_student_issue` — Quality

> Kiểm tra chất lượng phân tích lỗi (không phải "có chạy hay không").

### E3.1: Root cause accuracy

| Case | Input | Quality Criteria | Expected signal | Anti-signal |
|---|---|---|---|---|
| **E3.1_H1** | `issue="Lỗi kết nối database"`, `error_log="MongoError"` | Root cause phải liên quan đến database/Mongo | `root_cause` chứa "DATABASE_URL" hoặc "Mongo" hoặc "connection" | Root cause chung chung "Lỗi async/await" |
| **E3.1_H2** | `issue="Lỗi import module pandas"` | Root cause phải là thiếu thư viện | `root_cause` chứa "chưa cài" hoặc "thư viện" hoặc "pip install" | Root cause nói về env/database |
| **E3.1_H3** | `issue="File không tìm thấy"` | Root cause fallback (không match keyword nào) | `root_cause` không rỗng, không nói "env" nếu không liên quan | Root cause sai (vd: DATABASE_URL cho file error) |

### E3.2: Solution usefulness

| Case | Input | Quality Criteria | Expected signal | Anti-signal |
|---|---|---|---|---|
| **E3.2_H1** | Bất kỳ issue nào | suggested_solution phải actionable | `suggested_solution` chứa lệnh cụ thể (pip install, tạo .env, kiểm tra schema...) | "Vui lòng thử lại" hoặc "Liên hệ admin" |
| **E3.2_U1** | issue không rõ ràng < 10 ký tự | Báo không đủ thông tin, KHÔNG đoán | `status` = "empty", `error_code` = "UNCLEAR_ISSUE" | Cố gắng phân tích và cho root cause sai |

### E3.3: Reference quality

| Case | Input | Quality Criteria | Expected signal | Anti-signal |
|---|---|---|---|---|
| **E3.3_U1** | Bất kỳ | Reference links KHÔNG được là example.com | `reference_links` không chứa "example.com" | Link dẫn đến example.com |
| **E3.3_U2** | Bất kỳ | Reference links tồn tại | `reference_links` ≠ [] | Reference links rỗng |

---

## Nhóm E4: End-to-End Flow Quality

> Kiểm tra chất lượng tổng thể từ lab extraction → plan generation.

### E4.1: Task → Phase mapping

| Case | Input | Quality Criteria | Expected signal | Anti-signal |
|---|---|---|---|---|
| **E4.1_H1** | Lab có insight tasks (10 tasks) | generate_group_plan dùng dynamic phases từ tasks | `phases` có 10 items (mỗi task = 1 phase) | Phases chỉ có 4 canonical |
| **E4.1_U1** | Lab không có insight tasks | Fallback canonical 4 phases | `phases` có 4 items | Crash |

### E4.2: Guidebook depth

| Case | Input | Quality Criteria | Expected signal | Anti-signal |
|---|---|---|---|---|
| **E4.2_H1** | 4 members (PM, Backend, AI, QA) + lab có data | Guidebook phải dài, chi tiết, có file references | `summary` ≥ 2000 ký tự, có lab-specific file refs | Summary < 500 ký tự, chung chung |
| **E4.2_H2** | Member có role Frontend | Guidebook có hướng dẫn UI/UX | Checklist chứa item về UI, wireframe, component | Checklist chỉ có "làm task" chung |

---

## Tổng hợp

| Nhóm | Chủ đề | Số case |
|---|---|---|
| E1 | Regex fallback quality | 14 |
| E2 | AI extraction quality | 7 |
| E3 | analyze_student_issue quality | 8 |
| E4 | End-to-end quality | 4 |
| **Tổng** | | **33** |
