# Tài Liệu Định Nghĩa Công Cụ (Agent Tools Specification)

Tài liệu này mô tả chi tiết tất cả 15 công cụ (**Tools / APIs**) cần thiết để **AI Agent** thực thi quy trình hướng dẫn, quản lý và hỗ trợ học viên làm bài lab (Cá nhân & Nhóm). Toàn bộ 15 công cụ đã được tích hợp với **Cơ sở dữ liệu SQLite thực tế** tại `codebase/data/app.db`.

> ⚠️ **QUY TẮC CỐT LÕI: CHỐNG BỊA ĐẶT (ANTI-HALLUCINATION POLICY)**
> - **Trung thực khi không có dữ liệu**: Khi câu hỏi hoặc kết quả `RAG_search` trả về rỗng (`status: "empty"`), Bot **PHẢI NÓI RÕ KHÔNG TÌM THẤY THÔNG TIN / KHÔNG BIẾT**.
> - **Tuyệt đối không bịa đặt**: Không tự bịa mã nguồn, không bịa tên hàm, không bịa quy trình hoặc ví dụ code không tồn tại trong CSDL bài lab.

---

## 📋 Danh Sách Tổng Quan Các Tools

| STT | Tên Tool | Nhóm Chức Năng | Mục Đích Sử Dụng |
| :---: | :--- | :--- | :--- |
| 1 | `upload_lab_material` | Admin & Knowledge | Admin tải lên nội dung bài lab, bài giảng, codebase mẫu |
| 2 | `codebase_indexer` | Admin & Knowledge | Đánh chỉ mục (index) dữ liệu codebase & bài giảng vào Vector DB / RAG |
| 3 | `RAG_search` | Admin & Knowledge | Truy vấn tri thức bài giảng, codebase để trả lời câu hỏi |
| 4 | `get_user_context` | Platform & Context | Lấy thông tin học viên, bài lab được phân công trong ngày & vai trò |
| 5 | `create_group_room` | Platform & Context | Tự động tạo Discord Text Channel/Private Thread và phân quyền thành viên |
| 6 | `send_message` | Platform & Context | Gửi tin nhắn trực tiếp (DM) hoặc gửi vào channel Discord nhóm |
| 7 | `send_notification` | Platform & Context | Tag tên hoặc gửi thông báo quan trọng đến học viên |
| 8 | `parse_lab_requirements` | Task Management | Phân tích bài lab nhóm thành các task nhỏ, timeline & checklist |
| 9 | `assign_task` | Task Management | Phân công task, trả về Markdown Checklist cho Discord |
| 10 | `track_group_progress` | Task Management | Tổng hợp tiến độ công việc nhóm cho Nhóm trưởng |
| 11 | `generate_reflection` | Task Management | Sinh đánh giá/reflection cá nhân sau khi hoàn thành bài lab |
| 12 | `schedule_reminder` | Scheduler & Remind | Đặt lịch tự động nhắc nhở tiến độ hoặc deadline |
| 13 | `extend_deadline` | Scheduler & Remind | Gia hạn / giãn deadline cho task của học viên |
| 14 | `analyze_student_issue` | Troubleshooting | Phân tích lỗi code / vấn đề học viên gặp phải và đưa ra hướng giải quyết |
| 15 | `fetch_peer_solution` | Troubleshooting | Trả về Code Block tham khảo từ thành viên khác trực tiếp trên Discord |

---

## 🛠 Chi Tiết Định Nghĩa Các Tools

### 1. `upload_lab_material`
Mô tả: Cho phép Admin thiết lập nội dung bài lab code, bài giảng và mã nguồn codebase mẫu lên hệ thống.

#### Tham số đầu vào (Input Parameters):
| Tham Số | Kiểu Dữ Liệu | Bắt Buộc | Mô Tả |
| :--- | :---: | :---: | :--- |
| `lab_id` | `string` | Có | Mã định danh duy nhất của bài lab (ví dụ: `LAB05_INDIVIDUAL`) |
| `title` | `string` | Có | Tiêu đề bài lab |
| `type` | `string` | Có | Loại bài lab (`"individual"` hoặc `"group"`) |
| `description` | `string` | Có | Nội dung mô tả yêu cầu bài lab |
| `lecture_files` | `array[string]` | Không | Danh sách Discord Attachment URLs hoặc đường dẫn tệp bài giảng (PDF, Markdown...) |
| `codebase_repo_url` | `string` | Không | Đường dẫn kho chứa codebase mẫu (Git repo URL hoặc zip) |

