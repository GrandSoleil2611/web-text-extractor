from urllib.parse import urlsplit

import streamlit as st

from settings import SHOPEE_AFFILIATE_URL, VBEE_AFFILIATE_URL, VBEE_CTA_ENABLED


def render_affiliates():
    if VBEE_CTA_ENABLED:
        with st.container(border=True):
            st.subheader("🔊 Chuyển văn bản thành giọng nói")
            st.write("Tạo audio tiếng Việt từ nội dung vừa xử lý với Vbee AIVoice.")
            st.link_button("🎙️ Thử Vbee AIVoice →", VBEE_AFFILIATE_URL,
                           use_container_width=True)
            st.caption("Liên kết tài trợ")
    parsed = urlsplit(SHOPEE_AFFILIATE_URL)
    if parsed.scheme == "https" and parsed.hostname:
        with st.container(border=True):
            st.link_button("Khám phá ưu đãi Shopee →", SHOPEE_AFFILIATE_URL,
                           use_container_width=True)
            st.caption("Liên kết tài trợ")
