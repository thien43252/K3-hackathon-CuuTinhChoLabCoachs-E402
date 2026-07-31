# AI SPEC — Trợ Lý Quản Lý Tiến Độ & Hỗ Trợ Giải Đáp Bài Labcode

> **Dự án Hackathon · Nhóm 01 · Zone B**
> **Hướng B: Trợ lý Học viên (Discord Bot)**

---

## 👥 1. Danh Sách Thành Viên & Phân Công Công Việc

### Bảng phân công chi tiết theo tên và mã học viên:

| STT | Họ và Tên                   | Mã Học Viên |     Vai Trò     | Nhiệm Vụ Phân Công Chi Tiết                                                                                                                                                  |
| :-: | :----------------------------- | :-------------: | :--------------: | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|  1  | **Phạm Khắc Duy**      | `2A202601757` | **Leader** | • Lên plan tổng thể và kiến trúc dự án• Phân chia công việc cho các thành viên• Viết mã nguồn Agent Core logic (`codebase/app/agent`)                       |
|  2  | **Phạm Đức Thiện**   | `2A202601981` |   Thành viên   | • Phân tích bài toán, xây dựng tài liệu`spec.md`• Thiết kế System Prompt, Templates & HAX/PAIR principles• Tổng hợp và hoàn thiện tài liệu dự án          |
|  3  | **Nguyễn Ngọc Thuận** | `2A202601949` |   Thành viên   | • Xây dựng các Tools cho Agent (`codebase/app/tools`)• Phát triển các Services xử lý dữ liệu (`insight_extractor`, `task_tools`)                                |
|  4  | **Trần Công Chiến**   | `2A202601053` |   Thành viên   | • Viết mã nguồn Discord Bot integration (`codebase/app/channels`)• Tích hợp ghép nối sản phẩm end-to-end• Kiểm thử, hoàn thiện và cải tiến trải nghiệm bot |

---

### Phân công theo từng phần / module trong Repo:

* **Tài liệu & Kịch bản AI SPEC (`spec.md`, `README.md`)**: Phạm Đức Thiện, Phạm Khắc Duy
* **Hạt nhân AI Agent (`codebase/app/agent/`, `codebase/app/prompt/`)**: Phạm Khắc Duy
* **Hệ thống Tools & Services (`codebase/app/tools/`, `codebase/app/services/`)**: Nguyễn Ngọc Thuận
* **Giao diện & Tích hợp Discord (`codebase/app/channels/`, `codebase/app/discord_context.py`)**: Trần Công Chiến
* **Bộ Kiểm thử & Đánh giá (`eval/`, `codebase/tests/`)**: Trần Công Chiến, Phạm Đức Thiện