#### Kết quả đầu ra (Output Schema):
* **Thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "lab_id": "LAB05_GROUP",
    "message": "Đã lưu trữ nội dung bài lab thành công.",
    "created_at": "2026-07-30T12:00:00Z"
  }
  ```
* **Không tìm thấy / Thiếu dữ liệu (`400 Bad Request`)**:
  ```json
  {
    "status": "empty",
    "error_code": "INVALID_INPUT",
    "message": "Nội dung bài lab hoặc lab_id không được để trống."
  }
  ```
* **Lỗi hệ thống (`500 Internal Error`)**:
  ```json
  {
    "status": "error",
    "error_code": "STORAGE_FAILED",
    "message": "Không thể kết nối đến hệ thống lưu trữ dữ liệu Admin."
  }
  ```

---

### 2. `codebase_indexer`
Mô tả: Tự động trích xuất, phân tích và đánh chỉ mục (index) tệp bài giảng và codebase vào hệ thống RAG / Vector Database.

#### Tham số đầu vào (Input Parameters):
| Tham Số | Kiểu Dữ Liệu | Bắt Buộc | Mô Tả |
| :--- | :---: | :---: | :--- |
| `lab_id` | `string` | Có | Mã bài lab cần index dữ liệu |
| `force_reindex` | `boolean` | Không | Bắt buộc index lại từ đầu (mặc định: `false`) |

#### Kết quả đầu ra (Output Schema):
* **Thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "lab_id": "LAB05_GROUP",
    "indexed_chunks": 142,
    "vector_collection": "lab05_knowledge_base"
  }
  ```
* **Không lấy được dữ liệu (`404 Not Found`)**:
  ```json
  {
    "status": "empty",
    "error_code": "NO_MATERIAL_FOUND",
    "message": "Không tìm thấy tệp codebase hoặc bài giảng để index cho bài lab này."
  }
  ```
* **Lỗi hệ thống (`500 Internal Error`)**:
  ```json
  {
    "status": "error",
    "error_code": "VECTOR_DB_ERROR",
    "message": "Lỗi kết nối Vector Database khi ghi dữ liệu nhúng (embeddings)."
  }
  ```

---

### 3. `RAG_search`
Mô tả: Truy vấn cơ sở tri thức để lấy các đoạn mã nguồn mẫu, hướng dẫn làm bài hoặc đáp án bài giảng liên quan đến câu hỏi.

#### Tham số đầu vào (Input Parameters):
| Tham Số | Kiểu Dữ Liệu | Bắt Buộc | Mô Tả |
| :--- | :---: | :---: | :--- |
| `query` | `string` | Có | Câu hỏi hoặc vấn đề cần tra cứu |
| `lab_id` | `string` | Có | Mã bài lab cần giới hạn phạm vi truy vấn |
| `top_k` | `integer` | Không | Số lượng kết quả phù hợp nhất cần trả về (mặc định: `5`) |

#### Kết quả đầu ra (Output Schema):
* **Thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "query": "Cách khởi tạo kết nối database trong codebase",
    "data": [
      {
        "content": "Sử dụng hàm connectDB() trong src/db.js...",
        "source": "src/db.js",
        "score": 0.94
      }
    ]
  }
  ```
* **Không tìm thấy dữ liệu (`200 OK` - Rỗng)**:
  ```json
  {
    "status": "empty",
    "data": [],
    "message": "Không tìm thấy nội dung phù hợp với truy vấn trong tài liệu bài lab."
  }
  ```
* **Lỗi hệ thống (`500 Internal Error`)**:
  ```json
  {
    "status": "error",
    "error_code": "SEARCH_SERVICE_DOWN",
    "message": "Dịch vụ truy vấn RAG tạm thời không khả dụng."
  }
  ```

---

### 4. `get_user_context`
Mô tả: Lấy thông tin chi tiết về người dùng đang gọi bot (Học viên/Nhóm trưởng), lịch làm lab trong ngày và danh sách thành viên nhóm (nếu có).

#### Tham số đầu vào (Input Parameters):
| Tham Số | Kiểu Dữ Liệu | Bắt Buộc | Mô Tả |
| :--- | :---: | :---: | :--- |
| `user_id` | `string` | Có | Discord User ID của người dùng |
| `date` | `string` | Không | Ngày làm lab (định dạng `YYYY-MM-DD`, mặc định: ngày hiện tại) |

#### Kết quả đầu ra (Output Schema):
* **Thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "user": {
      "user_id": "U123456",
      "full_name": "Pham Duc Thien",
      "role": "group_leader"
    },
    "today_lab": {
      "lab_id": "LAB05_GROUP",
      "type": "group",
      "title": "Xây dựng AI Agent Workflow"
    },
    "group_info": {
      "group_id": "G01",
      "members": ["U123456", "U789012", "U345678"]
    }
  }
  ```
