"""One isolated crawl at a time; input/output stay in pipes, never temp files."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading

import psutil

from settings import JOB_TIMEOUT_SECONDS

_SLOT = threading.BoundedSemaphore(1)


def _stop_process_tree(process):
    if os.name != "nt":
        # The worker owns its own session. Kill only that process group, including
        # orphaned Chromium children after a timeout or a crashed driver.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        try:
            parent = psutil.Process(process.pid)
            children = parent.children(recursive=True)
            for child in reversed(children):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            parent.kill()
            psutil.wait_procs(children, timeout=5)
        except psutil.NoSuchProcess:
            pass
    process.wait(timeout=10)


def run_crawl(url, mode, audio_clean, blacklist):
    if not _SLOT.acquire(blocking=False):
        raise RuntimeError("Máy chủ đang xử lý một yêu cầu khác. Vui lòng thử lại sau.")
    process = None
    try:
        process = subprocess.Popen(
            [sys.executable, "-X", "utf8", str(Path(__file__).with_name("crawl_worker.py"))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        payload = json.dumps(dict(url=url, mode=mode, audio_clean=audio_clean,
                                  blacklist=blacklist), ensure_ascii=False)
        try:
            stdout, _ = process.communicate(payload, timeout=JOB_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            raise RuntimeError("Trang xử lý quá lâu. Đã dừng yêu cầu và đóng Chromium; hãy thử lại.") from None
        if process.returncode:
            raise RuntimeError("Không thể hoàn tất xử lý. Hãy thử trang khác hoặc thử lại sau.")
        response = json.loads(stdout)
        if "error" in response:
            raise RuntimeError(response["error"])
        return response["result"]
    finally:
        try:
            if process is not None:
                _stop_process_tree(process)
        finally:
            _SLOT.release()
