"""Deterministic HTML rendering of products for Telegram.

Everything the user sees is built from structured `Product` rows, so the output never
depends on an LLM formatting things correctly.
"""

from __future__ import annotations

import html
from typing import Iterable, Sequence

from vacuole.domain.models import Product

CAPTION_LIMIT = 1024
MESSAGE_LIMIT = 4096
NUMBER_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=False)


def clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def bullet(index: int) -> str:
    return NUMBER_EMOJI[index] if index < len(NUMBER_EMOJI) else f"{index + 1}."


def _price_line(product: Product) -> str:
    if not product.price_display:
        return "💰 <i>Price not listed</i>"
    line = f"💰 <b>{esc(product.price_display)}</b>"
    if product.old_price_display and product.old_price_display != product.price_display:
        line += f"  <s>{esc(product.old_price_display)}</s>"
    return line


def _compact_count(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M".replace(".0M", "M")
    if value >= 1_000:
        return f"{value / 1_000:.1f}K".replace(".0K", "K")
    return str(value)


def _rating_line(product: Product) -> str:
    if product.rating is None:
        return ""
    # One decimal always, so a 4.0 does not render as a bare "4" beside a 4.3.
    stars = f"⭐ {product.rating:.1f}"
    if product.reviews:
        stars += f" · {_compact_count(product.reviews)} reviews"
    return stars


def _currency_of(products: Iterable[Product]) -> str:
    for product in products:
        display = product.price_display
        if display:
            symbol = "".join(ch for ch in display if not ch.isdigit() and ch not in ",. ")
            if symbol:
                return symbol[:3]
    return ""


def format_results_summary(
    products: Sequence[Product],
    query: str,
    location_display: str,
    *,
    note: str = "",
) -> str:
    """The one message that lists every hit, compactly."""
    plural = "es" if len(products) != 1 else ""
    lines = [f"🛍 <b>{len(products)} match{plural} for “{esc(clip(query, 70))}”</b>"]

    priced = [p.price_value for p in products if p.price_value is not None]
    meta = [location_display]
    if priced:
        low, high = min(priced), max(priced)
        currency = _currency_of(products)
        if low != high:
            meta.append(f"{currency}{low:,.0f} – {currency}{high:,.0f}")
        else:
            meta.append(f"{currency}{low:,.0f}")
    lines.append(" · ".join(esc(m) for m in meta if m))

    if note:
        lines.append(f"\n💬 <i>{esc(clip(note, 320))}</i>")

    lines.append("")
    for index, product in enumerate(products):
        lines.append(f"{bullet(index)} <b>{esc(clip(product.title, 72))}</b>")

        detail_bits = [esc(product.price_display), esc(product.store)]
        rating = _rating_line(product)
        if rating:
            detail_bits.append(rating)  # already safe, built from numbers
        if product.offers:
            count = len(product.offers)
            detail_bits.append(f"+{count} more store{'s' if count > 1 else ''}")
        detail = " · ".join(bit for bit in detail_bits if bit)
        if detail:
            lines.append(f"      {detail}")

    lines.append("\n<i>Tap a number below for details and the buy link.</i>")
    return clip("\n".join(lines), MESSAGE_LIMIT)


def format_product_card(product: Product, index: int, *, total: int = 0) -> str:
    """Full detail for one product, used as a photo caption."""
    lines = [f"{bullet(index)} <b>{esc(clip(product.title, 140))}</b>", "", _price_line(product)]

    if product.store:
        lines.append(f"🏪 {esc(product.store)}")
    rating = _rating_line(product)
    if rating:
        lines.append(rating)
    if product.delivery:
        lines.append(f"🚚 {esc(product.delivery)}")
    if product.extras:
        lines.append(f"🏷 {esc(' · '.join(product.extras))}")
    if product.offers:
        alternatives = " · ".join(
            f"{esc(offer.get('store'))} {esc(offer.get('price'))}".strip()
            for offer in product.offers[:3]
        )
        lines.append(f"🔁 Also at: {alternatives}")
    if product.snippet:
        lines.append(f"\nℹ️ <i>{esc(product.snippet)}</i>")
    if total:
        lines.append(f"\n<i>Result {index + 1} of {total}</i>")

    return clip("\n".join(lines), CAPTION_LIMIT)


def links_message(products: Sequence[Product]) -> str:
    lines = ["🔗 <b>All links</b>", ""]
    for index, product in enumerate(products):
        title = esc(clip(product.title, 55))
        price = f" — {esc(product.price_display)}" if product.price_display else ""
        if product.link:
            lines.append(f'{bullet(index)} <a href="{esc(product.link)}">{title}</a>{price}')
        else:
            lines.append(f"{bullet(index)} {title}{price}")
    return clip("\n".join(lines), MESSAGE_LIMIT)


def transcript_for_history(query: str, products: Sequence[Product], note: str) -> str:
    """A compact plain-text record of what was shown, for conversation memory."""
    lines = [f"Showed {len(products)} results for '{query}':"]
    for product in products[:6]:
        bits = [product.title, product.price_display, product.store]
        lines.append(" - " + " | ".join(bit for bit in bits if bit))
    if note:
        lines.append(note)
    return "\n".join(lines)