* **Không tìm thấy dữ liệu (`404 Not Found`)**:
  ```json
  {
    "status": "empty",
    "error_code": "NO_LAB_TODAY",
    "message": "Không tìm thấy lịch bài lab nào cho học viên trong ngày hôm nay."
  }
  ```
* **Lỗi hệ thống (`500 Internal Error`)**:
  ```json
  {
    "status": "error",
    "error_code": "USER_SERVICE_UNAVAILABLE",
    "message": "Không thể kết nối đến hệ thống quản lý học viên."
  }
  ```

---

### 5. `create_group_room`
Mô tả: Tự động tạo Discord Text Channel hoặc Private Thread riêng và phân quyền cho các thành viên nhóm.

#### Tham số đầu vào (Input Parameters):
| Tham Số | Kiểu Dữ Liệu | Bắt Buộc | Mô Tả |
| :--- | :---: | :---: | :--- |
| `room_name` | `string` | Có | Tên channel Discord cần tạo (ví dụ: `lab05-group-01`) |
| `member_ids` | `array[string]` | Có | Danh sách Discord User ID của các thành viên cần thêm |
| `is_private` | `boolean` | Không | Quyền riêng tư của channel (mặc định: `true`) |

#### Kết quả đầu ra (Output Schema):
* **Thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "room_id": "129812345678901234",
    "discord_channel_id": "129812345678901234",
    "channel_name": "group-lab05-group-01",
    "added_members": ["U123456", "U789012", "U345678"]
  }
  ```
* **Không thêm được thành viên (`207 Multi-Status`)**:
  ```json
  {
    "status": "partial_success",
    "room_id": "129812345678901234",
    "discord_channel_id": "129812345678901234",
    "channel_name": "group-lab05-group-01",
    "added_members": ["U123456"],
    "failed_members": [{"user_id": "U789012", "reason": "User not found"}]
  }
  ```
* **Lỗi hệ thống (`500 Internal Error`)**:
  ```json
  {
    "status": "error",
    "error_code": "PLATFORM_API_ERROR",
    "message": "Không có quyền tạo channel trên Discord."
  }
  ```

---

### 6. `send_message`
Mô tả: Gửi tin nhắn hướng dẫn, phân công task hoặc trao đổi trực tiếp với học viên hoặc kênh nhóm.

#### Tham số đầu vào (Input Parameters):
| Tham Số | Kiểu Dữ Liệu | Bắt Buộc | Mô Tả |
| :--- | :---: | :---: | :--- |
| `target_id` | `string` | Có | Discord Channel ID hoặc User ID nhận tin nhắn |
| `message` | `string` | Có | Nội dung tin nhắn (hỗ trợ định dạng Discord Markdown) |
| `attachments` | `array[object]` | Không | Các đính kèm (File, Embed, Button...) |

#### Kết quả đầu ra (Output Schema):
* **Thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "message_id": "MSG_100293",
    "delivered_at": "2026-07-30T12:02:00Z"
  }
  ```
* **Lỗi gửi tin nhắn (`400 / 403`)**:
  ```json
  {
    "status": "error",
    "error_code": "CANNOT_SEND_MESSAGE",
    "message": "Người dùng đã chặn tin nhắn trực tiếp từ Bot hoặc Room ID không tồn tại."
  }
  ```

