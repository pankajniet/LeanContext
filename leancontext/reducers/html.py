"""HTML reducer — for web-fetch / scraped tool outputs.

Strips tags, scripts, styles and collapses whitespace, keeping the visible text and
the links (URLs are signal, so they're preserved). Stdlib only, deterministic.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

_SKIP = {"script", "style", "noscript", "svg", "head", "template"}


class _Extract(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip += 1
        if tag == "a":
            for key, val in attrs:
                if key == "href" and val:
                    self.links.append(val)

    def handle_endtag(self, tag):
        if tag in _SKIP and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0:
            text = data.strip()
            if text:
                self.parts.append(text)


def reduce_html(text: str) -> tuple[str, list[str]]:
    parser = _Extract()
    parser.feed(text)
    body = re.sub(r"[ \t]+", " ", "\n".join(parser.parts)).strip()
    links = list(dict.fromkeys(parser.links))

    out = body
    if links:
        out += "\n\nLinks: " + " ".join(links)
    notes = [f"stripped HTML tags/scripts/styles; kept visible text + {len(links)} links"]
    return out, notes
