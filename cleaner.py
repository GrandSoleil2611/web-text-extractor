import re
from contextvars import ContextVar
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BLACKLIST_FILE = BASE_DIR / "blacklist.txt"
blacklist_override = ContextVar("blacklist_override", default=None)

EMOJI_RE = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF\U0001F300-\U0001F5FF\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FAFF"
    "\u2600-\u26FF\u2700-\u27BF"
    "]",
    flags=re.UNICODE,
)

LEADING_DECORATION_RE = re.compile(
    r"^\s*(?:[★☆●○◆◇■□▪▫►▶▷➤➜➠→⇒※✦✧✿❀❁❃❋☘☀☁☂☕❤♥♡✨🍊🍒🌸🫶🤟🤗🥰😍]+\s*)+"
)

PROMO_REGEXES = [
    re.compile(r"\btruyện\s+được\s+đăng\s+(?:tải|bởi)\b", re.I),
    re.compile(r"\bmonkeyd+d?\.com\b", re.I),
    re.compile(r"\bmonkeyd\.vn\b", re.I),
    re.compile(r"\bfollow\s+(?:fanpage|page)\b", re.I),
    re.compile(r"\bqu[eé]o\s+c[oò]m\b", re.I),
    re.compile(r"\bnếu\s+được\b.*\b(?:c[oò]m|comment|review)\b", re.I),
    re.compile(r"\bxin\b.*\b(?:c[oò]m|comment|review)\b", re.I),
    re.compile(r"\bchúc\b.*\bđọc\s+truyện\s+vui\s+vẻ\b", re.I),
    re.compile(r"\bđọc\s+(?:truyện\s+)?tại\b", re.I),
]


def load_blacklist(path: Path = BLACKLIST_FILE) -> list[str]:
    override = blacklist_override.get()
    if override is not None:
        return [line.strip().casefold() for line in override.splitlines()
                if line.strip() and not line.lstrip().startswith("#")]
    if not path.exists():
        return []
    return [
        line.strip().casefold()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def contains_blacklisted_keyword(line: str, blacklist: list[str]) -> bool:
    folded = line.casefold()
    return any(k in folded for k in blacklist) or any(rx.search(line) for rx in PROMO_REGEXES)


def emoji_stats(line: str) -> tuple[int, float]:
    non_space = re.sub(r"\s+", "", line)
    if not non_space:
        return 0, 0.0
    count = len(EMOJI_RE.findall(line))
    return count, count / len(non_space)


def is_emoji_junk_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    count, density = emoji_stats(stripped)
    if count >= 3 and density >= 0.18:
        return True
    if count >= 5:
        return True
    alnum_count = len(re.findall(r"[A-Za-zÀ-ỹĐđ0-9]", stripped, flags=re.UNICODE))
    symbol_count = len(re.findall(r"[^\w\s.,!?;:'\"“”‘’()\[\]{}…-]", stripped, flags=re.UNICODE))
    return symbol_count >= 5 and alnum_count <= 3


def strip_leading_decorations(line: str) -> str:
    return LEADING_DECORATION_RE.sub("", line).strip()


def restore_split_words(text: str) -> str:
    """Chỉ phục hồi chữ bị chèn dấu, không đoán từ đã bị mất."""
    token_re = re.compile(
        r"(?<!\w)(?:[A-Za-zÀ-ỹĐđ]\s*[./\\|]\s*){2,}[A-Za-zÀ-ỹĐđ](?!\w)",
        flags=re.UNICODE,
    )

    def collapse(match: re.Match) -> str:
        return re.sub(r"\s*[./\\|]\s*", "", match.group(0))

    text = token_re.sub(collapse, text)
    return text.replace("\\-", "-")


def clean_story_text(
    text: str,
    *,
    remove_blacklist: bool = True,
    remove_emoji_lines: bool = True,
    restore_broken_words: bool = True,
    join_lines: bool = True,
) -> tuple[str, dict]:
    blacklist = load_blacklist() if remove_blacklist else []
    kept_lines: list[str] = []
    removed_blacklist: list[str] = []
    removed_emoji: list[str] = []

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        if remove_blacklist and contains_blacklisted_keyword(line, blacklist):
            removed_blacklist.append(line)
            continue

        if remove_emoji_lines and is_emoji_junk_line(line):
            removed_emoji.append(line)
            continue

        if remove_emoji_lines:
            line = strip_leading_decorations(line)
            if not line:
                continue

        kept_lines.append(line)

    result = "\n".join(kept_lines)

    if restore_broken_words:
        result = restore_split_words(result)

    # Workflow “Làm audio truyện”: xóa ký tự 【 】 nhưng giữ nguyên 100% nội dung bên trong.
    # Ví dụ: 【Hôm nay sao không quay video tắm?】 -> Hôm nay sao không quay video tắm?
    result = result.replace("【", "").replace("】", "")

    if join_lines:
        # Xuống dòng phải thành 1 space, không được xóa trắng hoàn toàn.
        result = re.sub(r"\s*\n+\s*", " ", result)
        result = re.sub(r"[ \t]{2,}", " ", result).strip()
    else:
        result = re.sub(r"\n{3,}", "\n\n", result).strip()

    return result, {
        "removed_blacklist_count": len(removed_blacklist),
        "removed_emoji_count": len(removed_emoji),
        "removed_blacklist": removed_blacklist,
        "removed_emoji": removed_emoji,
    }
