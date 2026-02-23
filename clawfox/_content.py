"""Turn page HTML into markdown + interactive element list for agent use."""
from __future__ import annotations

import json
import re
from html import unescape

# Optional: use markdownify for HTML->markdown. Fallback to stripped text if not present.
try:
    from markdownify import markdownify as md
    HAS_MARKDOWNIFY = True
except ImportError:
    HAS_MARKDOWNIFY = False

# Script we inject to get interactive elements with suggested Playwright selectors
INTERACTIVE_ELEMENTS_JS = """
() => {
  const elements = [];
  const nodes = document.querySelectorAll('a[href], button, input, [role="button"], [onclick]');
  nodes.forEach((el, i) => {
    const tag = el.tagName.toLowerCase();
    const id = el.id ? `#${el.id}` : null;
    const name = el.name && (el.tagName === 'INPUT' || el.tagName === 'BUTTON') ? `[name="${el.name}"]` : null;
    let suggested = id || name || null;
    if (!suggested && tag === 'button') {
      const t = (el.textContent || '').trim().slice(0, 50);
      if (t) suggested = `role=button[name="${t.replace(/"/g, '\\"')}"]`;
    }
    if (!suggested && tag === 'a' && el.textContent) {
      const t = (el.textContent || '').trim().slice(0, 50);
      if (t) suggested = `text=${JSON.stringify(t)}`;
    }
    if (!suggested) suggested = tag + (el.className ? '.' + String(el.className).split(/\\s+/)[0] : '');
    const href = el.getAttribute('href');
    const visible = el.offsetParent !== null && (el.offsetWidth > 0 || el.offsetHeight > 0);
    elements.push({ tag, id: el.id || null, name: el.name || null, suggested, href: href || null, visible, text: (el.textContent || '').trim().slice(0, 80) });
  });
  return elements;
}
"""


def html_to_markdown(html: str) -> str:
    if HAS_MARKDOWNIFY:
        return md(html, heading_style="ATX", strip=["script", "style"])
    # Fallback: strip tags and collapse whitespace
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:50000]  # cap size


def format_interactive_elements(elements: list[dict]) -> str:
    if not elements:
        return ""
    lines = ["## Interactive elements (suggested selectors)", ""]
    for e in elements:
        sel = e.get("suggested") or "?"
        extra = []
        if e.get("href"):
            extra.append(f"href={e['href']}")
        if e.get("text"):
            extra.append(f"text={e['text'][:40]!r}")
        line = f"- `{sel}`"
        if extra:
            line += " " + " ".join(extra)
        lines.append(line)
    return "\n".join(lines) + "\n"


def build_go_output(html: str, interactive_elements: list[dict], as_html: bool) -> str:
    if as_html:
        return html
    md_body = html_to_markdown(html)
    elements_section = format_interactive_elements(interactive_elements)
    if elements_section:
        return md_body.rstrip() + "\n\n" + elements_section
    return md_body