---

### 7. `send_notification`
Mô tả: Tag tên học viên (@username) hoặc phát thông báo khẩn cấp/nhắc nhở quan trọng trong kênh làm việc.

#### Tham số đầu vào (Input Parameters):
| Tham Số | Kiểu Dữ Liệu | Bắt Buộc | Mô Tả |
| :--- | :---: | :---: | :--- |
| `room_id` | `string` | Có | Room ID nơi phát thông báo |
| `user_ids_to_tag` | `array[string]` | Có | Danh sách ID người dùng cần tag tên |
| `content` | `string` | Có | Nội dung thông báo |
| `urgency` | `string` | Không | Mức độ ưu tiên (`"normal"`, `"high"`, `"urgent"`) |

#### Kết quả đầu ra (Output Schema):
* **Thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "notified_users_count": 3,
    "discord_mentions": ["<@U123456>", "<@U789012>", "<@U345678>"]
  }
  ```
* **Lỗi hệ thống (`500 Internal Error`)**:
  ```json
  {
    "status": "error",
    "error_code": "NOTIFICATION_FAILED",
    "message": "Hệ thống thông báo đẩy bị ngắt kết nối."
  }
  ```

---

### 8. `parse_lab_requirements`
Mô tả: Sử dụng AI để phân tích yêu cầu bài lab nhóm thành các task nhỏ, ước lượng timeline/phase và tạo checklist tương ứng.

#### Tham số đầu vào (Input Parameters):
| Tham Số | Kiểu Dữ Liệu | Bắt Buộc | Mô Tả |
| :--- | :---: | :---: | :--- |
| `lab_id` | `string` | Có | Mã bài lab cần phân tích |
| `member_count` | `integer` | Có | Số lượng thành viên trong nhóm |
| `duration_hours` | `number` | Không | Thời lượng làm lab dự kiến (tính theo giờ) |

#### Kết quả đầu ra (Output Schema):
* **Thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "tasks": [
      {
        "task_id": "T1",
        "title": "Thiết kế Schema Database",
        "phase": "Phase 1 (0-30 phút)",
        "checklist": ["Tạo bảng User", "Tạo bảng Task"]
      },
      {
        "task_id": "T2",
        "title": "Xây dựng API Backend",
        "phase": "Phase 2 (30-90 phút)",
        "checklist": ["Viết API GET /tasks", "Viết API POST /tasks"]
      }
    ]
  }
  ```
* **Không phân tích được (`422 Unprocessable`)**:
  ```json
  {
    "status": "empty",
    "error_code": "UNABLE_TO_PARSE",
    "message": "Nội dung bài lab quá ngắn hoặc thiếu thông tin để chia task."
  }
  ```

---

### 9. `assign_task`
Mô tả: Phân công task và checklist cho từng thành viên trên Discord sau khi Nhóm trưởng đã xác nhận chia công việc. Trả về danh sách Markdown Checklist để Bot gửi trực tiếp vào channel nhóm Discord.

#### Tham số đầu vào (Input Parameters):
| Tham Số | Kiểu Dữ Liệu | Bắt Buộc | Mô Tả |
| :--- | :---: | :---: | :--- |
| `group_id` | `string` | Có | Mã định danh nhóm |
| `assignments` | `array[object]` | Có | Danh sách phân công: `[{ user_id, task_id, deadline }]` |

