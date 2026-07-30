# Ma Trận Test Case — 8 Agent Tools + 1 Slash Command

> Cập nhật: 2026-07-31 · Tools đã đơn giản hóa (user_id, group_id auto-resolve từ context)

## Cách đọc

| Cột | Ý nghĩa |
|---|---|
| **Case** | Mã test case: `T{N}_{H|U}_{N}` (Tool số · Happy/Unhappy · STT) |
| **Mô tả** | Tình huống test |
| **Input** | Tham số truyền vào tool |
| **Context** | Discord context cần mock (nếu có) |
| **Expected status** | `success` / `empty` / `error` |
| **Expected error_code** | Mã lỗi (nếu unhappy) |
| **Expected output** | Field quan trọng trong response |

---

## Tool 1: `get_lab_content(lab_id)`

| Case | Mô tả | Input | Context | Expected status | Expected error_code | Expected output |
|---|---|---|---|---|---|---|
| **T1_H1** | Lấy nội dung lab đã cache thành công | `lab_id="DAY05"` | — | `success` | — | `lab_objective` ≠ "", `tasks` ≥ 2 items, `sitemap` ≠ [] |
| **T1_H2** | Lấy lab với insights đầy đủ (AI extraction) | `lab_id="DAY05"` | — | `success` | — | `timeline` ≠ "", `file_summaries` ≥ 1, `code_examples` ≥ 1 |
| **T1_H3** | Lấy lab với insights rỗng (regex fallback) | `lab_id="DAY05"` (lab không có AI key) | — | `success` | — | `tasks` ≥ 1 (từ regex), `lab_objective` có nội dung |
| **T1_U1** | lab_id rỗng | `lab_id=""` | — | `empty` | `INVALID_INPUT` | message: "lab_id không được để trống" |
| **T1_U2** | Lab chưa được admin import | `lab_id="NOT_EXIST"` | — | `empty` | `NO_CACHED_DATA` | message: "Admin cần /admin-add-lab trước" |
| **T1_U3** | Exception không xác định | `lab_id="TRIGGER_500"` | — | `error` | `CONTENT_LOOKUP_FAILED` | message chứa lỗi |

---

## Tool 2: `create_group_room(room_name, member_ids, is_private=True)`

| Case | Mô tả | Input | Context | Expected status | Expected error_code | Expected output |
|---|---|---|---|---|---|---|
| **T2_H1** | Tạo room thành công với tất cả members hợp lệ | `room_name="G01"`, `member_ids=["U123456", "U789012"]` | — (mock) | `success` | — | `channel_name` = "group-g01", `added_members` = ["U123456", "U789012"] |
| **T2_H2** | Tạo room private (mặc định) | `room_name="G01"`, `member_ids=["U123456"]` | — (mock) | `success` | — | `room_id` ≠ "" |
| **T2_U1** | room_name rỗng | `room_name=""`, `member_ids=["U123456"]` | — | `empty` | `INVALID_INPUT` | message: "room_name và danh sách member_ids không được để trống" |
| **T2_U2** | Có member không tìm thấy trên server | `room_name="G01"`, `member_ids=["U123456", "INVALID_999"]` | — (mock) | `empty` | `INVALID_MEMBERS` | `failed_members` có item với user_id="INVALID_999", `valid_count`=1 |
| **T2_U3** | Tất cả members đều invalid | `room_name="G01"`, `member_ids=["INVALID_1", "INVALID_2"]` | — (mock) | `empty` | `INVALID_MEMBERS` | `valid_count`=0 |
| **T2_U4** | Trigger test error | `room_name="TRIGGER_500"` | — | `error` | `PLATFORM_API_ERROR` | message chứa lỗi |

---

## Tool 3: `generate_group_plan(lab_id, members, notes=None)`

