# Cập nhật dark theme và banner Vbee

Giải nén `theme-banner-update.zip` và upload nội dung lên GitHub của app:

- `app.py`
- `affiliate.py`
- `assets/vbee-aivoice.png` (giữ đúng thư mục `assets`)
- `remote_component/index.html`
- `.streamlit/config.toml`

Nếu không upload được `.streamlit`, mở file `.streamlit/config.toml` hiện có trên
GitHub, chọn Edit và thay nội dung bằng file trong gói cập nhật. Commit changes,
đợi Streamlit cập nhật rồi Reboot app để áp dụng cấu hình theme.

Nếu trình duyệt đã chọn Light thủ công: menu ⋮ → Settings → Theme → Dark, rồi
tải lại. Bản mặc định của app mới là dark; lựa chọn cá nhân có thể ghi đè mặc định.

Banner xuất hiện đầu trang, có ảnh logo nguyên bản, nhãn Liên kết tài trợ và mở
Vbee trong tab mới khi bấm. Giữ nguyên affiliate parameter. CTA sau khi xử lý thành
công vẫn còn. `VBEE_CTA_ENABLED=false` ẩn cả banner và CTA.

Không thay đổi secrets, requirements hay chi phí hosting. Ảnh trang nguồn trong
khung Chromium vẫn có màu theo website nguồn; thanh điều khiển theo theme của tool.
