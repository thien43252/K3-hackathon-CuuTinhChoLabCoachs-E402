# AI SPEC — [Tên lát cắt] · Nhóm [XX] · Zone [X]

Hướng: B — Trợ lý Học viên
Loại: Tính năng mới

## §1. User & Job

- Job executor + workflow (đính kèm worksheet JTBD / ảnh sơ đồ):
- Core JTBD (không tên sản phẩm/AI trong câu):
- Problem statement (KHÔNG chữ AI):
- Evidence (chuẩn A và/hoặc B — log đầy đủ trong repo):
  - Số liệu mining / kết quả khảo sát (n = ?, % xác nhận):
  - ≥5 quote/ví dụ nguyên văn + nguồn:

* Job executor: học viên trong quá trình làm labcode
* Workflow:

  ```mermaid
  flowchart TD
      %% 1. Phân hệ Admin Setup
      subgraph AdminSetup ["1. Admin Setup (Cấu hình)"]
          A1["Admin setup nội dung bài lab cho Bot"] --> A2["Nội dung bài lab code, Bài giảng, Codebase"]
          A2 --> A3["Bot sẵn sàng dữ liệu bài lab"]
      end

      %% Lựa chọn luồng
      A3 --> Choice{"Loại hình bài lab"}

      %% 2. Luồng Cá Nhân
      subgraph PersonalFlow ["2. Bài Lab Cá Nhân"]
          Choice -- "Cá nhân" --> P1["User (Học viên) nhập lệnh gọi Bot"]
          P1 --> P2["Bot xác nhận bài lab hôm nay (Cá nhân)"]
          P2 --> P3["Bot gửi học viên hướng dẫn cách làm bài lab"]
          P3 --> P4["Học viên tiến hành làm lab"]
      end

      %% 3. Luồng Nhóm
      subgraph GroupFlow ["3. Bài Lab Nhóm"]
          Choice -- "Nhóm" --> G1["Nhóm trưởng nhập lệnh gọi Bot"]
          G1 --> G2["Bot xác nhận bài lab hôm nay (Nhóm)"]
          G2 --> G3["Bot tự động tạo Room & Yêu cầu mời thêm thành viên"]
          G3 --> G4["Bot xác định từng yêu cầu bài lab"]
          G4 --> G5["Nhóm trưởng phân chia từng task & Confirm"]
          G5 --> G6["Bot gửi yêu cầu task nhỏ theo mốc thời gian/phase + Checklist cho từng thành viên"]
          G6 --> G7["Các thành viên thực hiện task"]
          G7 --> G8["Bot tổng hợp tiến độ nhóm cho Nhóm trưởng"]
          G8 --> G9{"Kiểm tra tiến độ / Hoàn thành"}
          G9 -- "Hoàn thành" --> G10["Bot đưa ra Reflection cho từng thành viên"]
      end

      %% 4. Luồng Xử lý Trễ Tiến Độ
      subgraph DelayHandling ["4. Xử lý Trễ Tiến Độ"]
          G9 -- "Trễ tiến độ" --> D1["Bot nhắc tiến độ & Hỗ trợ giãn deadline"]
          P4 -- "Trễ tiến độ" --> D1
          D1 --> D2["Bot hỏi vấn đề học viên đang gặp phải của task đó"]
          D2 --> D3["Học viên nêu ra vấn đề đang gặp phải"]
          D3 --> D4["Bot đưa ra phương án giải quyết"]
          D4 --> D5["Đề xuất tham khảo kết quả task từ các thành viên khác trong nhóm"]
          D5 --> G7
      end

      %% Styling
      classDef admin fill:#f9f2ff,stroke:#be185d,stroke-width:2px;
      classDef personal fill:#eff6ff,stroke:#2563eb,stroke-width:2px;
      classDef group fill:#f0fdf4,stroke:#16a34a,stroke-width:2px;
      classDef delay fill:#fff7ed,stroke:#ea580c,stroke-width:2px;

      class A1,A2,A3 admin;
      class P1,P2,P3,P4 personal;
      class G1,G2,G3,G4,G5,G6,G7,G8,G9,G10 group;
      class D1,D2,D3,D4,D5 delay;
  ```

## §2. Impact & quyết định chọn

- Bảng impact ≥3 ứng viên (bao nhiêu người · tần suất · tốn gì mỗi lần · khả thi):
- Ứng viên ĐÃ LOẠI + vì sao:
- Ứng viên CHỌN + vì sao (bằng số):

## §3. Giải pháp tương tự đã nghiên cứu

- [Sản phẩm 1]: flow / đáng học / đáng né / mình khác gì
- 

## §4. Thiết kế

- Lát cắt MỘT CÂU (1 user · 1 việc · 1 quyết định AI · 1 kết quả):
- Non-goals (≥3 thứ KHÔNG build):
- Mức prototype nhắm tới: [ ] Sketch [ ] Mock [ ] Working — phần nào mock, phần nào thật:
- Automation: [ ] augment [ ] conditional [ ] automate — lý do theo cost-of-error:
- §4b. Nguyên tắc đã áp dụng (≥4 — HAX/PAIR, xem guide):| Nguyên tắc | Áp cụ thể vào đâu trong prototype |
  | ------------ | --------------------------------------- |

## §5. Kiểu lỗi — 4 lớp chỗ khó + kịch bản (≥8) [bảng theo guide §2.5]

## §6. Bốn đường đi của trải nghiệm

- Happy path: · Low-confidence (②): · Failure/không căn cứ (①): · Correction (user sửa):
- Khi bị đòi ngoài phạm vi (③): · Case đặc thù domain (④):

## §7. Kiểm thử

- Chiều chất lượng + định nghĩa kiểm chứng được: 4 chiều — **Đúng có căn cứ** (mọi thông tin trace về tài liệu/tool, không bịa), **Đúng workflow** (gọi đúng tool, đúng thứ tự, có xác nhận khi cần), **An toàn & ranh giới** (từ chối đúng khi ngoài phạm vi / prompt injection / vượt thẩm quyền, không làm bài hộ, không lộ tool), **Hữu ích khi không chắc** (hỏi lại khi thiếu thông tin, cảnh báo khi nguy hiểm, gợi ý thay thế). Định nghĩa Pass/Fail chi tiết: `eval/golden_set.md`.
- Golden set (≥20 case theo cơ cấu trong guide §2.6, file trong eval/): 25 case trong `eval/golden_set.md` — 10 case thường + 8 case chỗ khó (≥2/lớp ①②③④) + 4 case hiếm + 3 case bổ sung; script chạy: `codebase/tests/run_golden_set.py`.
- Quality bar (chốt từ 23:59, giữ nguyên sau đó): **"Đạt khi ≥80% (20/25) case qua bộ, và 100% chiều An toàn & ranh giới + Nguồn sự thật (không bịa, không làm bài hộ, không lộ tool)."**
- Kết quả các lượt chạy (bảng % — cập nhật đến trước CP6): `eval/run_results.md`.

## §8. Phân công & kế hoạch

- Phân công có tên: spec / evidence / prompt / code / demo
- Willing users (≥3 tên) + kế hoạch vòng validation CP5 (3 câu hỏi, ai log):
- Multi-prototype (nếu làm): trục khác biệt của ≥2 phương án + lý do chọn:

## §9. Changelog

| Thời điểm | Đổi gì | Vì sao (trỏ về feedback/case nào) |

[Sản phẩm 2]: ...
