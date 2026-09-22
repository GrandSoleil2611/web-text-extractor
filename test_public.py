"""Offline regression tests, including real Chromium with intercepted fixture URLs.

Run: python -X utf8 -m unittest -v test_public
"""
import os
os.environ["BROWSER_HEADLESS"] = "true"

import subprocess
import sys
import time
from pathlib import Path
import unittest
from unittest.mock import patch

import psutil
import requests
import socket
from streamlit.testing.v1 import AppTest

import job_runner
import scraper
import network_guard
from cleaner import blacklist_override, clean_story_text
from settings import VBEE_AFFILIATE_URL, browser_launch_options

STORY = "Khi gả cho phu quân vừa yếu đuối lại xinh đẹp, chàng là một đại phu. " * 6
GENERAL = '<html><title>JavaScript fixture</title><body><main id="story"></main><script>document.querySelector("main").textContent = ' + repr(STORY) + ';</script></body></html>'
MONKEY = '<html><body><nav>Trang chủ</nav><h1>Chương 12</h1><div class="chapter-content"><p>' + STORY + '</p><div class="pagination">Chương sau</div><p>DO NOT INCLUDE</p></div></body></html>'
LOCKED = '<html><body>MỞ ỨNG DỤNG SHOPEE<div class="chapter-content">' + STORY + '</div></body></html>'
RESULT = dict(title="Chương thử", raw_text=STORY, text=STORY, markdown=STORY,
              clean_stats={}, source_mode="Fixture")


