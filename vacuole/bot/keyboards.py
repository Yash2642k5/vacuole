"""Telegram keyboards. Callback payloads here must match the actions in callbacks.py."""

from __future__ import annotations

from typing import Sequence

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from vacuole.bot.formatting import bullet, clip
from vacuole.domain.models import Product
from vacuole.domain.ranking import button_options

PRODUCT_PREFIX = "prod:"
SORT_PREFIX = "sort:"
LINKS_DATA = "links"
BACK_DATA = "back"


def results_keyboard(products: Sequence[Product]) -> InlineKeyboardMarkup:
    """Number buttons for each hit, plus sort and re-search shortcuts."""
    buttons = [
        InlineKeyboardButton(bullet(i), callback_data=f"{PRODUCT_PREFIX}{i}")
        for i in range(len(products))
    ]
    rows = [buttons[start : start + 4] for start in range(0, len(buttons), 4)]

    rows.append(
        [
            InlineKeyboardButton(option.button, callback_data=f"{SORT_PREFIX}{option.key}")
            for option in button_options()
        ]
    )
    rows.append([InlineKeyboardButton("🔗 Open all links", callback_data=LINKS_DATA)])
    return InlineKeyboardMarkup(rows)


def product_keyboard(product: Product, index: int, total: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    if product.link:
        label = f"🛒 Buy on {product.store}" if product.store else "🛒 View product"
        rows.append([InlineKeyboardButton(clip(label, 30), url=product.link)])

    nav: list[InlineKeyboardButton] = []
    if index > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"{PRODUCT_PREFIX}{index - 1}"))
    if index + 1 < total:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"{PRODUCT_PREFIX}{index + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("📋 Back to all results", callback_data=BACK_DATA)])
    return InlineKeyboardMarkup(rows)


def location_request_keyboard() -> ReplyKeyboardMarkup:
    """One-tap live location share."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📍 Share my location", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Or just type a city name",
    )
