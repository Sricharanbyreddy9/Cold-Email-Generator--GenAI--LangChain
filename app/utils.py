# app/utils.py
import re
import html
from typing import Optional

_URL_RE = re.compile(
    r"""(?xi)
    \b
    (?:https?://|www\.)
    [^\s<>'")]+
    """
)

_HTML_TAG_RE = re.compile(r"<[^>]+>")

# allow characters that matter for tech terms: C++, C#, .NET, Node.js, React.js, Python-3.10, AWS/S3, etc.
_ALLOWED_CHARS_RE = re.compile(r"[^A-Za-z0-9\s\.\,\:\;\-\_\+\#\&\/\(\)\[\]\{\}'\"@%!?]")

_MULTI_SPACE_RE = re.compile(r"\s{2,}")

def clean_text(text: Optional[str]) -> str:
    """
    Normalize scraped text for prompting/parsing.

    Steps:
    1) HTML entity unescape
    2) Strip HTML tags
    3) Remove URLs
    4) Remove unwanted special chars (keep ones useful for tech tokens)
    5) Collapse multiple spaces/newlines
    6) Trim

    Returns a single-line string with meaningful punctuation preserved.
    """
    if not text:
        return ""

    # Ensure string
    text = str(text)

    # 1) Unescape HTML entities (&amp;, &nbsp;, etc.)
    text = html.unescape(text)

    # 2) Remove HTML tags
    text = _HTML_TAG_RE.sub(" ", text)

    # 3) Remove URLs
    text = _URL_RE.sub(" ", text)

    # 4) Remove unwanted special characters
    text = _ALLOWED_CHARS_RE.sub(" ", text)

    # 5) Replace multiple whitespace (including newlines/tabs) with single space
    text = _MULTI_SPACE_RE.sub(" ", text)

    # 6) Trim
    return text.strip()


def clean_and_clip(text: Optional[str], max_len: int = 4000) -> str:
    """
    Clean the text and clip to `max_len` characters (safe to pass to models).
    """
    cleaned = clean_text(text)
    return cleaned[:max_len]
