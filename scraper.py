import html as html_lib
from contextvars import ContextVar
import ipaddress
import re
import socket
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlparse, urljoin
from settings import (PUBLIC_DEPLOYMENT, BROWSER_HEADLESS, MAX_HTML_BYTES,
                      MAX_TEXT_CHARS, browser_launch_options)
from network_guard import guarded_network, proxy_url

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

try:
    import html2text
except ImportError:
    html2text = None

from cleaner import clean_story_text

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
}

SPECIAL_DOMAINS = {"monkeydd.com", "monkeyd.vn", "monkeyd.com"}
SPECIAL_ROOT_SELECTORS = [
    # MonkeyD: ưu tiên đúng thân chương trước. Không lấy body.
    ".chapter-content",
    ".content-container .chapter-content",
    ".page-content .chapter-content",
    "#chapter-content",
    ".content-container",
]

BASE_DIR = Path(__file__).resolve().parent
MONKEYD_PROFILE_DIR = BASE_DIR / ".monkeyd_browser_profile"
manual_unlock_handler = ContextVar("manual_unlock_handler", default=None)
MONKEYD_LOCK_MARKERS = (
    "MỞ ỨNG DỤNG SHOPEE",
    "ĐỂ ĐỌC TOÀN BỘ CHƯƠNG TRUYỆN",
    "TIẾP TỤC ỦNG HỘ MONKEYD",
    "ẤN VÀO ĐÂY",
)
GENERAL_CONTENT_SELECTORS = [
    "[itemprop='articleBody']", ".chapter-content", ".entry-content",
    ".article-content", ".post-content", ".story-content", ".reading-content",
    "article", "main", "#content",
]

SKIP_TAGS = {"script", "style", "noscript", "svg", "canvas", "template", "iframe"}
BLOCK_TAGS = {
    "p", "div", "article", "section", "main", "li", "ul", "ol", "blockquote",
    "h1", "h2", "h3", "h4", "h5", "h6", "br", "hr", "tr", "td", "th", "pre",
}
SPACE_CHARS = {
    "\u00a0", "\u1680", "\u2000", "\u2001", "\u2002", "\u2003", "\u2004", "\u2005",
    "\u2006", "\u2007", "\u2008", "\u2009", "\u200a", "\u202f", "\u205f", "\u3000",
}
REMOVE_CHARS = {"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff", "\u00ad"}


def validate_url(url: str) -> str:
    url = url.strip()
    if len(url) > 4096:
        raise ValueError("URL quá dài.")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("URL không hợp lệ.")
    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Không hỗ trợ localhost.")
    try:
        for info in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80)):
            ip = ipaddress.ip_address(info[4][0])
            if not ip.is_global or ip.is_multicast:
                raise ValueError("URL trỏ tới mạng nội bộ/private và đã bị chặn.")
    except socket.gaierror as exc:
        raise ValueError("Không thể phân giải tên miền.") from exc
    return url


def hostname_of(url: str) -> str:
    u = url if url.startswith(("http://", "https://")) else "https://" + url
    return (urlparse(u).hostname or "").lower()


def is_special_host(host: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in SPECIAL_DOMAINS)


def normalize_hidden_chars(text: str) -> str:
    if not text:
        return ""
    text = html_lib.unescape(text)
    for ch in SPACE_CHARS:
        text = text.replace(ch, " ")
    for ch in REMOVE_CHARS:
        text = text.replace(ch, "")
    text = unicodedata.normalize("NFC", text)
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch) not in ("Cc", "Cf"))
    return text


def normalize_extracted_text(text: str) -> str:
    text = normalize_hidden_chars(text).replace("\t", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\S\r\n]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _needs_space(prev: str, nxt: str) -> bool:
    if not prev or not nxt or prev[-1].isspace() or nxt[0].isspace():
        return False
    a, b = prev[-1], nxt[0]
    if b in ",.;:!?%)]}»”’…":
        return False
    if a in "([{«“‘":
        return False
    if a in "-/\\" or b in "-/\\":
        return False
    return a.isalnum() and b.isalnum()