#### Kết quả đầu ra (Output Schema):
* **Thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "assigned_count": 3,
    "assignments_summary": [
      "- [ ] Task `T1`: Phân công cho <@U123456> (Deadline: 2026-07-30T18:00:00Z)",
      "- [ ] Task `T2`: Phân công cho <@U789012> (Deadline: 2026-07-30T18:00:00Z)"
    ],
    "message": "Đã phân công thành công 3 task cho nhóm G01 trên Discord."
  }
  ```
* **Không tìm thấy công việc (`404 Not Found`)**:
  ```json
  {
    "status": "empty",
    "error_code": "INVALID_TASK_ID",
    "message": "Mã task_id T99 không tồn tại trong bài lab này."
  }
  ```

---

### 10. `track_group_progress`
Mô tả: Tổng hợp phần trăm hoàn thành, danh sách task đã xong / chưa xong của tất cả thành viên trong nhóm.

#### Tham số đầu vào (Input Parameters):
| Tham Số | Kiểu Dữ Liệu | Bắt Buộc | Mô Tả |
| :--- | :---: | :---: | :--- |
| `group_id` | `string` | Có | Mã nhóm cần kiểm tra tiến độ |

#### Kết quả đầu ra (Output Schema):
* **Thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "group_id": "G01",
    "overall_completion_percent": 75.0,
    "members_progress": [
      {
        "user_id": "U123456",
        "task_title": "Thiết kế Schema Database",
        "status": "completed",
        "completed_checklist": 2,
        "total_checklist": 2
      },
      {
        "user_id": "U789012",
        "task_title": "Xây dựng API Backend",
        "status": "in_progress",
        "completed_checklist": 1,
        "total_checklist": 2
      }
    ]
  }
  ```
* **Không có dữ liệu tiến độ (`404 Not Found`)**:
  ```json
  {
    "status": "empty",
    "error_code": "NO_TASK_ASSIGNED",
    "message": "Nhóm này chưa được phân công task nào."
  }
  ```

---

### 11. `generate_reflection`
Mô tả: Tổng hợp lịch sử làm bài, mức độ hoàn thành task và thái độ hợp tác của học viên để sinh bài đánh giá/reflection cá nhân.

#### Tham số đầu vào (Input Parameters):
| Tham Số | Kiểu Dữ Liệu | Bắt Buộc | Mô Tả |
| :--- | :---: | :---: | :--- |
| `user_id` | `string` | Có | Mã học viên |
| `lab_id` | `string` | Có | Mã bài lab |

#### Kết quả đầu ra (Output Schema):
* **Thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "user_id": "U123456",
    "reflection": {
      "summary": "Bạn đã hoàn thành xuất sắc nhiệm vụ thiết kế Database đúng thời hạn.",
      "strengths": ["Quản lý thời gian tốt", "Hỗ trợ thành viên khác trong nhóm"],
      "improvements": ["Nên viết comment rõ ràng hơn trong file migration"]
    }
  }
  ```
* **Thiếu dữ liệu hoàn thành (`400 Bad Request`)**:
  ```json
  {
    "status": "empty",
    "error_code": "INCOMPLETE_LAB",
    "message": "Học viên chưa hoàn thành bài lab nên chưa thể sinh reflection."
  }
  ```

---

### 12. `schedule_reminder`
Mô tả: Thiết lập lịch thông báo tự động (Timer / Cron) để nhắc học viên cập nhật tiến độ hoặc thông báo khi sắp đến deadline.

#### Tham số đầu vào (Input Parameters):
| Tham Số | Kiểu Dữ Liệu | Bắt Buộc | Mô Tả |
| :--- | :---: | :---: | :--- |
| `target_id` | `string` | Có | User ID hoặc Room ID nhận nhắc nhở |
| `remind_at` | `string` | Có | Thời điểm nhắc nhở (Định dạng ISO 8601, ví dụ: `2026-07-30T14:30:00Z`) |
| `message` | `string` | Có | Nội dung nhắc nhở |
| `repeat_every_minutes` | `integer` | Không | Chu kỳ lặp lại tính theo phút (nếu cần lặp) |

#### Kết quả đầu ra (Output Schema):
* **Thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "reminder_id": "REM_90123",
    "scheduled_time": "2026-07-30T14:30:00Z"
  }
  ```
* **Lỗi thời gian không hợp lệ (`400 Bad Request`)**:
  ```json
  {
    "status": "error",
    "error_code": "INVALID_TIME",
    "message": "Thời gian hẹn giờ `remind_at` phải ở trong tương lai."
  }
  ```

---

### 13. `extend_deadline`
Mô tả: Cập nhật giãn mốc thời gian hoàn thành task cho học viên trong trường hợp gặp khó khăn kỹ thuật hoặc lý do khách quan.

#### Tham số đầu vào (Input Parameters):
| Tham Số | Kiểu Dữ Liệu | Bắt Buộc | Mô Tả |
| :--- | :---: | :---: | :--- |
| `task_id` | `string` | Có | Mã task cần gia hạn |
| `user_id` | `string` | Có | Mã học viên sở hữu task |
| `extra_minutes` | `integer` | Có | Số phút xin gia hạn thêm (ví dụ: `30`) |
| `reason` | `string` | Không | Lý do xin gia hạn |