| Case | Mô tả | Input | Context | Expected status | Expected error_code | Expected output |
|---|---|---|---|---|---|---|
| **T3_H1** | Tạo plan thành công với lab có insights + members đủ role | `lab_id="DAY05"`, `members=[{user_id:"U1",role:"PM"},{user_id:"U2",role:"Backend"}]` | group_id="G01" | `success` | — | `todo_list` ≠ [], `phases` ≥ 1, `summary` ≥ 1000 chars |
| **T3_H2** | Tạo plan với custom_tasks cho member | `lab_id="DAY05"`, `members=[{user_id:"U1",role:"PM",custom_tasks:["Review code"]}]` | group_id="G01" | `success` | — | `members_plan[0].tasks` có task ID prefix "CT" |
| **T3_H3** | Tạo plan với notes | `lab_id="DAY05"`, `members=[...]`, `notes="Dùng FastAPI"` | group_id="G01" | `success` | — | `notes` = "Dùng FastAPI" trong response |
| **T3_H4** | Tạo plan với insight tasks → dynamic phases | `lab_id="DAY05"` (lab có ≥2 tasks) | group_id="G01" | `success` | — | `phases` dùng task names từ insights (không fallback canonical) |
| **T3_U1** | Không có Discord context (ngoài group room) | `lab_id="DAY05"`, `members=[...]` | group_id=null | `empty` | `NO_CONTEXT` | message: "Tool chỉ dùng được trong group room Discord" |
| **T3_U2** | lab_id rỗng | `lab_id=""`, `members=[...]` | group_id="G01" | `empty` | `INVALID_INPUT` | message: "lab_id không được để trống" |
| **T3_U3** | members rỗng | `lab_id="DAY05"`, `members=[]` | group_id="G01" | `empty` | `INVALID_MEMBERS` | message: "Danh sách thành viên không được để trống" |
| **T3_U4** | Lab chưa được import | `lab_id="NOT_EXIST"`, `members=[...]` | group_id="G01" | `empty` | `NO_LAB_DATA` | message: "Admin cần /admin-add-lab trước" |
| **T3_U5** | Lab không có insight tasks | `lab_id="MINIMAL"` (lab ít nội dung) | group_id="G01" | `success` | — | fallback canonical 4 phases vẫn chạy |

---

## Tool 4: `get_group_plan()`

| Case | Mô tả | Input | Context | Expected status | Expected error_code | Expected output |
|---|---|---|---|---|---|---|
| **T4_H1** | Lấy plan đã tạo trước đó | — | group_id="G01" | `success` | — | `phases` ≠ [], `members_plan` ≠ [], `notes` tồn tại |
| **T4_H2** | Lấy plan vừa mới generate | — | group_id="G01" (sau T3_H1) | `success` | — | `lab_id` = "DAY05", `created_at` ≠ "" |
| **T4_U1** | Không có Discord context | — | group_id=null | `empty` | `NO_CONTEXT` | message: "Tool chỉ dùng được trong group room Discord" |
| **T4_U2** | Nhóm chưa có plan | — | group_id="G99" (chưa generate) | `empty` | `NO_PLAN_FOUND` | message: "Chưa có kế hoạch nào. Dùng generate_group_plan" |

---

## Tool 5: `track_group_progress()`

| Case | Mô tả | Input | Context | Expected status | Expected error_code | Expected output |
|---|---|---|---|---|---|---|
| **T5_H1** | Có plan + có assignments (tiến độ 50%) | — | group_id="G01" (đã gen plan + vài task completed) | `success` | — | `overall_completion_pct` > 0, `progress_bar` chứa "█", `total_tasks` > 0 |
| **T5_H2** | Có plan + chưa có assignments (mới tạo plan) | — | group_id="G01" (vừa gen plan, chưa update gì) | `success` | — | `overall_completion_pct` = 0, `total_tasks` > 0 |
| **T5_H3** | Team đã hoàn thành 100% | — | group_id="G01" (all tasks completed) | `success` | — | `overall_completion_pct` = 100, `progress_bar` = "[████████████████████] 100%" |
| **T5_U1** | Không có Discord context | — | group_id=null | `empty` | `NO_CONTEXT` | message: "Tool chỉ dùng được trong group room Discord" |
| **T5_U2** | Team chưa chốt plan | — | group_id="G99" (chưa generate) | `empty` | `NO_PLAN` | message: "chưa chốt kế hoạch. Hãy yêu cầu leader gọi generate_group_plan" |

