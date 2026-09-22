import re
import time
from pathlib import Path
import streamlit as st
from job_runner import run_crawl
from affiliate import render_affiliates
from settings import PUBLIC_DEPLOYMENT, BROWSER_HEADLESS
from text_editor import EDITORS, render_find_replace

BASE_DIR = Path(__file__).resolve().parent
BLACKLIST_FILE = BASE_DIR / "blacklist.txt"

st.set_page_config(page_title="Lấy và làm sạch văn bản web | Web Text Extractor", page_icon="📄", layout="wide")
st.title("📄 Lấy và làm sạch văn bản web")
st.caption("Trích xuất nội dung từ URL, giữ bản gốc, làm sạch văn bản truyện và tải xuống TXT hoặc Markdown.")
with st.expander("Hướng dẫn sử dụng"):
    st.write("1. Dán URL bài viết hoặc chương truyện.\n2. Chọn Auto hoặc Playwright cho trang cần JavaScript.\n3. Bấm Convert, kiểm tra Raw Text và tải kết quả.")
    st.caption("Chỉ xử lý nội dung bạn có quyền sử dụng. Kết quả nằm trong phiên sử dụng, không được ghi vào kho lưu trữ của ứng dụng.")

for k in ("markdown_result", "text_result", "raw_text_result", "title_result", "clean_stats", "source_mode"):
    if k not in st.session_state:
        st.session_state[k] = {} if k == "clean_stats" else ""

url = st.text_input("URL", placeholder="https://monkeydd.com/...", max_chars=4096)
mode = st.radio("Chế độ crawl", ["Auto (khuyên dùng)", "Requests", "Playwright"], horizontal=True)

if "monkeyd" in url.lower():
    if BROWSER_HEADLESS:
        st.info("MonkeyD được xử lý bằng Chromium headless. Nếu trang yêu cầu mở khóa thủ công, hãy sử dụng bản local có cửa sổ Chromium; server không thể hiển thị cửa sổ đó cho bạn.")
    else:
        st.info("MonkeyD: nếu chương yêu cầu mở Shopee, Chromium sẽ mở để bạn tự thao tác. Tool không tự click và không giả mạo storage.")
audio_clean = st.checkbox("Clean Text theo workflow 'Làm audio truyện'", value=True)

with st.expander("⚙ Blacklist Keywords"):
    try:
        current = BLACKLIST_FILE.read_text(encoding="utf-8-sig")
    except Exception:
        current = ""
    if "blacklist" not in st.session_state:
        st.session_state.blacklist = current
    edited = st.text_area("Mỗi dòng là một cụm từ rác", st.session_state.blacklist, height=230, max_chars=20000)
    if st.button("💾 Lưu Blacklist"):
        st.session_state.blacklist = edited
        if PUBLIC_DEPLOYMENT:
            st.success("Đã lưu blacklist cho phiên của bạn.")
        else:
            try:
                BLACKLIST_FILE.write_text(edited, encoding="utf-8")
                st.success("Đã lưu blacklist.txt")
            except OSError:
                st.warning("Không thể ghi file; blacklist vẫn được áp dụng trong phiên này.")

if st.button("Convert", type="primary", use_container_width=True):
    if not url.strip():
        st.warning("Bạn hãy nhập URL trước.")
    elif PUBLIC_DEPLOYMENT and time.monotonic() - st.session_state.get("last_crawl", 0) < 10:
        st.warning("Vui lòng đợi vài giây trước khi gửi yêu cầu tiếp theo.")
    else:
        st.session_state.last_crawl = time.monotonic()
        for key in EDITORS.values():
            st.session_state.pop(key, None)
            st.session_state.pop(key + "_undo", None)
        st.session_state.pop("replace_notice", None)
        for key in ("markdown_result", "text_result", "raw_text_result", "title_result", "source_mode"):
            st.session_state[key] = ""
        with st.spinner("Đang render và bóc đúng vùng nội dung..."):
            try:
                result = run_crawl(url, "Auto" if mode.startswith("Auto") else mode,
                                   audio_clean, st.session_state.blacklist)
                st.session_state.markdown_result = result["markdown"]
                st.session_state.text_result = result["text"]
                st.session_state.raw_text_result = result["raw_text"]
                st.session_state.title_result = result["title"]
                st.session_state.clean_stats = result.get("clean_stats", {})
                st.session_state.source_mode = result.get("source_mode", "unknown")
                st.success("Đã xử lý xong.")
            except Exception as e:
                st.error(str(e))

if st.session_state.raw_text_result:
    render_affiliates()
    st.divider()
    if st.session_state.title_result:
        st.subheader(st.session_state.title_result)
    st.caption(f"Nguồn: {st.session_state.source_mode}")
    filename = re.sub(r'[\\/:*?"<>|]', "_", st.session_state.title_result or "article")
    for key, source in (("edit_clean", "text_result"), ("edit_raw", "raw_text_result"), ("edit_md", "markdown_result")):
        if key not in st.session_state:
            st.session_state[key] = st.session_state[source]
    render_find_replace()
    tab_clean, tab_raw, tab_md = st.tabs(["Clean Text", "Raw Text", "Markdown"])

    with tab_clean:
        stats = st.session_state.clean_stats or {}
        c1, c2 = st.columns(2)
        c1.metric("Blacklist đã xóa", stats.get("removed_blacklist_count", 0))
        c2.metric("Dòng emoji đã xóa", stats.get("removed_emoji_count", 0))
        diag = stats.get("diagnostics", {})
        if diag:
            with st.expander("🔎 Diagnostics"):
                st.json(diag)
        removed = stats.get("removed_blacklist", []) + stats.get("removed_emoji", [])
        if removed:
            with st.expander("Các dòng bị xóa"):
                st.code("\n".join(removed))
        st.text_area("Clean Text", key="edit_clean", height=520)
        st.download_button("⬇ Tải Clean .txt", st.session_state.edit_clean, f"{filename}_clean.txt", "text/plain", use_container_width=True)

    with tab_raw:
        st.info("Raw Text ban đầu chưa qua làm sạch. Bạn có thể chỉnh sửa bản hiển thị và tải xuống; bản crawl gốc vẫn được giữ trong phiên.")
        st.text_area("Raw Text", key="edit_raw", height=520)
        st.download_button("⬇ Tải Raw .txt", st.session_state.edit_raw, f"{filename}_raw.txt", "text/plain", use_container_width=True)

    with tab_md:
        st.text_area("Markdown", key="edit_md", height=520)
        st.download_button("⬇ Tải .md", st.session_state.edit_md, f"{filename}.md", "text/markdown", use_container_width=True)

st.divider()
st.caption("Web Text Extractor · Công cụ lấy và làm sạch văn bản miễn phí · Liên kết tài trợ được ghi rõ; ứng dụng không tự chuyển trang.")