def extract_text_preserve_nodes(element: Tag) -> str:
    pieces: list[str] = []

    def append(value: str):
        value = normalize_hidden_chars(value)
        if not value:
            return
        if pieces and _needs_space(pieces[-1], value):
            pieces.append(" ")
        pieces.append(value)

    def walk(node):
        if isinstance(node, NavigableString):
            append(str(node))
            return
        if not isinstance(node, Tag):
            return
        name = (node.name or "").lower()
        if name in SKIP_TAGS:
            return
        if name == "br":
            pieces.append("\n")
            return
        if name in BLOCK_TAGS:
            pieces.append("\n")
        for child in node.children:
            walk(child)
        if name in BLOCK_TAGS:
            pieces.append("\n")

    walk(element)
    return normalize_extracted_text("".join(pieces))


def find_general_container(soup: BeautifulSoup) -> Tag:
    for selector in GENERAL_CONTENT_SELECTORS:
        matches = soup.select(selector)
        best = None
        best_len = 0
        for el in matches:
            t = extract_text_preserve_nodes(el)
            if len(t) > best_len:
                best, best_len = el, len(t)
        if best is not None and best_len >= 200:
            return best
    return soup.body or soup


def extract_content_from_html(raw_html: str, host: str = "") -> str:
    """Static fallback. MonkeyD normally uses Playwright; this function stays fail-closed."""
    source = normalize_hidden_chars(raw_html or "")
    soup = BeautifulSoup(source, "lxml")
    for tag in soup.find_all(list(SKIP_TAGS)):
        tag.decompose()

    if is_special_host(host):
        # Static fallback only if a real chapter container exists.
        for selector in (".chapter-content", ".content-container .chapter-content"):
            el = soup.select_one(selector)
            if el:
                text = extract_text_preserve_nodes(el)
                if len(text) >= 100:
                    return text
        raise RuntimeError("MonkeyD: không tìm thấy vùng nội dung chương; đã dừng để tránh lấy nhầm toàn bộ trang.")

    return extract_text_preserve_nodes(find_general_container(soup))


@guarded_network
def fetch_with_requests(url: str, timeout: int = 20) -> str:
    url = validate_url(url)
    with requests.Session() as s:
        s.headers.update(DEFAULT_HEADERS)
        s.trust_env = False
        if proxy_url.get():
            s.proxies.update({"http": proxy_url.get(), "https": proxy_url.get()})
        for _ in range(6):
            with s.get(url, timeout=timeout, allow_redirects=False, stream=True) as r:
                if r.is_redirect:
                    url = validate_url(urljoin(url, r.headers["Location"]))
                    continue
                r.raise_for_status()
                if "text/html" not in r.headers.get("Content-Type", "").lower():
                    raise ValueError("URL không trả về trang HTML.")
                chunks, size = [], 0
                for chunk in r.iter_content(65536):
                    size += len(chunk)
                    if size > MAX_HTML_BYTES:
                        raise ValueError("Trang quá lớn; giới hạn HTML là 5 MB.")
                    chunks.append(chunk)
                r._content = b"".join(chunks)
                if r.apparent_encoding:
                    r.encoding = r.apparent_encoding
                return r.text
        raise ValueError("Trang chuyển hướng quá nhiều lần.")