---

## Tool 6: `update_group_progress(task_id, status=None, completed_checklist=None)`

| Case | Mô tả | Input | Context | Expected status | Expected error_code | Expected output |
|---|---|---|---|---|---|---|
| **T6_H1** | Mark task completed | `task_id="T1"`, `status="completed"` | group_id="G01", user_id="U123456" | `success` | — | `new_status` = "completed", `completed_checklist` = `total_checklist` (auto full) |
| **T6_H2** | Update checklist số (không change status) | `task_id="T1"`, `completed_checklist=3` | group_id="G01", user_id="U123456" | `success` | — | `completed_checklist` = 3 |
| **T6_H3** | Update in_progress | `task_id="T1"`, `status="in_progress"` | group_id="G01", user_id="U123456" | `success` | — | `new_status` = "in_progress" |
| **T6_H4** | Update → trả về overall_team_progress | `task_id="T1"`, `status="completed"` | group_id="G01", user_id="U123456" | `success` | — | `overall_team_progress_pct` ≥ 0 |
| **T6_U1** | Không có Discord context | `task_id="T1"`, `status="completed"` | group_id=null, user_id=null | `empty` | `NO_CONTEXT` | message: "Tool chỉ dùng được trong Discord group room" |
| **T6_U2** | task_id rỗng | `task_id=""`, `status="completed"` | group_id="G01", user_id="U123456" | `empty` | `INVALID_INPUT` | message: "task_id không được để trống" |
| **T6_U3** | Assignment không tồn tại | `task_id="T99"`, `status="completed"` | group_id="G01", user_id="U123456" | `empty` | `NO_ASSIGNMENT_FOUND` | message: "Cần leader tạo plan trước" |
| **T6_U4** | Status không hợp lệ | `task_id="T1"`, `status="invalid_status"` | group_id="G01", user_id="U123456" | `empty` | `INVALID_STATUS` | message: "status phải là 'in_progress' hoặc 'completed'" |
| **T6_U5** | completed_checklist âm | `task_id="T1"`, `completed_checklist=-1` | group_id="G01", user_id="U123456" | `empty` | `INVALID_CHECKLIST` | message: "completed_checklist không được âm" |

---

## Tool 7: `analyze_student_issue(task_id, issue_description, error_log=None)`

| Case | Mô tả | Input | Context | Expected status | Expected error_code | Expected output |
|---|---|---|---|---|---|---|
| **T7_H1** | Lỗi env/database (keyword match) | `task_id="T1"`, `issue_description="Lỗi kết nối database"`, `error_log="MongoError: connection failed"` | user_id="U123456" | `success` | — | `root_cause` chứa "DATABASE_URL" hoặc "Mongo", `suggested_solution` ≠ "" |
| **T7_H2** | Lỗi module/import | `task_id="T1"`, `issue_description="Lỗi import module pandas"` | user_id="U123456" | `success` | — | `root_cause` chứa "chưa cài đặt thư viện" |
| **T7_H3** | Lỗi không xác định → fallback | `task_id="T1"`, `issue_description="Code chạy sai kết quả đầu ra"` | user_id="U123456" | `success` | — | `root_cause` chứa "Async/Await" hoặc "Pydantic" (default fallback) |
| **T7_U1** | issue_description quá ngắn | `task_id="T1"`, `issue_description="Lỗi"` | user_id="U123456" | `empty` | `UNCLEAR_ISSUE` | message: "Mô tả lỗi quá ngắn hoặc log lỗi không hợp lệ" |
| **T7_U2** | task_id rỗng | `task_id=""`, `issue_description="Bị lỗi mạng"` | user_id="U123456" | `empty` | `INVALID_INPUT` | message: "task_id và issue_description không được để trống" |
| **T7_U3** | issue_description rỗng | `task_id="T1"`, `issue_description=""` | user_id="U123456" | `empty` | `INVALID_INPUT` | message: "task_id và issue_description không được để trống" |

