# Báo cáo kiểm thử — 22/09/2026

## Bổ sung Find / Replace All

`test_text_editor.py`: 3/3 test PASS trên Windows (Streamlit AppTest và unit test).
Đã kiểm tra thay thế toàn bộ, hoa/thường, nguyên từ, ký tự regex được hiểu nguyên
văn, xóa bằng chuỗi rỗng, giới hạn kích thước, hoàn tác, tách Raw/Clean và đặt lại
khi crawl mới. Giao diện editor dùng session state; nút download đọc cùng nội dung
đã chỉnh sửa. Chưa chạy lại kiểm thử browser desktop/mobile cho riêng panel mới.

## Môi trường

- Windows: Python portable 3.12.10, Streamlit 1.61.1, Playwright 1.62.0,
  Chromium 151.0.7922.34. `.venv` gốc bị hỏng đường dẫn interpreter nên không dùng
  để chạy test; môi trường kiểm thử riêng nằm trong `.tools` và bị loại khỏi deploy.
- Linux: Ubuntu 24.04 WSL, Python 3.12.3, cài mới toàn bộ `requirements.txt`,
  Playwright Chromium Linux cùng revision. Headless được bật; không cần cửa sổ GUI.
- Đây là test Windows và Linux thật, **không phải** một deployment Streamlit Cloud
  hoặc Render. Docker image chưa build do máy không có Docker.

## Kết quả

| Nội dung | Kết quả / phạm vi |
|---|---|
| `self_test.py` gốc | PASS trên Windows: giữ node text, chữ tiếng Việt, lọc blacklist/emoji, phục hồi từ, ngoặc và gộp dòng |
| 16 test đầu trong `test_public.py` | PASS cả Windows public mode và Linux; Linux 16/16 trong 33,766 giây |
| Test bổ sung blacklist hai phiên | PASS Windows và Linux; file blacklist chung giữ nguyên |
| Nhập URL rỗng | Có thông báo, app không crash |
| URL localhost/private/metadata | Bị chặn; kiểm tra cả Requests redirect và proxy egress |
| DNS pinning | Unit test xác nhận socket kết nối đúng địa chỉ IP đã kiểm tra |
| Trang thường `https://example.com` | Requests và Playwright PASS qua worker ở cả Windows public mode và Linux public mode |
| Trang nội dung tạo bằng JavaScript | Chromium thật + fixture HTML: PASS |
| MonkeyD có vùng chương | Chromium thật + fixture: đúng nội dung/heading, dừng trước phân trang |
| MonkeyD bị khóa | Fixture: báo cần thao tác trực tiếp; không trả kết quả giả |
| MonkeyD thiếu container | Fixture: fail closed; không lấy cả body |
| Browser lỗi giữa quá trình | Browser/driver do test tạo được đóng |
| Worker hết thời gian | Test chạy Chromium thật rồi buộc timeout, kiểm tra process được dọn |
| Máy chủ bận | Yêu cầu mới nhận lỗi thân thiện, không tạo crawl đồng thời |
| Vbee | URL giữ nguyên `?aff=a915a4fe-8d92-40ce-97a4-47bca84ec1da`, mở tab mới |
| Shopee | Không có CTA khi URL cấu hình rỗng |
| Giao diện thật | Chạy Streamlit local, thử Requests/Playwright, kiểm tra desktop 1440px và mobile 390px, không tràn ngang |
| Cấu hình public trong UI | Test riêng app với `PUBLIC_DEPLOYMENT=true`, Requests/Playwright và Vbee đều PASS |
| Dependencies | `pip check`: không xung đột ở Windows và Linux |
| Syntax/config | Python compile và đọc TOML thành công |

Test affiliate chặn điều hướng ra Vbee bằng HTML fixture trong browser test;
không gửi click affiliate thật và không xác minh dịch vụ Vbee xử lý mã giới thiệu.
Ảnh đã xem: `test-artifacts/desktop.png`, `test-artifacts/mobile.png`; không đóng gói
ảnh vào source deploy. Cảnh báo `missing ScriptRunContext` của Streamlit AppTest là
cảnh báo trong môi trường test, không phải exception của app.
Test AppTest đặt timeout 20 giây để khởi tạo UI trên filesystem WSL chậm;
lần chạy riêng test blacklist đầu tiên vượt timeout mặc định 3 giây.

## Chưa xác minh / không tuyên bố đã đạt

- Không có URL chương MonkeyD cụ thể trong project; chưa crawl chương live cần
  mở khóa thủ công. Các fixture không chứng minh website thật cho phép IP cloud.
- Chưa test lại thao tác mở khóa bằng tay/profile người dùng trên Windows; source
  luồng này được giữ nguyên, không đọc hoặc sửa cookie/profile riêng của người dùng.
- Chưa xuất bản Community Cloud/Render; chưa xác minh Debian Chromium hệ thống của
  Community Cloud với Playwright đã pin. Docker dùng browser revision đi kèm là
  phương án dự phòng; Dockerfile và render.yaml chưa được nhà cung cấp thực thi.
- Không có load test dài hạn hoặc chứng nhận không bao giờ hết RAM. Test dọn process
  kiểm tra các luồng thành công/lỗi/timeout trong bộ test, không phải mọi lỗi hệ điều hành.
- Chưa kiểm tra index Google, thứ hạng SEO hoặc metadata của URL public vì chưa có URL.

Xem README.md mục G để deploy và chạy smoke test bắt buộc trên hosting thực tế.