# MonkeyD: lấy đúng vùng SAU heading chương và DỪNG trước phân trang/comment/report.
# Không dùng body fallback. Không chỉ lấy <p>: walker đọc mọi Text node, <i>, <em>, <span>, <b>, <strong>...
MONKEYD_BOUNDARY_EXTRACTOR_JS = r"""
(args) => {
  const ROOT_SELECTORS = args.rootSelectors || [];
  const SKIP = new Set(['SCRIPT','STYLE','NOSCRIPT','SVG','CANVAS','TEMPLATE','IFRAME']);
  const BLOCK = new Set(['P','DIV','ARTICLE','SECTION','MAIN','LI','UL','OL','BLOCKQUOTE','H1','H2','H3','H4','H5','H6','BR','HR','TR','TD','TH','PRE']);
  const STOP_TEXT_RX = /^(?:chương\s+trước|chương\s+sau|xem\s+bình\s+luận|bình\s+luận|báo\s+cáo\s+nội\s+dung|cài\s+đặt|đóng\s+báo\s+cáo|<<|>>)/i;
  const STOP_CLASS_RX = /(pagination|chapter[-_ ]?nav|chapter[-_ ]?navigation|comment|comments|report|setting|modal|advert|ads|share|social|footer)/i;

  function cleanText(s) {
    return (s || '').replace(/[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]/g, ' ')
      .replace(/[\u200b\u200c\u200d\u2060\ufeff\u00ad]/g, '');
  }

  function visible(el) {
    if (!el || el.nodeType !== Node.ELEMENT_NODE) return true;
    const s = getComputedStyle(el);
    return s.display !== 'none' && s.visibility !== 'hidden' && s.visibility !== 'collapse' && Number(s.opacity || '1') !== 0;
  }

  function decodeCssEscapes(v) {
    return v.replace(/\\A\s?/gi, '\n')
      .replace(/\\([0-9a-fA-F]{1,6})\s?/g, (_, h) => {
        try { return String.fromCodePoint(parseInt(h, 16)); } catch { return ''; }
      })
      .replace(/\\(["'\\])/g, '$1');
  }

  function pseudo(el, which) {
    let v = '';
    try { v = getComputedStyle(el, which).content || ''; } catch { return ''; }
    if (!v || v === 'none' || v === 'normal' || v === '""' || v === "''") return '';
    const attrMatch = v.match(/^attr\(([^)]+)\)$/i);
    if (attrMatch) return cleanText(el.getAttribute(attrMatch[1].trim()) || '');
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
    return cleanText(decodeCssEscapes(v));
  }

  function isStopElement(el) {
    if (!el || el.nodeType !== Node.ELEMENT_NODE) return false;
    const idc = `${el.id || ''} ${typeof el.className === 'string' ? el.className : ''}`;
    if (STOP_CLASS_RX.test(idc)) return true;
    const own = cleanText(el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ');
    return own.length <= 120 && STOP_TEXT_RX.test(own);
  }

  function isChapterHeading(el) {
    if (!el || !/^H[1-3]$/.test(el.tagName)) return false;
    const t = cleanText(el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ');
    if (!t || t.length > 250) return false;
    return /chương\s*\d+|[-–—]\s*(?:chương\s*)?\d+\s*$/i.test(t) || /^chương\s*\d+/i.test(t);
  }

  let root = null;
  let rootSelector = '';
  for (const sel of ROOT_SELECTORS) {
    const candidates = Array.from(document.querySelectorAll(sel)).filter(visible);
    if (candidates.length) {
      root = candidates.reduce((a,b) => ((b.innerText || b.textContent || '').length > (a.innerText || a.textContent || '').length ? b : a));
      rootSelector = sel;
      break;
    }
  }
  if (!root) return {ok:false, error:'root_not_found'};

  // Heading ưu tiên nằm trong root. Nếu .chapter-content chỉ chứa phần thân, heading có thể nằm ngay trước root.
  let heading = Array.from(root.querySelectorAll('h1,h2,h3')).find(isChapterHeading) || null;
  if (!heading) {
    let p = root.previousElementSibling;
    let hops = 0;
    while (p && hops++ < 8) {
      if (isChapterHeading(p)) { heading = p; break; }
      const nested = p.querySelector && Array.from(p.querySelectorAll('h1,h2,h3')).find(isChapterHeading);
      if (nested) { heading = nested; break; }
      p = p.previousElementSibling;
    }
  }

  const pieces = [];
  function needSpace(a,b) {
    if (!a || !b || /\s$/.test(a) || /^\s/.test(b)) return false;
    const ca=a[a.length-1], cb=b[0];
    if (/[,.!?:;%\)\]\}»”’…]/.test(cb)) return false;
    if (/[\(\[\{«“‘]/.test(ca)) return false;
    if (/[-/\\]/.test(ca) || /[-/\\]/.test(cb)) return false;
    return /[\p{L}\p{N}]/u.test(ca) && /[\p{L}\p{N}]/u.test(cb);
  }
  function append(v) {
    v = cleanText(v);
    if (!v) return;
    const last = pieces.length ? pieces[pieces.length-1] : '';
    if (needSpace(last, v)) pieces.push(' ');
    pieces.push(v);
  }

  let stopped = false;
  function walk(node, skipHeading=false) {
    if (stopped) return;
    if (node.nodeType === Node.TEXT_NODE) {
      append(node.nodeValue || '');
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const el = node;
    if (SKIP.has(el.tagName) || !visible(el)) return;
    if (isStopElement(el)) { stopped = true; return; }
    if (skipHeading && heading && (el === heading || el.contains(heading))) {
      // Nếu container chứa heading, duyệt children và chỉ bắt đầu sau heading.
      for (const child of el.childNodes) {
        if (child === heading) { skipHeading = false; continue; }
        if (!skipHeading) walk(child, false);
        if (stopped) break;
      }
      return;
    }
    if (BLOCK.has(el.tagName)) pieces.push('\n');
    append(pseudo(el,'::before'));
    if (el.tagName === 'BR') pieces.push('\n');
    else {
      for (const child of el.childNodes) { walk(child, false); if (stopped) break; }
      if (!stopped && el.shadowRoot) for (const child of el.shadowRoot.childNodes) { walk(child,false); if (stopped) break; }
    }
    append(pseudo(el,'::after'));
    if (BLOCK.has(el.tagName)) pieces.push('\n');
  }

  // Nếu heading nằm trong root, bỏ heading và lấy mọi thứ sau nó.
  // Nếu heading ở ngoài root, root được xem là phần thân chương và lấy toàn bộ root đến stop marker.
  if (heading && root.contains(heading)) {
    walk(root, true);
  } else {
    walk(root, false);
  }

  return {
    ok:true,
    rootSelector,
    heading: heading ? cleanText(heading.innerText || heading.textContent || '').trim() : '',
    text: pieces.join(''),
    html: root.outerHTML || '',
    stopped
  };
}
"""

