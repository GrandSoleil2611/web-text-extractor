"""Optional live smoke test. Start Streamlit on 127.0.0.1:8501 first.

Uses example.com as a real network test; blocks affiliate navigation so no
advertising click is sent to Vbee during automated verification.
"""
from pathlib import Path
import re
import os
from playwright.sync_api import sync_playwright
from settings import VBEE_AFFILIATE_URL


def main():
    output = Path("test-artifacts")
    output.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 1100})
            context.route("https://vbee.vn/**", lambda route: route.fulfill(
                status=200, content_type="text/html", body="Affiliate navigation test"))
            page = context.new_page()
            page.goto(os.getenv("STREAMLIT_TEST_URL", "http://127.0.0.1:8501"))
            page.get_by_role("button", name="Convert", exact=True).click()
            page.get_by_text("Bạn hãy nhập URL trước.", exact=True).wait_for()
            page.get_by_role("textbox", name="URL", exact=True).fill("https://example.com")
            page.get_by_text("Requests", exact=True).click()
            page.get_by_role("button", name="Convert", exact=True).click()
            link = page.get_by_role("link", name="🎙️ Thử Vbee AIVoice →")
            link.wait_for(timeout=100000)
            assert link.get_attribute("href") == VBEE_AFFILIATE_URL
            assert link.get_attribute("target") == "_blank"
            with page.expect_popup() as popup_info:
                link.click()
            popup = popup_info.value
            popup.wait_for_load_state()
            assert popup.url == VBEE_AFFILIATE_URL
            popup.close()
            page.screenshot(path=str(output / "desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            link.scroll_into_view_if_needed()
            page.screenshot(path=str(output / "mobile.png"), full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Horizontal overflow"
            # The same live app must also support the explicit Chromium mode.
            page.wait_for_timeout(10000)  # public per-session cooldown
            page.get_by_text("Playwright", exact=True).click()
            page.get_by_role("button", name="Convert", exact=True).click()
            page.get_by_text("Đã xử lý xong.", exact=True).wait_for(timeout=100000)
            page.get_by_text(re.compile(r"Nguồn: Playwright rendered DOM")).wait_for(timeout=10000)
            print("LIVE UI PASSED: Requests, Playwright, Vbee new tab, 1440px/390px")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
