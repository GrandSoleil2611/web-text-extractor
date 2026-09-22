# Web Text Extractor — lấy và làm sạch văn bản web

Ứng dụng Python/Streamlit miễn phí cho người dùng: nhập URL, lấy nội dung bằng
Requests hoặc Chromium/Playwright, giữ Raw Text, làm sạch văn bản và tải TXT/Markdown.

### Tìm và thay thế

Sau khi lấy nội dung, mở **🔎 Tìm và thay thế**, chọn Clean Text / Raw Text / Markdown,
nhập nội dung tìm và nội dung thay thế rồi bấm **Thay thế tất cả**. Có đếm kết quả,
phân biệt hoa/thường, khớp nguyên từ và hoàn tác một lần thay thế cho từng bản.
Để ô thay thế trống để xóa; ký tự được hiểu nguyên văn, không phải regex.
Có thể sửa trực tiếp trong ô văn bản; file tải xuống dùng bản đã chỉnh sửa.
Bản crawl gốc vẫn giữ trong phiên. Crawl mới đặt lại các bản chỉnh sửa và lịch sử hoàn tác.
Kiểm thử tính năng: `python -X utf8 -m unittest -v test_text_editor`.

**Chưa xuất bản public.** Repo đã có cấu hình để triển khai; cần tài khoản GitHub
và tài khoản hosting của chủ ứng dụng. Không upload nguyên thư mục làm việc:
profile Chromium hiện có chứa trạng thái đăng nhập/cookie và phải giữ riêng.

## A. Kiến trúc và kết quả kiểm tra source

- `app.py`: entry point Streamlit, giao diện nhập URL, chế độ crawl, blacklist,
  kết quả và download. Giữ đủ Auto / Requests / Playwright, Raw / Clean / Markdown.
- `scraper.py`: Requests + BeautifulSoup/lxml cho HTML; Playwright Chromium cho
  trang JavaScript; MonkeyD luôn đi qua Chromium và bộ trích xuất vùng chương.
- `cleaner.py`: lọc blacklist/emoji, phục hồi từ bị chèn dấu, xử lý ngoặc và gộp dòng.
  Thuật toán làm sạch giữ nguyên; chỉ bổ sung nguồn blacklist theo từng phiên.
- `job_runner.py` → `crawl_worker.py`: mỗi lượt xử lý chạy trong process riêng;
  UI không chạy browser trực tiếp trên thread Streamlit.
- `network_guard.py`: proxy riêng cho mỗi lượt crawl public, kiểm tra IP đích và
  kết nối tới đúng IP đã kiểm tra, dùng cho Requests và Chromium.
- `settings.py`, `affiliate.py`: cấu hình runtime và CTA độc lập.
- `self_test.py`: các test gốc; `test_public.py`, `test_browser_ui.py`: test bổ sung.

Không dùng Selenium. Source Python gốc không hard-code đường dẫn Chrome Windows;
Playwright quản lý browser riêng. `install.bat` / `run.bat` là script Windows, không
dùng trên cloud. Dependencies Python có bản Linux. `.venv` cũ trên máy hiện tại
tham chiếu Python Windows không còn tồn tại; đây là vấn đề môi trường local,
không phải dependency source. Môi trường kiểm thử riêng không nằm trong repo deploy.

## B. Chromium: local và server

| Trường hợp | Trước đây | Sau thay đổi |
|---|---|---|
| Trang thường cần JavaScript | Chromium headless | Giữ Chromium headless |
| MonkeyD trên Windows local | Cửa sổ Chromium, profile persistent, chờ thao tác tối đa 5 phút | Giữ luồng này |
| MonkeyD trên server Linux | Cố mở cửa sổ GUI | Chromium headless, context riêng, không dùng profile chung |
| MonkeyD bị khóa và yêu cầu người dùng thao tác | Người dùng thao tác trong cửa sổ local | Thông báo giới hạn; không trả nội dung khóa thành kết quả thành công |

