WEB TEXT EXTRACTOR - FINAL
==========================

1) Chạy install.bat một lần.
2) Chạy run.bat.
3) Dán URL và bấm Convert.

MONKEYD / MONKEYDD
------------------
- Tool KHÔNG fallback sang toàn bộ body.
- Chỉ lấy vùng chương (.chapter-content ưu tiên), rồi cắt nội dung trước phần điều hướng/comment/report.
- Giữ text trong p/span/i/em/b/strong và text node; xử lý whitespace/zero-width.
- Nếu trang yêu cầu thao tác Shopee, Chromium có giao diện sẽ mở.
  Bạn tự thực hiện thao tác của website. Tool không tự click và không inject localStorage/cookie giả.
  Sau khi nội dung chương xuất hiện, tool tự extract và đóng Chromium.
- Browser profile hợp lệ được lưu ở .monkeyd_browser_profile để giữ cookie/localStorage do website/browser tạo.

CLEAN TEXT
----------
- Lọc blacklist quảng cáo/lời chào.
- Lọc dòng emoji rác.
- c.h.ế.t -> chết; d.ư.ợ.c -> dược; b.ắ.n -> bắn...
- 【Nội dung】 -> Nội dung (chỉ xóa hai ký tự 【 】, không thêm dấu ngoặc kép).
- Xuống dòng được gộp thành 1 khoảng trắng, tránh lỗi chàng.Để / mình.Chàng.

RAW TEXT
--------
Raw Text luôn là dữ liệu trước blacklist/restore/join. Nếu Raw thiếu chữ thì không nên dùng Clean Text.
