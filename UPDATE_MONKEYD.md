# Cập nhật MonkeyD tương tác — không cần server phụ

1. Giải nén `monkeyd-update.zip` vào một thư mục mới.
2. Mở repository GitHub đang dùng để deploy app.
3. Chọn **Add file → Upload files** và kéo các file Python cùng thư mục
   `remote_component` từ bản giải nén vào. Không upload nguyên file ZIP.
4. Commit changes vào đúng nhánh mà Streamlit đang dùng (thường là `main`).
5. Kiểm tra repo có đủ các đường dẫn sau:

```text
app.py
scraper.py
crawl_worker.py
remote_job.py
remote_browser.py
remote_ui.py
remote_component/index.html
```

Nếu không kéo được thư mục `remote_component`, dùng **Add file → Create new file**,
đặt tên `remote_component/index.html`, mở file HTML tương ứng trong bản giải nén
bằng Notepad rồi sao chép toàn bộ nội dung vào và commit. Không tạo file ở root
với tên `index.html` vì tool cần đúng đường dẫn thư mục trên.

Giữ nguyên secrets đang có:

```toml
PUBLIC_DEPLOYMENT = "true"
BROWSER_HEADLESS = "true"
VBEE_CTA_ENABLED = "true"
SHOPEE_AFFILIATE_URL = ""
```

Streamlit thường cập nhật sau commit. Nếu app vẫn hiện thông báo cũ, vào
**Manage app → Reboot app**, rồi refresh trang. Không cần đổi packages.txt,
requirements.txt, thêm API key, nhập thẻ thanh toán hoặc chuyển hosting.

## Cách dùng

1. Nhập URL MonkeyD và bấm **Convert**.
2. Nếu trang khóa, đợi phần **Thao tác với trang nguồn** hiện ảnh Chromium.
3. Bấm đúng liên kết/nút yêu cầu của MonkeyD **ngay trong ảnh**. Ảnh này tương tác
   với browser trên server, không phải ảnh minh họa. Liên kết nguồn không phải
   Shopee affiliate của tool.
4. Nếu mở tab ngoài, có thể chọn tab, cuộn hoặc bấm **Về trang truyện**.
5. Khi nội dung đã hiện, bấm **Lấy nội dung**. Tool sẽ trả Raw/Clean/Markdown;
   Find/Replace và tải file hoạt động như trước.

Nếu ảnh vừa thay đổi và cú bấm bị từ chối, đợi ảnh mới rồi bấm lại. Không có tự
click liên kết quảng cáo, gọi trực tiếp hàm unlock hoặc inject cookie giả.

Phiên giới hạn 4 phút, tự đóng khi mất kết nối khoảng 45 giây; có nút **Hủy và đóng
Chromium**. Để giữ gói free nhẹ, chỉ một job được xử lý tại một thời điểm.

Đã xác minh trên URL chương trong ảnh người dùng bằng Chromium thật ở máy thử.
Trang có CAPTCHA, yêu cầu ứng dụng di động thực, hoặc chặn IP hosting vẫn có thể
không hoạt động. Chưa xác minh bản mới trên chính URL Streamlit của người dùng.
