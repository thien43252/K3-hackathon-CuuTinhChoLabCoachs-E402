# BẢNG PHÂN TÍCH & PHẢN HỒI USER TESTING

> **Dự án:** Trợ lý AI Học viên Labcode (Student Assistant AI Agent)
> **Mục tiêu:** Kiểm thử thực tế với $\ge 5$ người ngoài nhóm trước phiên Dry Run & bảo vệ CP5.
> **Thời lượng:** 10 phút / người thử.

## 📋 BẢNG LOG PHẢN HỒI CHI TIẾT

|     STT     | Người thử*(Tên / Vai trò — Willing User?)*                       | Task được giao                                                              | Quan sát chi tiết*(Họ bấm gì, kẹt/lúng túng ở đâu)*                                                                                              | Trích dẫn nguyên văn (Quote 3 câu hỏi)                                                                                                                                                                                                                                       | Mức nghiêm trọng*(Blocker / Major / Minor / Insight)* |
| :----------: | :--------------------------------------------------------------------- | :----------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------- |
| **01** | Nguyễn Minh Quang<br /> *(Học viên cá nhân — Willing User #1)* | Hỏi hướng dẫn làm lab & gỡ lỗi`ModuleNotFoundError` khi chạy FastAPI | Bấm ngay nút hỏi bài lab. Khi bị lỗi, không dán log lỗi mà chỉ gõ "Em bị lỗi", đứng chờ bot 30 giây rồi mới dán log khi bot yêu cầu. | •*Khó chịu:* "Bot không tự biết mình đang bị lỗi gì mà bắt dán log."  • *Độ tin:* "Tin, vì đưa đúng lệnh `pip install` chuẩn."  • *Dùng thật:* "Có dùng, nhưng muốn bot tự đọc log luôn."                                               | **Minor**                                          |
| **02** | *Đoàn Văn Tuyền (Học viên cá nhân — Willing User #2)*      | Tạo phòng nhóm Discord, chia task cho 4 người và theo dõi tiến độ    | Tạo room thành công. Khi chia task xong, tưởng bot tự phân công luôn nên không gõ lệnh confirm "OK phân công đi". Đứng đợi 1 phút.     | •*Khó chịu:* "Không rõ là bot đang đợi mình confirm hay đã chia task xong rồi."  • *Độ tin:* "Có tin danh sách task, nhưng không biết các bạn khác đã nhận chưa."  • *Dùng thật:* "Có dùng nếu bot nhắc nhở rõ hơn bước tiếp theo." | **Major**                                          |
| **03** | Nguyễn Huy Hoàng (Học viên Zone B)                                | Thử hỏi bài Kubernetes không có trong tài liệu & hỏi viết essay hộ   | Nhập prompt hỏi Kubernetes bài giảng trang mấy và nhờ viết bài essay tiếng Anh.                                                                   | •*Khó chịu:* "Bot trả lời hơi dài dòng khi từ chối."  • *Độ tin:* "Rất tin vì bot không bịa ra số trang bài giảng giả."  • *Dùng thật:* "Đánh giá cao việc bot từ chối viết essay hộ học viên."                                            | **Insight**                                        |
| **04** | **Xuân Trường**(Học viên Zone B)                            | Xin gia hạn task T3 lần 3 và xin xem code tham khảo của đồng đội      | Nhập lệnh xin gia hạn thêm 30 phút. Nhận thông báo từ chối do vượt quá 2 lần, sau đó bấm xin xem code tham khảo.                          | •*Khó chịu:* "Ứng dụng từ chối gia hạn hơi cứng nhắc."  • *Độ tin:* "Tin code tham khảo vì bot hiển thị rõ tên bạn đã làm xong."  • *Dùng thật:* "Dùng thật nếu bot hỗ trợ gợi ý hướng làm thay vì chỉ từ chối."                    | **Major**                                          |
| **05** | **Ngô Hằng**(Học viên Zone B)                                | Báo hoàn thành bài lab và yêu cầu bot tạo bài đánh giá Reflection  | Gõ lệnh yêu cầu tạo reflection sau khi hoàn thành lab nhóm.                                                                                         | •*Khó chịu:* "Bài reflection xuất ra hơi nhanh nhưng format Markdown nhìn đẹp."  • *Độ tin:* "Tin 80%, vì có vài nhận xét hơi chung chung."  • *Dùng thật:* "Có dùng để nộp báo cáo tổng kết bài lab."                                       | **Minor**                                          |

---

## 📊 TỔNG HỢP & HÀNH ĐỘNG SAU VALIDATION

### 1. Chủ đề lặp lại nhiều nhất

> **Vấn đề luồng giao tiếp:** Học viên/Nhóm trưởng chưa nhận biết rõ **bước tiếp theo cần làm gì.**

### 2. 1-2 Thay đổi làm ngay trước Demo

> 1. **Cập nhật Prompt System:** Thêm câu hướng dẫn bước tiếp theo rõ ràng ở cuối mỗi phản hồi.
> 2. **Bổ sung mẫu gợi ý gỡ lỗi:** Khi học viên báo lỗi mơ hồ, bot trả lời kèm ví dụ mẫu dán log ngay lập tức.

### 3. Giữ nguyên có lý do

> **Giữ nguyên chính sách từ chối gia hạn quá 2 lần:** Mặc dù người thử cảm thấy "cứng nhắc", nhưng đây là **Business Constraint**của khóa học nhằm đảm bảo tiến độ làm bài, không thể cho phép gia hạn vô hạn.

### 4. Đưa vào Backlog

> 1. Tự động đọc log trực tiếp từ Terminal/IDE của học viên mà không bắt dán tay.
> 2. Cá nhân hóa bài đánh giá Reflection sâu hơn dựa trên phân tích commit Git thực tế.
