"""User-driven screenshot/click bridge, executed inside the isolated worker."""
import base64
import json
import math
import queue
import secrets
import sys
import threading
import time
from urllib.parse import urlsplit


class BrowserBridge:
    def __init__(self, output):
        self.output = output
        self.commands = queue.Queue(maxsize=8)
        self.last_id = None
        self.last_frame = None
        self.ack = None
        self.notice = ""
        threading.Thread(target=self._read_commands, daemon=True).start()

    def publish(self, state):
        self.output.write(json.dumps(state, ensure_ascii=False) + "\n")
        self.output.flush()

    def _read_commands(self):
        while True:
            line = sys.stdin.readline(2049)
            if not line:
                return
            if len(line) > 2048 or not line.endswith("\n"):
                return
            try:
                command = json.loads(line)
                if isinstance(command, dict):
                    self.commands.put_nowait(command)
            except (ValueError, queue.Full):
                continue

    def handle_unlock(self, context, story, url):
        from scraper import _monkeyd_has_real_content, is_special_host

        active = story
        popup_queue = []
        previous_image = None
        frame = None

        def on_popup(page):
            if len(context.pages) > 4:
                page.close()
            else:
                popup_queue.append(page)

        context.on("page", on_popup)
        deadline = time.monotonic() + 210
        try:
            while time.monotonic() < deadline:
                pages = [p for p in context.pages if not p.is_closed()]
                if story.is_closed() or not pages:
                    raise RuntimeError("MonkeyD: trang truyện đã đóng. Hãy thử lại.")
                if popup_queue:
                    active = popup_queue[-1]
                    popup_queue.clear()
                if active.is_closed():
                    active = story
                try:
                    screenshot = active.screenshot(type="jpeg", quality=65, timeout=5000)
                except Exception:
                    active = story
                    screenshot = story.screenshot(type="jpeg", quality=65, timeout=5000)
                    self.notice = "Tab phụ đang chuyển trang. Đã quay về trang truyện."
                signature = (screenshot, active, tuple(pages), active.url)
                if signature != previous_image:
                    frame = secrets.token_hex(8)
                    previous_image = signature
                tabs = []
                for index, page in enumerate(pages):
                    host = urlsplit(page.url).hostname or "Đang mở trang"
                    tabs.append({"index": index, "label": ("Truyện · " if page == story else "Tab · ") + host})
                ready = is_special_host(urlsplit(story.url).hostname or "") and _monkeyd_has_real_content(story)
                self.last_frame = frame
                self.publish({"type": "browser", "frame": frame,
                              "image": base64.b64encode(screenshot).decode("ascii"),
                              "tabs": tabs, "active": pages.index(active),
                              "ready": ready, "ack": self.ack, "notice": self.notice,
                              "seconds_left": max(0, int(deadline - time.monotonic()))})
                self.notice = ""
                # Pump Playwright events while waiting for input. No action is
                # generated automatically: a command must come from the viewer.
                until = time.monotonic() + 2
                command = None
                while time.monotonic() < until:
                    try:
                        command = self.commands.get_nowait()
                        break
                    except queue.Empty:
                        story.wait_for_timeout(100)
                if command is None:
                    continue
                identity = command.get("id")
                if not isinstance(identity, str) or identity == self.last_id:
                    continue
                self.last_id = identity
                self.ack = identity
                action = command.get("action")
                # A pointer click must refer to the exact image currently shown.
                # Reject stale images instead of clicking a different target.
                if action in {"click", "tab"} and command.get("frame") != self.last_frame:
                    self.notice = "Ảnh vừa cập nhật. Hãy bấm lại trên ảnh mới."
                    continue
                try:
                    if action == "click":
                        x, y = command.get("x"), command.get("y")
                        viewport = active.viewport_size or {"width": 1365, "height": 900}
                        if all(isinstance(v, (int, float)) and math.isfinite(v) for v in (x, y)) and 0 <= x < viewport["width"] and 0 <= y < viewport["height"]:
                            active.mouse.click(x, y)
                    elif action in {"up", "down"}:
                        active.mouse.wheel(0, -550 if action == "up" else 550)
                    elif action == "story":
                        active = story
                        active.bring_to_front()
                    elif action == "tab":
                        index = command.get("tab")
                        if isinstance(index, int) and 0 <= index < len(pages):
                            active = pages[index]
                            active.bring_to_front()
                    elif action == "close_tab" and active != story:
                        active.close()
                        active = story
                    elif action == "reload":
                        active.reload(wait_until="domcontentloaded", timeout=15000)
                    elif action == "finish":
                        if is_special_host(urlsplit(story.url).hostname or "") and _monkeyd_has_real_content(story):
                            return
                        self.notice = "Trang truyện chưa hiện nội dung. Hãy hoàn tất yêu cầu trên trang rồi thử lại."
                    story.wait_for_timeout(500)
                except Exception:
                    self.notice = "Trang chưa phản hồi thao tác. Hãy thử cập nhật hoặc quay về trang truyện."
        finally:
            context.remove_listener("page", on_popup)
        raise RuntimeError("MonkeyD: hết thời gian thao tác. Hãy bấm Convert để mở phiên mới.")