**Headless không thay thế được thao tác mở khóa thủ công.** Streamlit Community
Cloud và Render không tự đưa cửa sổ Chromium trên server tới trình duyệt người dùng.
Do đó không thể khẳng định giữ 100% hành vi tương tác MonkeyD trên một app headless.
Không có tự click Shopee, giả cookie/storage hay fallback MonkeyD sang Requests/body.

Nếu bắt buộc người dùng public thao tác trực tiếp trong Chromium của server, cần
một hệ thống trình duyệt từ xa theo từng phiên (ví dụ VPS/container có màn hình ảo
và noVNC được xác thực). Đây là kiến trúc khác, chưa được triển khai trong project
này, không đáp ứng yêu cầu “không GUI” theo nghĩa tuyệt đối và không thể hứa miễn
phí ổn định. Chuyển riêng sang Render không giải quyết được giới hạn tương tác đó.

## C–D. File và thay đổi

Sửa `app.py`, `scraper.py`, `cleaner.py`, `requirements.txt`.
Thêm `settings.py`, `affiliate.py`, `job_runner.py`, `crawl_worker.py`,
`network_guard.py`, `packages.txt`, `.streamlit/config.toml`, `.env.example`,
`.gitignore`, `.dockerignore`, `Dockerfile`, `render.yaml`, `README.md`,
`test_public.py`, `test_browser_ui.py`, `TEST_REPORT.md`.
`blacklist.txt`, `self_test.py`, các script BAT và `README.txt` gốc được giữ lại;
README.md này là hướng dẫn deploy mới.

- Public: Linux mặc định headless; context/cookie không dùng chung giữa khách.
- Local: MonkeyD vẫn dùng profile cũ; không upload profile này lên hosting.
- Một job crawl tại một thời điểm trên mỗi process ứng dụng; job mới khi bận nhận
  thông báo. Giới hạn public 90 giây cho toàn lượt Auto, kể cả fallback.
- Request có timeout 20 giây; browser launch 30 giây, navigation 35 giây,
  thao tác mặc định 10 giây. Worker bị dừng cả cây process khi quá hạn.
- HTML Requests tối đa 5 MiB; kết quả tối đa 2 triệu ký tự / root HTML 5 MiB.
- Public chỉ kết nối đích public qua cổng 80/443; proxy chặn IP private/local,
  bao gồm chuyển hướng và subresource. WebSocket/service worker/download bị tắt
  trong browser public. Trang phụ thuộc các tính năng đó có thể không hoạt động.
- Blacklist public lưu riêng trong session, không sửa file chung. Kết quả không
  được ghi database/file; không log toàn bộ URL hoặc nội dung người dùng.
- UI bắt lỗi, có hướng dẫn/title/icon/mô tả/footer, không nhồi từ khóa.
- Vbee ON sau khi có kết quả, mở tab mới qua thao tác người dùng, có nhãn
  “Liên kết tài trợ”. Không gửi nội dung văn bản sang Vbee tự động.
- Shopee OFF cho tới khi cấu hình URL thật.

## E–F. Chọn hosting

**Ưu tiên thử Streamlit Community Cloud trước**, miễn phí, đúng kiến trúc Streamlit:
`requirements.txt` cài Python packages; `packages.txt` cài Debian Chromium và font.
Code tự tìm `chromium` trên PATH, không cần Chrome Windows hoặc tải browser lúc
mỗi người dùng bấm Convert. Tuy nhiên Chromium hệ thống không được Playwright
bảo đảm tương thích tuyệt đối như bản browser đi kèm: cần smoke test sau deploy.

**Render Docker là phương án dự phòng** nếu Chromium hệ thống không tương thích:
Dockerfile cài Chromium bằng `python -m playwright install --with-deps chromium`,
đồng bộ với phiên bản Playwright đã pin. Render Free có RAM 512 MB và ngủ sau
15 phút không có truy cập; Chromium có thể hết RAM trên trang nặng. Không tự nâng
lên gói trả phí. Render phù hợp hơn về kiểm soát môi trường, không phải lời hứa
giải quyết MonkeyD bị khóa thủ công hoặc đủ tài nguyên cho nhiều người dùng.

