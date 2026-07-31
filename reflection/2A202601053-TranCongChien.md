# Reflection — Trần Công Chiến · 2A202601053

> Outline theo rubric: **Vai trò · Phần mình làm · AI hỗ trợ thế nào · Một bài học từ case fail của chính nhóm**.
> Mỗi mục có câu gợi ý — thay bằng trải nghiệm thật của mình, trỏ được vào file/đoạn trong repo.

## Vai trò

<!-- 1-2 câu: mình giữ vai trò gì trong nhóm (VD: Prompt & Agent engineering, spec & evidence, code, validation, demo) -->

## Phần mình làm

* Xây dựng phần kết nỗi discord
* Xây dựng và thiết kế architecture và workflow cho phần AI bao gồm: import data, genrate plan
* Xây dựng phần eval
* Ghép code

<!-- Liệt kê việc CỤ THỂ mình làm, kèm đường dẫn file/đoạn code để CP5 hỏi là chỉ được:
- [việc 1] → file `...`
- [việc 2] → file `...`
- Lỗi mình gặp khi làm + cách xử lý (guide §4.1 khuyên ghi lại từ lúc build):
  - lỗi: ...
  - cách xử lý: ... -->

## AI hỗ trợ thế nào

* Thực hiện tư vấn về architecutre
* Fix bug
* Đóng góp xây test matrix để xây case test
* Coding

<!-- AI giúp gì, dùng ở bước nào, và tại sao mình vẫn hiểu/kiểm soát được phần đó (chống vibe-coding bị hỏng):
- [AI giúp: ...]
- [Vì sao mình hiểu được phần đó: ...] -->

## Một bài học từ case fail của chính nhóm

* Cần list ra phần spec kĩ hơn như logic, tham số, output và usecase
* Cần học cách bảo trì dự án khi có nhiều thành viết cùn code

<!-- Chọn 1 case fail THẬT, có bằng chứng trong `eval/run_results.md` (lượt 1: 48%).
Gợi ý các case có sẵn:
- Case 02/12 — bot bịa guide FastAPI + trích dẫn CODELAB.md → bài học về rule chống hallucination phải kèm điều kiện kiểm chứng, và phải ĐO bằng golden set thay vì tin cảm tính.
- Case 20 — bot lộ hết 8 tool nội bộ → bài học: đừng tin LLM tự giữ ranh giới, cần guardrail cấm liệt kê.
- Case 21 — non-leader vẫn được phân công → bài học: thiếu role trong context thì phân quyền không thể chặn.

Viết: [case fail cụ thể] → [vì sao xảy ra] → [bài học mình rút ra] -->
