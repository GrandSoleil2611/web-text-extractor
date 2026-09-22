from urllib.parse import urlsplit
import base64
from functools import lru_cache
from html import escape
from pathlib import Path

import streamlit as st

from settings import SHOPEE_AFFILIATE_URL, VBEE_AFFILIATE_URL, VBEE_CTA_ENABLED


@lru_cache(maxsize=1)
def _vbee_image():
    return base64.b64encode((Path(__file__).parent / "assets" / "vbee-aivoice.png").read_bytes()).decode("ascii")


def render_vbee_banner():
    if not VBEE_CTA_ENABLED:
        return
    try:
        picture = _vbee_image()
    except OSError:
        st.caption("Chưa tải được ảnh banner. Kiểm tra file assets/vbee-aivoice.png trên GitHub.")
        return
    st.markdown(f'''<style>
.vbee-banner{{display:flex;align-items:center;gap:28px;padding:22px;margin:8px 0 24px;border:1px solid #35405a;border-radius:18px;background:linear-gradient(115deg,#1d2340,#172131);text-decoration:none!important;color:#eef2ff!important;transition:border-color .15s}}
.vbee-banner:hover{{border-color:#b6a9ff}}
.vbee-banner:focus-visible{{outline:3px solid #ffe000;outline-offset:3px}}
.vbee-banner img{{width:240px;max-width:100%;height:auto;flex-shrink:0;border-radius:12px;display:block}}
.vbee-banner-copy{{flex:1;min-width:0}}
.vbee-banner-label{{font-size:12px;color:#b5bfd5;letter-spacing:.04em}}
.vbee-banner-title{{font-size:23px;font-weight:700;line-height:1.3;margin:7px 0}}
.vbee-banner-description{{font-size:15px;color:#c7d1e3;line-height:1.6}}
.vbee-banner-action{{display:inline-block;background:#ffe000;color:#20174d;font-size:14px;font-weight:700;padding:10px 16px;border-radius:9px;margin-top:13px}}
@media(max-width:640px){{.vbee-banner{{flex-direction:column;align-items:flex-start;gap:17px;padding:18px}}.vbee-banner img{{width:200px}}.vbee-banner-title{{font-size:21px}}}}
</style>
<a class="vbee-banner" href="{escape(VBEE_AFFILIATE_URL, quote=True)}" target="_blank" rel="sponsored noopener noreferrer" aria-label="Vbee AIVoice — liên kết tài trợ">
<img src="data:image/png;base64,{picture}" alt="AIVoice by Vbee.ai" width="540" height="276">
<div class="vbee-banner-copy"><div class="vbee-banner-label">LIÊN KẾT TÀI TRỢ</div>
<div class="vbee-banner-title">Biến văn bản thành giọng nói</div>
<div class="vbee-banner-description">Tạo audio tiếng Việt từ nội dung của bạn với Vbee AIVoice.</div>
<span class="vbee-banner-action">Thử Vbee AIVoice →</span></div></a>''', unsafe_allow_html=True)


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
