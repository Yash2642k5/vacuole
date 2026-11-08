"""Turn SerpApi's loosely typed payloads into `Product` rows.

Engines disagree on types (str vs list vs dict), so every field goes through a coercion
helper before it reaches the domain model.
"""

from __future__ import annotations

import re
from typing import Any

from vacuole.domain.models import Product

_PRICE_RE = re.compile(r"\d[\d,]*\.?\d*")
_WHITESPACE_RE = re.compile(r"\s+")


def as_text(value: Any, limit: int | None = None) -> str:
    """Flatten whatever an engine gave us into a plain string."""
    if value is None:
        return ""
    if isinstance(value, str):
        text = value.strip()
    elif isinstance(value, bool):
        return ""
    elif isinstance(value, (int, float)):
        text = str(value)
    elif isinstance(value, dict):
        for key in ("raw", "value", "text", "name", "title"):
            if key in value:
                return as_text(value[key], limit)
        text = ""
    elif isinstance(value, (list, tuple)):
        parts = [as_text(item) for item in value]
        text = " · ".join(part for part in parts if part)
    else:
        text = str(value).strip()

    text = _WHITESPACE_RE.sub(" ", text).strip()
    if limit and len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def as_float(*candidates: Any) -> float | None:
    for value in candidates:
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, dict):
            nested = as_float(*(value.get(k) for k in ("value", "extracted", "raw")))
            if nested is not None:
                return nested
            continue
        text = as_text(value)
        if not text:
            continue
        match = _PRICE_RE.search(text.replace(",", ""))
        if match:
            try:
                return float(match.group())
            except ValueError:
                continue
    return None


def as_int(*candidates: Any) -> int | None:
    value = as_float(*candidates)
    if value is None:
        return None
    # "22,200" style review counts and "22K" both arrive here; the K/M suffix
    # loses magnitude, so recover it from the raw text.
    for candidate in candidates:
        text = as_text(candidate).upper()
        if text and value and re.search(r"\d\s*K\b", text):
            value *= 1000
            break
        if text and value and re.search(r"\d\s*M\b", text):
            value *= 1_000_000
            break
    return int(value)


def first_link(item: dict[str, Any]) -> str:
    """Prefer a link that lands on the retailer over one that lands on Google."""
    for key in (
        "direct_link",
        "link_clean",
        "link",
        "product_link",
        "offers_link",
        "serpapi_product_api",
    ):
        link = as_text(item.get(key))
        if link.startswith("http"):
            return link
    return ""


def parse_google_product(item: dict[str, Any]) -> Product:
    extras = [e for e in (as_text(x) for x in (item.get("extensions") or [])) if e]
    if item.get("tag"):
        extras.insert(0, as_text(item["tag"]))
    return Product(
        title=as_text(item.get("title"), 160) or "Untitled product",
        link=first_link(item),
        store=as_text(item.get("source") or item.get("seller") or item.get("store"), 40),
        price_display=as_text(item.get("price")),
        price_value=as_float(item.get("extracted_price"), item.get("price")),
        old_price_display=as_text(item.get("old_price")),
        rating=as_float(item.get("rating")),
        reviews=as_int(item.get("reviews")),
        thumbnail=as_text(item.get("thumbnail") or item.get("serpapi_thumbnail")),
        delivery=as_text(item.get("delivery"), 70),
        snippet=as_text(item.get("snippet"), 180),
        sponsored=bool(item.get("sponsored")),
        extras=extras[:3],
    )


def parse_amazon_product(item: dict[str, Any]) -> Product:
    extras = [e for e in (as_text(x) for x in (item.get("tags") or [])) if e]
    if item.get("bought_last_month"):
        extras.insert(0, as_text(item["bought_last_month"]))
    return Product(
        title=as_text(item.get("title"), 160) or "Untitled product",
        link=first_link(item),
        store="Amazon",
        price_display=as_text(item.get("price")),
        price_value=as_float(item.get("extracted_price"), item.get("price")),
        old_price_display=as_text(item.get("old_price") or item.get("list_price")),
        rating=as_float(item.get("rating")),
        reviews=as_int(item.get("reviews")),
        thumbnail=as_text(item.get("thumbnail")),
        delivery=as_text(item.get("delivery"), 70),
        snippet=as_text(item.get("options") or item.get("snippet"), 180),
        sponsored=bool(item.get("sponsored")),
        extras=extras[:3],
    )
