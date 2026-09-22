"""Deployment settings. Never store credentials or visitor browser state here."""
import os
import shutil
import sys


def flag(name, default=False):
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


PUBLIC_DEPLOYMENT = flag("PUBLIC_DEPLOYMENT", sys.platform.startswith("linux"))
BROWSER_HEADLESS = PUBLIC_DEPLOYMENT or flag("BROWSER_HEADLESS", False)
REQUEST_TIMEOUT_SECONDS = 20
JOB_TIMEOUT_SECONDS = 90 if PUBLIC_DEPLOYMENT else 420
MAX_HTML_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 2_000_000
VBEE_AFFILIATE_URL = "https://vbee.vn/?aff=a915a4fe-8d92-40ce-97a4-47bca84ec1da"
VBEE_CTA_ENABLED = flag("VBEE_CTA_ENABLED", True)
SHOPEE_AFFILIATE_URL = os.getenv("SHOPEE_AFFILIATE_URL", "").strip()


def browser_launch_options(headless=True):
    options = {"headless": headless, "timeout": 30000}
    executable = os.getenv("CHROMIUM_EXECUTABLE_PATH", "").strip()
    # Community Cloud installs Debian Chromium from packages.txt. Docker uses
    # the Chromium revision installed by the pinned Playwright package.
    if not executable and sys.platform.startswith("linux"):
        executable = shutil.which("chromium") or ""
    if executable:
        options["executable_path"] = executable
    if sys.platform.startswith("linux"):
        options["args"] = ["--disable-dev-shm-usage"]
    return options
