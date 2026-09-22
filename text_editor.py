"""Session-local find/replace controls for extracted text."""
import re
import streamlit as st
from settings import MAX_TEXT_CHARS

EDITORS = {"Clean Text": "edit_clean", "Raw Text": "edit_raw", "Markdown": "edit_md"}


def search_pattern(query, match_case=False, whole_word=False):
    if not query:
        return None
    expression = re.escape(query)
    if whole_word:
        expression = r"(?<!\w)" + expression + r"(?!\w)"
    return re.compile(expression, 0 if match_case else re.IGNORECASE)


def replace_all(text, query, replacement, match_case=False, whole_word=False):
    pattern = search_pattern(query, match_case, whole_word)
    if pattern is None:
        return text, 0
    count, removed = 0, 0
    for match in pattern.finditer(text):
        count += 1
        removed += match.end() - match.start()
    if len(text) - removed + count * len(replacement) > MAX_TEXT_CHARS:
        raise ValueError("Kết quả thay thế quá lớn; giới hạn là 2 triệu ký tự.")
    return pattern.sub(lambda match: replacement, text), count


def render_find_replace():
    with st.expander("🔎 Tìm và thay thế"):
        target = st.selectbox("Áp dụng cho", list(EDITORS), key="replace_target")
        key = EDITORS[target]
        query = st.text_input("Tìm kiếm", key="find_query")
        replacement = st.text_input("Thay thế bằng", key="replace_value",
                                    help="Để trống để xóa các đoạn tìm thấy. Ký tự được hiểu nguyên văn, không dùng regex.")
        match_case = st.checkbox("Phân biệt chữ hoa/thường", key="find_case")
        whole_word = st.checkbox("Chỉ khớp nguyên từ", key="find_word")
        pattern = search_pattern(query, match_case, whole_word)
        count = sum(1 for _ in pattern.finditer(st.session_state[key])) if pattern else 0
        st.caption(f"Tìm thấy {count} kết quả trong {target}." if query else "Nhập nội dung cần tìm.")
        undo_key = key + "_undo"
        if st.button("Thay thế tất cả", disabled=not query or not count, key="replace_all"):
            try:
                previous = st.session_state[key]
                updated, replaced = replace_all(previous, query, replacement, match_case, whole_word)
                if updated != previous:
                    st.session_state[undo_key] = previous
                    st.session_state[key] = updated
                st.session_state["replace_notice"] = f"Đã thay thế {replaced} kết quả trong {target}."
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        if st.button("Hoàn tác lần thay thế", disabled=undo_key not in st.session_state, key="undo_replace"):
            st.session_state[key] = st.session_state.pop(undo_key)
            st.session_state["replace_notice"] = f"Đã hoàn tác lần thay thế trong {target}."
            st.rerun()
        if notice := st.session_state.pop("replace_notice", None):
            st.success(notice)
        st.caption("Thay thế trên toàn bộ bản đang chọn, không thay đổi các bản khác. File tải xuống dùng nội dung đã chỉnh sửa. Hoàn tác khôi phục bản trước lần thay thế gần nhất.")