---

## Tool 8: `list_members()`

| Case | Mô tả | Input | Context | Expected status | Expected error_code | Expected output |
|---|---|---|---|---|---|---|
| **T8_H1** | Group room có members → danh sách đầy đủ | — | group_id="G01", members=[{id:"U1",name:"A"},{id:"U2",name:"B"}] | `success` | — | `members` = 2 items, `total` = 2, `group_id` = "G01" |
| **T8_H2** | Group room 1 member | — | group_id="G01", members=[{id:"U1",name:"A"}] | `success` | — | `total` = 1 |
| **T8_U1** | General channel (no context) | — | context rỗng | `empty` | `NO_CONTEXT` | message: "Tool chỉ dùng được trong group room" |
| **T8_U2** | Group room nhưng members rỗng | — | group_id="G01", members=[] | `empty` | `NO_CONTEXT` | message: "Tool chỉ dùng được trong group room" |

---

## Tất cả Slash Commands (5 commands)

### SC1: `/make-plan` — Tạo draft plan (dùng LLM)

| Case | Mô tả | Input | Channel | Expected behavior |
|---|---|---|---|---|
| **SC1_H1** | Tạo draft thành công | `lab_number=3`, `requirement="Dùng FastAPI"` | Group room | ✅ Plan được gửi, có nội dung Markdown |
| **SC1_U1** | Dùng ở ngoài group room | `lab_number=3`, `requirement="test"` | General / DM | ❌ Báo "chỉ dùng trong group room" |

### SC2: `/admin-add-lab` — [ADMIN] Đăng ký lab repo

| Case | Mô tả | Input | Permission | Expected behavior |
|---|---|---|---|---|
| **SC2_H1** | Add lab thành công (repo mới) | `lab_id="test"`, `repo_url=valid_url`, `lab_date="2026-08-01"` | Admin | ✅ Clone + phân tích + lưu DB + trả về sitemap |
| **SC2_H2** | Add lab đã tồn tại (update) | `lab_id="test"` (lab đã có) | Admin | ✅ Update lab_materials, không crash |
| **SC2_U1** | Không phải admin | `lab_id="test", ...` | Non-admin | ❌ 403 MissingPermissions |
| **SC2_U2** | Repo không tồn tại / không clone được | `lab_id="test"`, `repo_url="https://invalid.url/repo"` | Admin | ❌ Báo lỗi clone |
| **SC2_U3** | Exception không xác định | — | Admin | ❌ followup gửi lỗi |

### SC3: `/admin-list-labs` — [ADMIN] Xem danh sách lab

| Case | Mô tả | Input | Permission | Expected behavior |
|---|---|---|---|---|
| **SC3_H1** | Có lab đã đăng ký | — | Admin | ✅ Trả về danh sách lab |
| **SC3_H2** | Chưa có lab nào | — | Admin | ✅ Báo "chưa có lab" |
| **SC3_U1** | Không phải admin | — | Non-admin | ❌ 403 MissingPermissions |

### SC4: `/admin-assign-lab` — [ADMIN] Gán lab cho user

