"""RSS / Atom readers for the central bank speeches panel."""

from __future__ import annotations

import email.utils
import xml.etree.ElementTree as ET

from .base import HttpClient

ATOM = "{http://www.w3.org/2005/Atom}"


def _date(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        return email.utils.parsedate_to_datetime(raw).date().isoformat()
    except (TypeError, ValueError):
        return raw[:10] if len(raw) >= 10 and raw[4] == "-" else None


def parse_feed(xml_text: str, bank: str, limit: int = 8) -> list[dict]:
    root = ET.fromstring(xml_text)
    items = []
    for item in root.iter("item"):
        items.append({"bank": bank, "title": (item.findtext("title") or "").strip(),
                      "url": (item.findtext("link") or "").strip(),
                      "date": _date(item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date"))})
    for entry in root.iter(f"{ATOM}entry"):
        link = entry.find(f"{ATOM}link")
        items.append({"bank": bank, "title": (entry.findtext(f"{ATOM}title") or "").strip(),
                      "url": link.get("href", "") if link is not None else "",
                      "date": _date(entry.findtext(f"{ATOM}updated") or entry.findtext(f"{ATOM}published"))})
    items = [i for i in items if i["title"]]
    items.sort(key=lambda i: i["date"] or "", reverse=True)
    return items[:limit]


def fetch(http: HttpClient, url: str, bank: str) -> list[dict]:
    return parse_feed(http.get_text(url), bank)
