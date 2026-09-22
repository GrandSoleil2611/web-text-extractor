from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

_viewer = components.declare_component("remote_browser_viewer", path=str(Path(__file__).with_name("remote_component")))


def save_result(result):
    for source, target in (("markdown", "markdown_result"), ("text", "text_result"),
                           ("raw_text", "raw_text_result"), ("title", "title_result")):
        st.session_state[target] = result[source]
    st.session_state.clean_stats = result.get("clean_stats", {})
    st.session_state.source_mode = result.get("source_mode", "unknown")


@st.fragment(run_every=2)
def render_remote_job():
    job = st.session_state.get("remote_job")
    if job is None:
        return
    state = job.snapshot()
    if state["type"] in {"result", "error"} and job.done.is_set():
        if state["type"] == "result":
            save_result(state["result"])
            st.session_state.remote_notice = "Đã lấy nội dung từ phiên Chromium."
        else:
            st.session_state.remote_error = state["error"]
        del st.session_state["remote_job"]
        st.rerun()
    st.subheader("Thao tác với trang nguồn")
    st.caption("Đây là Chromium riêng cho phiên của bạn. Bấm vào ảnh để thao tác; nội dung trang và liên kết bên trong thuộc website nguồn. Phiên tự đóng sau tối đa 4 phút.")
    if st.button("Hủy và đóng Chromium", key="cancel_remote"):
        job.cancel()
        st.info("Đang đóng phiên Chromium…")
    if state["type"] == "browser":
        st.caption(f"Còn khoảng {state['seconds_left']} giây để thao tác.")
        command = _viewer(state=state, key="remote_screen_" + job.identity, default=None)
        if command:
            job.send(command)
    else:
        st.info("Đang mở trang bằng Chromium…")
