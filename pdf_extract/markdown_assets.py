from __future__ import annotations

import re
from collections.abc import Iterable


_HTML_IMAGE_SRC_RE = re.compile(
    r'(<img\b[^>]*\bsrc\s*=\s*)(?P<quote>["\'])(?P<path>imgs/[^"\']+)(?P=quote)',
    re.IGNORECASE,
)
_MARKDOWN_IMAGE_RE = re.compile(r"(!\[[^\]]*\]\()(?P<path>imgs/[^)\s]+)(\))")


def iter_page_local_image_paths(md_text: str) -> Iterable[str]:
    for match in _HTML_IMAGE_SRC_RE.finditer(md_text):
        yield match.group("path")
    for match in _MARKDOWN_IMAGE_RE.finditer(md_text):
        yield match.group("path")


def rewrite_page_local_image_paths(md_text: str, page_dir: str) -> str:
    page_prefix = f"pages/{page_dir}/"

    def rewrite_html(match: re.Match[str]) -> str:
        quote = match.group("quote")
        return f"{match.group(1)}{quote}{page_prefix}{match.group('path')}{quote}"

    md_text = _HTML_IMAGE_SRC_RE.sub(rewrite_html, md_text)
    return _MARKDOWN_IMAGE_RE.sub(rf"\1{page_prefix}\g<path>\3", md_text)
