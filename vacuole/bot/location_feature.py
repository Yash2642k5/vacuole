"""Setting where the user shops from: /location <city> and shared pins."""

from __future__ import annotations

from telegram import ReplyKeyboardRemove, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import BaseHandler, CommandHandler, ContextTypes, MessageHandler, filters

from vacuole.bot.formatting import esc
from vacuole.bot.keyboards import location_request_keyboard
from vacuole.bot.session import LocationTracker, UserSession
from vacuole.domain.models import DEFAULT_LOCATION
from vacuole.services.location import LocationService


class LocationFeature:
    def __init__(self, service: LocationService, tracker: LocationTracker):
        self._service = service
        self._tracker = tracker

    def handlers(self) -> list[BaseHandler]:
        return [
            CommandHandler(["location", "setlocation"], self.location_command),
            MessageHandler(filters.LOCATION, self.handle_pin),
        ]

    async def handle_pin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """A shared pin arrives as latitude/longitude; turn it into a search location."""
        message = update.message
        if message is None or message.location is None:
            return

        placeholder = await message.reply_text(
            "📍 <i>Pinning you down…</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardRemove(),
        )

        location = await self._service.from_coordinates(
            message.location.latitude, message.location.longitude
        )

        if location.source == "live":
            await self._tracker.remember(
                UserSession(context.user_data), update.effective_user.id, location
            )
            text = (
                f"✅ Got it — searching from <b>{esc(location.label)}</b>.\n\n"
                "Prices, delivery estimates and store availability will match this area."
            )
        else:
            text = (
                "I couldn't work out your city from that pin, so I'll keep using "
                f"<b>{esc(DEFAULT_LOCATION.label)}</b>.\n\n"
                "You can also type <code>/location Mumbai</code>."
            )

        try:
            await placeholder.edit_text(text, parse_mode=ParseMode.HTML)
        except BadRequest:
            await message.reply_text(text, parse_mode=ParseMode.HTML)

    async def location_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/location shows the current one, /location <city> sets it."""
        user_id = update.effective_user.id
        session = UserSession(context.user_data)
        typed = " ".join(context.args or []).strip()

        if not typed:
            location = await self._tracker.current(session, user_id)
            await update.message.reply_text(
                f"Right now I'm shopping from <b>{esc(location.label)}</b>.\n\n"
                "Share your live location for local prices and delivery, "
                "or type <code>/location Bengaluru</code>.",
                parse_mode=ParseMode.HTML,
                reply_markup=location_request_keyboard(),
            )
            return

        resolved = await self._service.from_text(typed)
        if resolved is None:
            await update.message.reply_text(
                f"I couldn't find “{esc(typed)}”. Try a bigger city nearby, "
                "or just share your location.",
                parse_mode=ParseMode.HTML,
                reply_markup=location_request_keyboard(),
            )
            return

        await self._tracker.remember(session, user_id, resolved)
        await update.message.reply_text(
            f"✅ Searching from <b>{esc(resolved.label)}</b> from now on.",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardRemove(),
        )
