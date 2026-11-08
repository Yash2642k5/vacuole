"""Inline-button handling.

Each button type is a `CallbackAction`. To add a button, write an action and add it to
the list given to `ResultsCallbacks` (see `default_actions`); the router never changes.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from telegram import InputMediaPhoto, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import BaseHandler, CallbackQueryHandler, ContextTypes

from vacuole.bot import formatting
from vacuole.bot.keyboards import (
    BACK_DATA,
    LINKS_DATA,
    PRODUCT_PREFIX,
    SORT_PREFIX,
    product_keyboard,
    results_keyboard,
)
from vacuole.bot.session import UserSession
from vacuole.domain.models import Product
from vacuole.domain.ranking import get_sort_option


class CallbackAction(Protocol):
    def matches(self, data: str) -> bool: ...

    async def handle(self, query, session: UserSession, data: str) -> None: ...


class ShowProduct:
    """Prev/Next/number buttons: show one product card."""

    def matches(self, data: str) -> bool:
        return data.startswith(PRODUCT_PREFIX)

    async def handle(self, query, session: UserSession, data: str) -> None:
        try:
            index = int(data[len(PRODUCT_PREFIX):])
        except ValueError:
            return
        products = session.products
        if 0 <= index < len(products):
            await self._show(query, products[index], index, len(products))

    @staticmethod
    async def _show(query, product: Product, index: int, total: int) -> None:
        """Show one card, editing the current card in place when it is also a photo."""
        caption = formatting.format_product_card(product, index, total=total)
        keyboard = product_keyboard(product, index, total)
        message = query.message

        # Prev/Next on an existing photo card: swap the media, no new message.
        if message is not None and message.photo and product.thumbnail:
            try:
                await message.edit_media(
                    media=InputMediaPhoto(
                        media=product.thumbnail, caption=caption, parse_mode=ParseMode.HTML
                    ),
                    reply_markup=keyboard,
                )
                return
            except (BadRequest, TelegramError) as exc:
                print(f"[card] media edit failed, sending fresh: {exc}")

        if message is not None and message.photo:
            try:
                await message.delete()
            except TelegramError:
                pass

        if product.thumbnail:
            try:
                await query.message.chat.send_photo(
                    photo=product.thumbnail,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                )
                return
            except (BadRequest, TelegramError) as exc:
                # Some CDN thumbnails refuse Telegram's fetch; fall back to text.
                print(f"[card] photo send failed: {exc}")

        await query.message.chat.send_message(
            caption,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )


class ResortResults:
    """Re-order the rows we already have; no second API call, so it is instant."""

    def matches(self, data: str) -> bool:
        return data.startswith(SORT_PREFIX)

    async def handle(self, query, session: UserSession, data: str) -> None:
        option = get_sort_option(data[len(SORT_PREFIX):])
        ordered = option.sort(session.products)
        session.products = ordered

        try:
            await query.message.edit_text(
                formatting.format_results_summary(
                    ordered,
                    session.query,
                    session.location_display,
                    note=f"Sorted by {option.label}.",
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=results_keyboard(ordered),
                disable_web_page_preview=True,
            )
        except BadRequest as exc:
            if "not modified" not in str(exc).lower():
                print(f"[sort] edit failed: {exc}")


class OpenLinks:
    def matches(self, data: str) -> bool:
        return data == LINKS_DATA

    async def handle(self, query, session: UserSession, data: str) -> None:
        await query.message.reply_text(
            formatting.links_message(session.products),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )


class DismissCard:
    def matches(self, data: str) -> bool:
        return data == BACK_DATA

    async def handle(self, query, session: UserSession, data: str) -> None:
        try:
            await query.message.delete()
        except TelegramError:
            pass


def default_actions() -> list[CallbackAction]:
    return [ShowProduct(), ResortResults(), OpenLinks(), DismissCard()]


class ResultsCallbacks:
    def __init__(self, actions: Sequence[CallbackAction] | None = None):
        self._actions = list(actions) if actions is not None else default_actions()

    def handlers(self) -> list[BaseHandler]:
        return [CallbackQueryHandler(self.handle_callback)]

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None:
            return

        session = UserSession(context.user_data)

        # A callback may only be answered once, so the expiry alert has to come first:
        # results live in user_data and are lost when the bot restarts.
        if not session.products:
            await query.answer("That search has expired — send me a new one.", show_alert=True)
            return

        await query.answer()

        data = query.data or ""
        for action in self._actions:
            if action.matches(data):
                await action.handle(query, session, data)
                return