| Case | Mô tả | Input | Permission | Expected behavior |
|---|---|---|---|---|
| **SC4_H1** | Gán lab thành công | `user_id="U123"`, `lab_id="DAY05"` | Admin | ✅ Cập nhật users.today_lab_id |
| **SC4_U1** | Không phải admin | — | Non-admin | ❌ 403 MissingPermissions |
| **SC4_U2** | User không tồn tại | `user_id="INVALID"` | Admin | ❌ Báo lỗi |
| **SC4_U3** | Lab không tồn tại trong lab_materials | `user_id="U123"`, `lab_id="NON_EXIST"` | Admin | ❌ Báo lỗi |

### SC5: `/update-progress` — Cập nhật tiến độ (không LLM)

| Case | Mô tả | Input | Channel | Expected behavior |
|---|---|---|---|---|
| **SC5_H1** | Mark task completed | `task_id=T1`, `status=completed` | Group room | ✅ Cập nhật, new_status=completed + team progress |
| **SC5_H2** | Mark in_progress | `task_id=T1`, `status=in_progress` | Group room | ✅ Cập nhật thành công |
| **SC5_H3** | Cập nhật checklist count | `task_id=T1`, `checklist_done=3` | Group room | ✅ Cập nhật checklist |
| **SC5_U1** | Dùng ở ngoài group room | `task_id=T1` | General channel | ❌ Báo "chỉ dùng trong group room" |
| **SC5_U2** | Task không tồn tại | `task_id=T99` | Group room | ❌ Báo "không tìm thấy task" |

### SC6: `/view-progress` — Xem tiến độ (không LLM)

| Case | Mô tả | Input | Channel | Expected behavior |
|---|---|---|---|---|
| **SC6_H1** | Có plan + có tiến độ → show progress bar | — | Group room | ✅ Trả về progress_bar, total/completed tasks, member breakdown |
| **SC6_H2** | Có plan nhưng chưa có progress → 0% | — | Group room | ✅ Trả về 0%, progress bar rỗng |
| **SC6_U1** | Dùng ở ngoài group room | — | General channel | ❌ Báo "chỉ dùng trong group room" |
| **SC6_U2** | Team chưa chốt plan | — | Group room | ❌ Báo "nhóm chưa chốt kế hoạch" |

---

## Cross-cutting: Permission & Context (từ system_prompt + discord_bot)

| Case | Mô tả | Expected behavior |
|---|---|---|
| **CC1** | General channel — chỉ dùng `get_lab_content` + `create_group_room` + `list_members` | Agent phải reject các tool khác với lý do channel type |
| **CC2** | Group room — dùng được tất cả 8 tools | Agent cho phép đầy đủ |
| **CC3** | Bot không được @mention → không response | `if bot.user not in message.mentions: return` |
| **CC4** | Context string có members list đầy đủ | Agent identify được ai là ai dù không @mention |
| **CC5** | Slash command admin — non-admin dùng | ❌ MissingPermissions error handler gửi ephemeral message |
| **CC6** | Slash command admin — đúng admin dùng | ✅ Command chạy bình thường |

---

## Tổng hợp coverage

| Tool / Command | Happy cases | Unhappy cases | Tổng |
|---|---|---|---|
| T1: get_lab_content | 3 | 3 | **6** |
| T2: create_group_room | 2 | 4 | **6** |
| T3: generate_group_plan | 4 | 5 | **9** |
| T4: get_group_plan | 2 | 2 | **4** |
| T5: track_group_progress | 3 | 2 | **5** |
| T6: update_group_progress | 4 | 5 | **9** |
| T7: analyze_student_issue | 3 | 3 | **6** |
| T8: list_members | 2 | 2 | **4** |
| SC1: /make-plan | 1 | 1 | **2** |
| SC2: /admin-add-lab | 2 | 3 | **5** |
| SC3: /admin-list-labs | 2 | 1 | **3** |
| SC4: /admin-assign-lab | 1 | 3 | **4** |
| SC5: /update-progress | 3 | 2 | **5** |
| SC6: /view-progress | 2 | 2 | **4** |
| Cross-cutting | 6 | — | **6** |
| **TOTAL** | **40** | **38** | **78+** |
