"""Minimal markdown + code + citation renderer for the chat drawer."""
from __future__ import annotations
import re, html
def render_markdown(md: str) -> str:
    if not md: return ""
    # escape then selectively unescape our allowed tags
    text = html.escape(md)
    # code fences
    def repl_code(m):
        lang = (m.group(1) or "").strip()
        body = html.escape(m.group(2))
        return f'<pre style="background:var(--code);padding:8px;border-radius:8px;overflow:auto"><code lang="{lang}">{body}</code></pre>'
    text = re.sub(r"```(\w*)\n(.*?)```", repl_code, text, flags=re.DOTALL)
    # inline code
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # bold / italic
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    # links
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', text)
    # citations like [1] or [ex.com](https://ex.com)
    text = re.sub(r"\[(\d+)\]", r'<sup class="citation">[\1]</sup>', text)
    # line breaks
    text = text.replace("\n", "<br>")
    return text
def citations_block(urls: list[str]) -> str:
    if not urls: return ""
    items = "".join(f'<li><a href="{html.escape(u)}">{html.escape(u)}</a></li>' for u in urls)
    return f'<ol class="citations">{items}</ol>'