#### Kết quả đầu ra (Output Schema):
* **Thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "task_id": "T2",
    "old_deadline": "2026-07-30T14:00:00Z",
    "new_deadline": "2026-07-30T14:30:00Z",
    "message": "Đã gia hạn thành công thêm 30 phút."
  }
  ```
* **Không được phép gia hạn (`403 Forbidden`)**:
  ```json
  {
    "status": "error",
    "error_code": "MAX_EXTENSION_REACHED",
    "message": "Task này đã vượt quá số lần xin gia hạn cho phép (Tối đa 2 lần)."
  }
  ```

---

### 14. `analyze_student_issue`
Mô tả: Tiếp nhận mô tả sự cố/log lỗi của học viên, phân tích nguyên nhân và đưa ra hướng dẫn khắc phục cụ thể.

#### Tham số đầu vào (Input Parameters):
| Tham Số | Kiểu Dữ Liệu | Bắt Buộc | Mô Tả |
| :--- | :---: | :---: | :--- |
| `user_id` | `string` | Có | Mã học viên báo lỗi |
| `task_id` | `string` | Có | Mã task đang thực hiện |
| `issue_description` | `string` | Có | Mô tả lỗi hoặc câu hỏi của học viên |
| `error_log` | `string` | Không | Đoạn log lỗi hoặc mã lỗi từ Terminal/IDE |

#### Kết quả đầu ra (Output Schema):
* **Thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "root_cause": "Thiếu biến môi trường DATABASE_URL trong tệp .env",
    "suggested_solution": "Hãy tạo tệp .env ở thư mục gốc và thêm dòng DATABASE_URL=mongodb://localhost:27017/lab",
    "reference_links": ["https://docs.example.com/env-setup"]
  }
  ```
* **Lỗi không phân tích được (`422 Unprocessable Entity`)**:
  ```json
  {
    "status": "empty",
    "error_code": "UNCLEAR_ISSUE",
    "message": "Mô tả lỗi quá ngắn hoặc log lỗi không hợp lệ. Vui lòng cung cấp thêm chi tiết log Terminal."
  }
  ```

---

### 15. `fetch_peer_solution`
Mô tả: Tìm kiếm các thành viên trong cùng nhóm đã hoàn thành task tương tự/liên quan để trả về đoạn mã nguồn tham khảo (Code Block) trực tiếp trên Discord.

#### Tham số đầu vào (Input Parameters):
| Tham Số | Kiểu Dữ Liệu | Bắt Buộc | Mô Tả |
| :--- | :---: | :---: | :--- |
| `group_id` | `string` | Có | Mã nhóm |
| `current_task_id` | `string` | Có | Mã task học viên đang trễ/gặp khó khăn |
| `requesting_user_id` | `string` | Có | Mã học viên yêu cầu hỗ trợ |

#### Kết quả đầu ra (Output Schema):
* **Thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "helpers": [
      {
        "user_id": "U123456",
        "full_name": "Pham Duc Thien",
        "completed_task_id": "T1",
        "code_snippet": "```python\n# Code mẫu tham khảo...\nimport os\ndef init_database():\n    db_url = os.getenv('DATABASE_URL')\n    return True\n```",
        "github_commit_url": "https://github.com/example-org/lab-g01/commit/a1b2c3d4",
        "note": "Học viên này đã hoàn thành task T1 liên quan đến phần kết nối Database."
      }
    ]
  }
  ```
* **Không tìm thấy học viên nào hoàn thành (`404 Not Found`)**:
  ```json
  {
    "status": "empty",
    "data": [],
    "message": "Hiện chưa có thành viên nào trong nhóm hoàn thành task tiền đề này để tham khảo."
  }
  ```
* **Lỗi hệ thống (`500 Internal Error`)**:
  ```json
  {
    "status": "error",
    "error_code": "PEER_FETCH_FAILED",
    "message": "Không thể truy xuất dữ liệu mã nguồn của các thành viên trong nhóm."
  }
  ```