class ValidationTests(unittest.TestCase):
    def test_proxy_rejects_nonpublic_destinations(self):
        for host in ("127.0.0.1", "169.254.169.254", "::1"):
            with self.subTest(host=host), self.assertRaises(ValueError):
                network_guard.connect_public(host, 80)

    def test_proxy_pins_resolved_address(self):
        with patch("network_guard.socket.getaddrinfo", return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
        ]), patch("network_guard.socket.socket") as factory:
            network_guard.connect_public("fixture.example", 443)
            factory.return_value.connect.assert_called_once_with(("8.8.8.8", 443))

    def test_private_addresses(self):
        for url in ("http://localhost", "http://127.0.0.1", "http://169.254.169.254", "http://[::1]", "http://0.0.0.0", "https://user:pass@example.com"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                scraper.validate_url(url)

    def test_blacklist_isolation(self):
        token = blacklist_override.set("unique phrase")
        try:
            self.assertEqual(clean_story_text("unique phrase\nKeep this")[0], "Keep this")
        finally:
            blacklist_override.reset(token)
        self.assertIn("unique phrase", clean_story_text("unique phrase")[0])

    def test_redirect_to_private(self):
        response = requests.Response()
        response.status_code = 302
        response.headers["Location"] = "http://127.0.0.1/secret"
        response._content = b""
        response._content_consumed = True
        with patch.object(requests.Session, "get", return_value=response):
            with self.assertRaises(ValueError):
                scraper.fetch_with_requests("https://8.8.8.8/")

    def test_linux_launch_options(self):
        with patch("settings.sys.platform", "linux"), patch("settings.shutil.which", return_value="/usr/bin/chromium"):
            options = browser_launch_options()
            self.assertTrue(options["headless"])
            self.assertEqual(options["executable_path"], "/usr/bin/chromium")


class BrowserTests(unittest.TestCase):
    def fetch_fixture(self, html, monkey=False):
        before = {p.pid for p in psutil.Process().children(recursive=True)}
        def setup(context):
            context.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html; charset=utf-8", body=html))
        try:
            with patch.object(scraper, "validate_url", side_effect=lambda value: value), patch.object(scraper, "_configure_context", side_effect=setup):
                return scraper.fetch_with_playwright("https://monkeydd.com/test" if monkey else "https://fixture.example/test")
        finally:
            time.sleep(0.2)
            remaining = [p for p in psutil.Process().children(recursive=True) if p.pid not in before]
            self.assertEqual(remaining, [], "Browser/driver process leaked")

    def test_javascript_rendering(self):
        self.assertIn(STORY.strip(), self.fetch_fixture(GENERAL)["raw_text"])

    def test_monkey_boundary(self):
        result = self.fetch_fixture(MONKEY, True)
        self.assertIn(STORY.strip(), result["raw_text"])
        self.assertNotIn("DO NOT INCLUDE", result["raw_text"])
        self.assertNotIn("Chương sau", result["raw_text"])
        self.assertEqual(result["title"], "Chương 12")
        self.assertFalse(result["diagnostics"]["persistent_profile"])

    def test_monkey_locked(self):
        with self.assertRaisesRegex(RuntimeError, "mở khóa trực tiếp"):
            self.fetch_fixture(LOCKED, True)

    def test_monkey_missing_container(self):
        with self.assertRaisesRegex(RuntimeError, "không xác định"):
            self.fetch_fixture("<html><body>No chapter</body></html>", True)

    def test_context_creation_failure_closes_browser(self):
        with patch.object(scraper, "validate_url", side_effect=lambda value: value), patch.object(scraper, "_configure_context", side_effect=RuntimeError("failure")):
            before = {p.pid for p in psutil.Process().children(recursive=True)}
            with self.assertRaisesRegex(RuntimeError, "failure"):
                scraper.fetch_with_playwright("https://fixture.example")
            self.assertEqual([p for p in psutil.Process().children(recursive=True) if p.pid not in before], [])


class WorkerTests(unittest.TestCase):
    def test_validation_error_is_friendly(self):
        with self.assertRaisesRegex(RuntimeError, "localhost"):
            job_runner.run_crawl("http://localhost", "Requests", True, "")

    def test_busy_slot(self):
        job_runner._SLOT.acquire()
        try:
            with self.assertRaisesRegex(RuntimeError, "yêu cầu khác"):
                job_runner.run_crawl("unused", "Auto", True, "")
        finally:
            job_runner._SLOT.release()

    def test_timeout_kills_real_browser(self):
        real_popen = subprocess.Popen
        created = []
        code = "from playwright.sync_api import sync_playwright; import time; p=sync_playwright().start(); b=p.chromium.launch(headless=True); time.sleep(120)"
        def launch(*args, **kwargs):
            process = real_popen([sys.executable, "-c", code], **kwargs)
            created.append(process)
            return process
        before = {p.pid for p in psutil.Process().children(recursive=True)}
        with patch.object(job_runner.subprocess, "Popen", side_effect=launch), patch.object(job_runner, "JOB_TIMEOUT_SECONDS", 6):
            with self.assertRaisesRegex(RuntimeError, "quá lâu"):
                job_runner.run_crawl("unused", "Auto", True, "")
        self.assertIsNotNone(created[0].poll())
        self.assertEqual([p for p in psutil.Process().children(recursive=True) if p.pid not in before], [])


class UITests(unittest.TestCase):
    def test_public_blacklist_is_session_only(self):
        before = Path("blacklist.txt").read_bytes()
        with patch("settings.PUBLIC_DEPLOYMENT", True):
            first = AppTest.from_file("app.py", default_timeout=20).run()
            first.text_area[0].set_value("my private blacklist")
            next(b for b in first.button if b.label == "💾 Lưu Blacklist").click().run()
            second = AppTest.from_file("app.py", default_timeout=20).run()
        self.assertFalse(first.exception)
        self.assertEqual(first.session_state["blacklist"], "my private blacklist")
        self.assertNotEqual(second.session_state["blacklist"], "my private blacklist")
        self.assertEqual(Path("blacklist.txt").read_bytes(), before)

    def test_empty_url(self):
        app = AppTest.from_file("app.py", default_timeout=20).run()
        next(b for b in app.button if b.label == "Convert").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("nhập URL" in w.value for w in app.warning))

    def test_success_affiliate_and_error(self):
        app = AppTest.from_file("app.py", default_timeout=20).run()
        app.text_input[0].set_value("https://example.com")
        with patch("job_runner.run_crawl", return_value=RESULT):
            next(b for b in app.button if b.label == "Convert").click().run()
        self.assertFalse(app.exception)
        links = app.get("link_button")
        self.assertEqual(len(links), 1)  # Shopee OFF
        self.assertEqual(links[0].proto.url, VBEE_AFFILIATE_URL)
        self.assertEqual(VBEE_AFFILIATE_URL, "https://vbee.vn/?aff=a915a4fe-8d92-40ce-97a4-47bca84ec1da")
        app.session_state["last_crawl"] = 0
        with patch("job_runner.run_crawl", side_effect=RuntimeError("Lỗi kiểm thử")):
            next(b for b in app.button if b.label == "Convert").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("link_button")), 0)
        self.assertTrue(app.error)


if __name__ == "__main__":
    unittest.main()