GENERAL_BROWSER_EXTRACTOR_JS = r"""
(args) => {
  const root = document.querySelector(args.selector);
  if (!root) return {ok:false,error:'selector_not_found'};
  return {ok:true,text:root.innerText || root.textContent || '',html:root.outerHTML || ''};
}
"""


def _find_general_browser_root(page) -> str:
    for selector in GENERAL_CONTENT_SELECTORS:
        try:
            loc = page.locator(selector).first
            if loc.count() and loc.is_visible(timeout=1000):
                t = (loc.text_content(timeout=1000) or "").strip()
                if len(t) >= 80:
                    return selector
        except Exception:
            continue
    for selector in ("article", "main", "body"):
        try:
            if page.locator(selector).first.count():
                return selector
        except Exception:
            pass
    raise RuntimeError("Không tìm thấy vùng nội dung trên trang.")


def _looks_like_whole_page(text: str) -> bool:
    bad = [
        "Đăng nhập", "Đăng ký", "Trang chủ", "Báo cáo nội dung vi phạm", "Cài đặt",
        "Chính sách bảo mật", "Sitemap", "document.addEventListener", "@keyframes", "font-family:",
    ]
    hits = sum(1 for x in bad if x.casefold() in text.casefold())
    return hits >= 4


def _page_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=3000) or ""
    except Exception:
        return ""