Nguồn chính thức:
- [Streamlit dependencies và packages.txt](https://docs.streamlit.io/deploy/concepts/dependencies)
- [Deploy Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
- [Playwright browsers](https://playwright.dev/python/docs/browsers)
- [Playwright executable_path: lưu ý tương thích](https://playwright.dev/python/docs/api/class-browsertype)
- [Render Free](https://render.com/docs/free), [compute plans](https://render.com/docs/compute-plans)

## G. Các bước deploy chính xác

### Streamlit Community Cloud

1. Tạo repository GitHub cho project. Upload source/cấu hình nêu ở C–D cùng
   `blacklist.txt`; loại `.venv*`, `.tools`, `.browser-cache`,
   `.monkeyd_browser_profile`, `__pycache__`, secrets và ảnh test.
   Nếu dùng Git, `.gitignore` đã có sẵn; kiểm tra danh sách staged trước khi commit.
2. Truy cập https://share.streamlit.io, đăng nhập và kết nối GitHub.
3. Chọn **Create app**, repository vừa tạo, branch chứa code, main file **app.py**.
4. Trong Advanced settings, chọn **Python 3.12**. Điền secrets bên dưới (không
   commit `.streamlit/secrets.toml`). Chọn subdomain còn trống rồi Deploy.
5. Đợi cài requirements và packages. Kiểm tra log nếu lỗi apt/pip/browser; không
   bỏ Playwright để làm deployment xanh giả tạo.
6. Trên URL `https://<tên-đã-chọn>.streamlit.app`, thử `https://example.com` với
   Requests và Playwright; thử một chương MonkeyD mà bạn có quyền truy cập;
   kiểm tra Raw/Clean/download và link Vbee. Test trang bị khóa phải báo đúng giới hạn.
7. Nếu lỗi launch Chromium hệ thống hoặc thiếu tài nguyên kéo dài, dùng Render
   Docker bên dưới. Chưa xác nhận deployment Cloud cho tới khi smoke test này qua.

Secrets đề xuất (giá trị chuỗi ở cấp gốc được Streamlit đưa vào environment):

```toml
PUBLIC_DEPLOYMENT = "true"
BROWSER_HEADLESS = "true"
VBEE_CTA_ENABLED = "true"
SHOPEE_AFFILIATE_URL = ""
```

### Render Docker

1. Đẩy cùng source lên GitHub. Trong Render chọn **New → Blueprint**, kết nối repo
   có `render.yaml`, kiểm tra plan **Free** trước khi tạo.
2. Blueprint dùng Dockerfile tại root, health check `/_stcore/health` và các biến
   public/headless đã khai báo. Không cần build/start command bổ sung.
3. Đợi Docker build hoàn tất. Browser cùng thư viện Linux được cài lúc build;
   ứng dụng chạy bằng user không phải root và nghe cổng `$PORT` do Render cấp.
4. Mở URL `https://<tên-dịch-vụ>.onrender.com` Render trả về và chạy smoke test như trên.
5. Nếu hết RAM, giảm tải hoặc cân nhắc gói trả phí do bạn quyết định. Gói free
   không có cam kết uptime hay đáp ứng tải lớn.

Tên miền đi kèm hai nền tảng là **tên miền phụ miễn phí**, không phải quyền sở hữu
một tên miền `.com`/`.vn` miễn phí. Chưa đăng ký tên miền hoặc tạo dịch vụ thay bạn.

### Local / Linux tự quản

Windows: cài Python 3.12, chạy `install.bat`, rồi `run.bat`. Nếu `.venv` cũ bị hỏng,
đổi tên nó để giữ bản dự phòng rồi chạy installer tạo lại; không copy `.venv` giữa máy.

Linux có quyền cài system dependencies:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m playwright install --with-deps chromium
export PUBLIC_DEPLOYMENT=true
python -m streamlit run app.py --server.address=0.0.0.0
```

## H. Environment / secrets

Không cần API key, Vbee secret hay tài khoản Shopee để chạy ứng dụng.
Affiliate URL không phải secret và được giữ chính xác:

`https://vbee.vn/?aff=a915a4fe-8d92-40ce-97a4-47bca84ec1da`

| Biến | Mặc định / cách dùng |
|---|---|
| `PUBLIC_DEPLOYMENT` | `true` trên Linux, `false` trên Windows; public hosting luôn đặt `true` |
| `BROWSER_HEADLESS` | Public luôn ép `true`; đặt `true` khi muốn test headless trên Windows |
| `VBEE_CTA_ENABLED` | `true`; đặt `false` để ẩn CTA |
| `SHOPEE_AFFILIATE_URL` | Rỗng = OFF; đặt URL affiliate HTTPS thật khi được duyệt |
| `CHROMIUM_EXECUTABLE_PATH` | Rỗng = tự tìm Chromium Linux hoặc browser Playwright; thường không cần đặt |
| `PLAYWRIGHT_BROWSERS_PATH` | Docker đặt `/opt/playwright`; không cần đặt trên Community Cloud |
| `PORT` | Render tự cấp; Docker mặc định 8501 |

`.env.example` chỉ là tài liệu; app không tự đọc `.env`. Dùng environment thực hoặc
Streamlit secrets. Không tắt `PUBLIC_DEPLOYMENT` để xử lý lỗi trên hosting public.

## Kiểm thử

```bash
python -X utf8 self_test.py
python -X utf8 -m unittest -v test_public
# Terminal khác sau khi chạy app ở 127.0.0.1:8501:
python -X utf8 test_browser_ui.py
```

`test_public.py` dùng Chromium thật với HTML fixture bị chặn mạng; không tạo click
quảng cáo. `test_browser_ui.py` crawl example.com thật và chặn navigation Vbee
bằng trang fixture để kiểm tra URL/tab mới mà không phát sinh click affiliate thật.
Xem `TEST_REPORT.md` để phân biệt kết quả đã test và phần chưa được xác nhận.

## I. Rủi ro và giới hạn còn lại

- Chưa có URL chương MonkeyD live cụ thể trong project; fixture không chứng minh
  trang thật sẽ bỏ chặn IP datacenter hoặc cho phép headless.
- MonkeyD cần mở khóa thủ công không được hỗ trợ từ xa bằng cấu hình headless này;
  local vẫn giữ luồng cũ. Không quảng bá là hỗ trợ đầy đủ mọi chương sau deploy.
- Timeout/giới hạn kết quả không phải quota RAM cứng; một trang có JavaScript rất
  nặng vẫn có thể làm container hết RAM trước khi timeout. Chromium chạy trong
  container cần được cập nhật bảo mật định kỳ; không coi URL filtering là sandbox OS.
- Proxy bảo vệ kết nối mạng tiêu chuẩn, không phải chứng nhận chống mọi lỗ hổng
  Chromium. Không cấu hình credential nội bộ nhạy cảm trong worker crawl.
- Một job đồng thời và cooldown session là giới hạn cơ bản, không chống được tấn
  công phân tán. Nếu tăng lưu lượng, cần rate limit ở gateway và tài nguyên phù hợp.
- Cloud có thể sleep, restart, đổi package hệ thống hoặc chặn website nguồn;
  nội dung/blacklist trong session mất khi session kết thúc hoặc server khởi động lại.
- UI title/mô tả/hướng dẫn là SEO cơ bản; không cam kết top Google. Streamlit có
  hạn chế kiểm soát HTML metadata/SSR; landing page riêng là bước khác nếu cần SEO sâu.
- Chỉ xử lý nội dung được phép sử dụng; CTA Vbee không cấp quyền đối với văn bản nguồn.
