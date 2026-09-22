"""Session-owned browser worker. JSON-lines IPC only; no cookie/screenshot files."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

from job_runner import _SLOT, _stop_process_tree

REMOTE_LIFETIME_SECONDS = 240
REMOTE_IDLE_SECONDS = 45
MAX_MESSAGE = 16 * 1024 * 1024


class RemoteJob:
    def __init__(self, url, audio_clean, blacklist):
        if not _SLOT.acquire(blocking=False):
            raise RuntimeError("Máy chủ đang xử lý yêu cầu khác. Vui lòng thử lại sau.")
        self._lock = threading.Lock()
        self.identity = uuid.uuid4().hex
        self._write_lock = threading.Lock()
        self._cancelled = threading.Event()
        self.done = threading.Event()
        self._state = {"type": "loading"}
        self._last_seen = time.monotonic()
        self._last_action = None
        self._started = time.monotonic()
        self.process = None
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-X", "utf8", str(Path(__file__).with_name("crawl_worker.py")), "--interactive"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8", bufsize=1,
                start_new_session=os.name != "nt",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            self.process.stdin.write(json.dumps(dict(url=url, mode="Playwright", audio_clean=audio_clean, blacklist=blacklist)) + "\n")
            self.process.stdin.flush()
            self.reader = threading.Thread(target=self._read, daemon=True)
            self.reader.start()
            threading.Thread(target=self._supervise, daemon=True).start()
        except Exception:
            if self.process is not None:
                _stop_process_tree(self.process)
            _SLOT.release()
            raise

    def _read(self):
        try:
            while True:
                line = self.process.stdout.readline(MAX_MESSAGE + 1)
                if not line:
                    break
                if len(line) > MAX_MESSAGE or not line.endswith("\n"):
                    self._cancelled.set()
                    break
                state = json.loads(line)
                if state.get("type") not in {"browser", "result", "error"}:
                    continue
                with self._lock:
                    self._state = state
        except (OSError, ValueError):
            self._cancelled.set()

    def _supervise(self):
        reason = "Phiên Chromium đã kết thúc. Hãy bấm Convert để thử lại."
        try:
            while self.process.poll() is None:
                now = time.monotonic()
                if self._cancelled.wait(0.25):
                    reason = "Đã đóng phiên Chromium."
                    break
                if now - self._started > REMOTE_LIFETIME_SECONDS:
                    reason = "Phiên Chromium hết thời gian 4 phút. Hãy thử lại."
                    break
                if now - self._last_seen > REMOTE_IDLE_SECONDS:
                    reason = "Đã đóng Chromium vì phiên sử dụng không còn kết nối."
                    break
        finally:
            try:
                _stop_process_tree(self.process)
                # Let the reader consume the final result before marking done.
                self.reader.join(timeout=3)
                for pipe in (self.process.stdin, self.process.stdout):
                    if pipe:
                        pipe.close()
            finally:
                with self._lock:
                    if self._state.get("type") not in {"result", "error"}:
                        self._state = {"type": "error", "error": reason}
                _SLOT.release()
                self.done.set()

    def snapshot(self):
        self._last_seen = time.monotonic()
        with self._lock:
            return dict(self._state)

    def send(self, command):
        if not isinstance(command, dict) or self.done.is_set() or self._cancelled.is_set():
            return
        identity = command.get("id")
        if not isinstance(identity, str) or len(identity) > 100:
            return
        with self._write_lock:
            if identity == self._last_action:
                return
            data = json.dumps(command)
            if len(data) > 2048:
                return
            try:
                self.process.stdin.write(data + "\n")
                self.process.stdin.flush()
                self._last_action = identity
            except (BrokenPipeError, OSError, ValueError):
                pass

    def cancel(self):
        self._cancelled.set()