def _monkeyd_is_locked(page) -> bool:
    body = _page_text(page).upper()
    return any(marker.upper() in body for marker in MONKEYD_LOCK_MARKERS)


def _monkeyd_has_real_content(page) -> bool:
    """Chỉ true khi có chapter text đủ dài và không còn khung khóa."""
    if _monkeyd_is_locked(page):
        return False
    for selector in SPECIAL_ROOT_SELECTORS:
        try:
            loc = page.locator(selector).first
            if not loc.count() or not loc.is_visible(timeout=500):
                continue
            text = normalize_extracted_text(loc.inner_text(timeout=1500) or "")
            if len(text) >= 150 and not _looks_like_whole_page(text):
                return True
        except Exception:
            continue
    return False


def _handle_monkeyd_manual_unlock(context, page, url: str, timeout_seconds: int = 300):
    """
    Không tự click và không inject localStorage/cookie.
    Nếu MonkeyD đang khóa bằng Shopee, Chromium hiển thị để người dùng tự thao tác.
    Sau khi thấy thao tác mở tab Shopee, tool có thể đóng tab ngoài và reload tab truyện.
    """
    if not _monkeyd_is_locked(page):
        return

    print("\n" + "=" * 68)
    print("MONKEYD ĐANG YÊU CẦU THAO TÁC TRÊN TRÌNH DUYỆT")
    print("1) Trong Chromium vừa mở, tự bấm liên kết/nút theo yêu cầu của trang.")
    print("2) Nếu trang không tự cập nhật, quay lại tab truyện; tool sẽ tự reload.")
    print("3) Tool KHÔNG tự click và KHÔNG giả mạo localStorage/cookie.")
    print("Đang chờ tối đa 5 phút...")
    print("=" * 68 + "\n")

    deadline = time.time() + timeout_seconds
    last_reload = 0.0
    popup_seen = False

    while time.time() < deadline:
        # Khi người dùng tự click và một tab Shopee bật lên, đó là dấu hiệu thao tác đã diễn ra.
        # Chỉ đóng tab ngoài sau khi người dùng đã tự click; không kích hoạt link thay người dùng.
        for p in list(context.pages):
            if p == page:
                continue
            try:
                host = hostname_of(p.url) if p.url and p.url.startswith(("http://", "https://")) else ""
            except Exception:
                host = ""
            if "shopee" in host:
                popup_seen = True
                try:
                    p.close()
                except Exception:
                    pass

        if popup_seen and time.time() - last_reload >= 2.0:
            try:
                page.bring_to_front()
                page.reload(wait_until="domcontentloaded", timeout=30000)
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass
                last_reload = time.time()
            except Exception:
                pass

        if _monkeyd_has_real_content(page):
            return

        time.sleep(1.0)

    raise RuntimeError(
        "MonkeyD vẫn đang khóa nội dung sau 5 phút. Hãy chạy Convert lại và hoàn tất thao tác trong cửa sổ Chromium."
    )


def _configure_context(context):
    context.set_default_timeout(10000)
    context.set_default_navigation_timeout(35000)
    if PUBLIC_DEPLOYMENT:
        def guard(route):
            try:
                validate_url(route.request.url)
                route.continue_()
            except Exception:
                route.abort()
        context.route("**/*", guard)
        # WebSockets cannot be validated by the HTTP request routing guard.
        context.route_web_socket("**/*", lambda ws: ws.close())


def _launch_options(headless):
    options = browser_launch_options(headless)
    if proxy_url.get():
        options["proxy"] = {"server": proxy_url.get(), "bypass": "<-loopback>"}
        options.setdefault("args", []).extend([
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            "--disable-quic",
        ])
    return options


