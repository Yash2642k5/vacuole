"""/start and /help."""

from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import BaseHandler, CommandHandler, ContextTypes

from vacuole.bot.formatting import esc
from vacuole.bot.keyboards import location_request_keyboard
from vacuole.bot.session import LocationTracker, UserSession


class BasicCommands:
    def __init__(self, locations: LocationTracker):
        self._locations = locations

    def handlers(self) -> list[BaseHandler]:
        return [
            CommandHandler("start", self.start),
            CommandHandler("help", self.help),
        ]

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        name = esc(update.effective_user.first_name or "there")
        await update.message.reply_text(
            f"👋 Hi {name}, I'm <b>Vacuole</b> — your shopping assistant.\n\n"
            "Tell me what you're after and I'll compare live prices across stores:\n"
            "• <i>wireless earbuds under 2000</i>\n"
            "• <i>best air fryer with good reviews</i>\n"
            "• <i>price of iPhone 16 128gb</i>\n\n"
            "📍 Share your location for local prices and delivery times — "
            "otherwise I search across <b>India</b>.",
            parse_mode=ParseMode.HTML,
            reply_markup=location_request_keyboard(),
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        location = await self._locations.current(
            UserSession(context.user_data), update.effective_user.id
        )
        await update.message.reply_text(
            "<b>How to use me</b>\n\n"
            "Just describe the product. Add a budget (<i>under 3000</i>), a brand, "
            "or ask for the <i>cheapest</i> or <i>best rated</i>.\n\n"
            "<b>Commands</b>\n"
            "/start — start over\n"
            "/location — set where you shop from\n"
            "/help — this message\n\n"
            f"Currently searching from: <b>{esc(location.label)}</b>",
            parse_mode=ParseMode.HTML,
        )
