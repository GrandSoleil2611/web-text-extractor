"""Private worker entry point. Do not print URLs, page text, or raw exceptions."""
import contextlib
import io
import json
import sys

from cleaner import blacklist_override
from scraper import scrape, scrape_auto


def main():
    payload = json.load(sys.stdin)
    token = blacklist_override.set(payload.get("blacklist"))
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            if payload["mode"] == "Auto":
                result = scrape_auto(payload["url"], payload["audio_clean"])
            else:
                result = scrape(payload["url"], payload["mode"] == "Playwright", payload["audio_clean"])
        response = {"result": result}
    except Exception as exc:
        message = str(exc)
        if message.startswith("MonkeyD:") or isinstance(exc, ValueError):
            # Only our short validation messages, never upstream response bodies.
            message = message if len(message) < 400 else "Dữ liệu trang không hợp lệ."
        else:
            message = "Không thể lấy nội dung. Trang có thể chặn truy cập, quá thời gian hoặc Chromium chưa sẵn sàng. Hãy thử lại hoặc dùng URL khác."
        response = {"error": message}
    finally:
        blacklist_override.reset(token)
    sys.stdout.write(json.dumps(response, ensure_ascii=True))


if __name__ == "__main__":
    main()