@guarded_network
def fetch_with_playwright(url: str) -> dict:
    from playwright.sync_api import sync_playwright

    url = validate_url(url)
    host = hostname_of(url)

    with sync_playwright() as p:
        if is_special_host(host):
            # Persistent profile giúp cookie/localStorage hợp lệ do browser/site tạo ra được giữ lại.
            # headless=False để người dùng có thể tự thao tác khi trang yêu cầu.
            browser = None
            context = None
            try:
                options = dict(locale="vi-VN", viewport={"width": 1365, "height": 900},
                               user_agent=DEFAULT_HEADERS["User-Agent"],
                               accept_downloads=not PUBLIC_DEPLOYMENT,
                               service_workers="block" if PUBLIC_DEPLOYMENT else "allow")
                if BROWSER_HEADLESS:
                    browser = p.chromium.launch(**_launch_options(True))
                    context = browser.new_context(**options)
                else:
                    MONKEYD_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
                    context = p.chromium.launch_persistent_context(
                        user_data_dir=str(MONKEYD_PROFILE_DIR),
                        **_launch_options(False), **options)
                _configure_context(context)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=35000)
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                page.wait_for_timeout(1200)

                if BROWSER_HEADLESS:
                    if _monkeyd_is_locked(page):
                        handler = manual_unlock_handler.get()
                        if handler is None:
                            raise RuntimeError("MonkeyD: trang yêu cầu thao tác mở khóa trực tiếp. Hãy dùng chế độ điều khiển Chromium trong ứng dụng.")
                        handler(context, page, url)
                else:
                    _handle_monkeyd_manual_unlock(context, page, url)

                # Sau khi nội dung thật xuất hiện mới extract đúng boundary.
                data = page.evaluate(MONKEYD_BOUNDARY_EXTRACTOR_JS, {"rootSelectors": SPECIAL_ROOT_SELECTORS})
                if not data or not data.get("ok"):
                    raise RuntimeError(
                        "MonkeyD: không xác định được vùng nội dung chương. Tool đã dừng thay vì lấy cả trang."
                    )
                raw_text = normalize_extracted_text(data.get("text", ""))
                title = normalize_extracted_text(data.get("heading", ""))
                root_html = data.get("html", "")
                source = f"Playwright boundary extractor ({data.get('rootSelector','?')})"
                diagnostics = {
                    "selector": data.get("rootSelector", ""),
                    "boundary_heading_found": bool(title),
                    "stop_boundary_hit": bool(data.get("stopped")),
                    "raw_length": len(raw_text),
                    "manual_unlock_needed": _monkeyd_is_locked(page),
                    "persistent_profile": not BROWSER_HEADLESS,
                }
                if len(raw_text) < 100:
                    raise RuntimeError(
                        "MonkeyD: nội dung chương trích xuất quá ngắn; đã dừng để tránh trả dữ liệu thiếu."
                    )
                if _looks_like_whole_page(raw_text):
                    raise RuntimeError(
                        "MonkeyD: kết quả có dấu hiệu chứa menu/footer/script; đã chặn để tránh dữ liệu rác."
                    )
                if not title:
                    try:
                        title = page.title().strip()
                    except Exception:
                        title = ""
                return {
                    "raw_text": raw_text,
                    "title": title,
                    "source": source,
                    "root_html": root_html,
                    "diagnostics": diagnostics,
                }
            finally:
                try:
                    if context is not None:
                        context.close()
                finally:
                    if browser is not None:
                        browser.close()

        # Trang thông thường: browser headless như trước.
        browser = p.chromium.launch(**_launch_options(True))
        try:
            context = browser.new_context(
                user_agent=DEFAULT_HEADERS["User-Agent"], locale="vi-VN",
                viewport={"width": 1365, "height": 900},
                accept_downloads=not PUBLIC_DEPLOYMENT,
                service_workers="block" if PUBLIC_DEPLOYMENT else "allow")
            _configure_context(context)
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=35000)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            page.wait_for_timeout(1200)

            selector = _find_general_browser_root(page)
            data = page.evaluate(GENERAL_BROWSER_EXTRACTOR_JS, {"selector": selector})
            if not data or not data.get("ok"):
                raise RuntimeError(f"Không extract được vùng nội dung: {selector}")
            raw_text = normalize_extracted_text(data.get("text", ""))
            root_html = data.get("html", "")
            title = ""
            for sel in (f"{selector} h1", f"{selector} h2", "h1", "h2"):
                try:
                    loc = page.locator(sel).first
                    if loc.count():
                        v = (loc.inner_text(timeout=1000) or "").strip()
                        if v:
                            title = v
                            break
                except Exception:
                    pass
            if not title:
                try:
                    title = page.title().strip()
                except Exception:
                    title = ""
            return {
                "raw_text": raw_text,
                "title": title,
                "source": f"Playwright rendered DOM ({selector})",
                "root_html": root_html,
                "diagnostics": {"selector": selector, "raw_length": len(raw_text)},
            }
        finally:
            browser.close()


