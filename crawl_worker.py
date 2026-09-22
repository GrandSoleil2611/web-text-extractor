"""Private worker entry point. Do not print URLs, page text, or raw exceptions."""
import contextlib
import io
import json
import sys

from cleaner import blacklist_override
from scraper import scrape, scrape_auto, manual_unlock_handler


def main():
    interactive = "--interactive" in sys.argv
    payload = json.loads(sys.stdin.readline()) if interactive else json.load(sys.stdin)
    bridge = None
    handler_token = None
    if interactive:
        from remote_browser import BrowserBridge
        bridge = BrowserBridge(sys.stdout)
        handler_token = manual_unlock_handler.set(bridge.handle_unlock)
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
        if handler_token is not None:
            manual_unlock_handler.reset(handler_token)
    if bridge:
        bridge.publish({"type": "error" if "error" in response else "result", **response})
    else:
        sys.stdout.write(json.dumps(response, ensure_ascii=True))


if __name__ == "__main__":
    main()
