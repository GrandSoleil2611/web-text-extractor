from cleaner import clean_story_text
from scraper import extract_content_from_html, normalize_hidden_chars, _looks_like_whole_page

# Static lossless test: text inside span/i/em/b must survive.
html = r'''
<html><body>
<nav>Trang chủ Đăng nhập</nav>
<div class="chapter-content">
  <p>Khi gả cho phu quân <span>vừa</span> yếu đuối <i>lại</i> xinh <em>đẹp</em> của <span>ta</span>, <b>chàng</b> là vị đại phu trẻ nhất trong trấn, còn ta là một sát thủ.</p>
  <p>Sau khi thành hôn, ta và chàng chung sống hoà thuận, tôn trọng lẫn nhau.</p>
  <p>Khi ta trúng độc, sắp c.h.ế.t, lại nghe chàng nói.</p>
  <p>🍊 Follow Fanpage FB "Xoăn dịch truyện" để nhận thông tin 🫶</p>
</div>
<footer>Chương trước Chương sau Sitemap</footer>
</body></html>
'''
raw = extract_content_from_html(html, "monkeydd.com")
assert "vừa yếu đuối lại xinh đẹp của ta, chàng" in raw, raw
assert "tôn trọng lẫn nhau" in raw, raw
assert "Trang chủ" not in raw, raw
assert "Sitemap" not in raw, raw

clean, stats = clean_story_text(raw)
assert "sắp chết" in clean, clean
assert "Follow Fanpage" not in clean, clean
assert ". Sau khi" in clean, clean
assert ".Sau khi" not in clean, clean

bracket_clean, _ = clean_story_text('【Hôm nay sao không quay video tắm?】 【Có phải muốn ăn tát rồi không?】')
assert bracket_clean == 'Hôm nay sao không quay video tắm? Có phải muốn ăn tát rồi không?', bracket_clean
assert '【' not in bracket_clean and '】' not in bracket_clean

hidden = normalize_hidden_chars("ta\u200b và\ufeff chàng\xa0đi")
assert hidden == "ta và chàng đi", repr(hidden)
assert _looks_like_whole_page("Đăng nhập Đăng ký Trang chủ Báo cáo nội dung vi phạm Cài đặt Sitemap")

bad_html = "<html><body><nav>menu</nav><p>some body text but no chapter container</p></body></html>"
try:
    extract_content_from_html(bad_html, "monkeydd.com")
    raise AssertionError("Expected fail-closed error")
except RuntimeError:
    pass

print("SELF TEST PASSED")
print("RAW:", raw)
print("CLEAN:", clean)