def html_to_markdown(raw_html: str) -> str:
    if not raw_html:
        return ""
    if html2text is None:
        soup = BeautifulSoup(raw_html, "lxml")
        return normalize_extracted_text(soup.get_text(separator=" ", strip=True))
    converter = html2text.HTML2Text()
    converter.body_width = 0
    converter.ignore_links = False
    converter.ignore_images = True
    converter.inline_links = True
    md = converter.handle(raw_html)
    md = "\n".join(line.rstrip() for line in md.splitlines())
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def _finish(title: str, raw_text: str, root_html: str, source: str, audio_clean: bool, diagnostics=None):
    if len(raw_text) > MAX_TEXT_CHARS or len(root_html) > MAX_HTML_BYTES:
        raise ValueError("Nội dung quá lớn để xử lý. Hãy chọn một trang hoặc chương ngắn hơn.")
    raw_text = normalize_extracted_text(raw_text)
    if audio_clean:
        clean_text, stats = clean_story_text(raw_text)
    else:
        clean_text, stats = raw_text, {"removed_blacklist_count": 0, "removed_emoji_count": 0, "removed_blacklist": [], "removed_emoji": []}
    stats["diagnostics"] = diagnostics or {}
    md = html_to_markdown(root_html)
    if title and md and not md.lstrip().startswith("#"):
        md = f"# {title}\n\n{md}"
    if not md:
        md = (f"# {title}\n\n" if title else "") + raw_text
    return {"title": title, "raw_text": raw_text, "text": clean_text, "markdown": md, "source_mode": source, "clean_stats": stats}


def scrape(url: str, use_browser: bool = False, audio_clean: bool = True):
    host = hostname_of(url)
    if is_special_host(host):
        use_browser = True

    if use_browser:
        result = fetch_with_playwright(url)
        return _finish(result["title"], result["raw_text"], result.get("root_html", ""), result["source"], audio_clean, result.get("diagnostics"))

    raw_html = fetch_with_requests(url)
    raw_text = extract_content_from_html(raw_html, host)
    soup = BeautifulSoup(normalize_hidden_chars(raw_html), "lxml")
    root = find_general_container(soup)
    title = ""
    for sel in ("h1", "h2"):
        el = root.select_one(sel) if isinstance(root, Tag) else None
        if el:
            title = el.get_text(" ", strip=True)
            if title:
                break
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)
    return _finish(title, raw_text, str(root), "Requests + BS4", audio_clean)


def scrape_auto(url: str, audio_clean: bool = True):
    host = hostname_of(url)
    if is_special_host(host):
        return scrape(url, True, audio_clean)
    try:
        result = scrape(url, False, audio_clean)
        if len(result.get("raw_text", "")) >= 500:
            return result
    except Exception:
        pass
    return scrape(url, True, audio_clean)
