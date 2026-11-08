"""Free-text messages: run the assistant and render its reply."""

from __future__ import annotations

import asyncio

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import BaseHandler, ContextTypes, MessageHandler, filters

from vacuole.bot import formatting
from vacuole.bot.keyboards import results_keyboard
from vacuole.bot.progress import ProgressTracker
from vacuole.bot.session import LocationTracker, UserSession
from vacuole.domain.models import AssistantReply, UserLocation
from vacuole.ports import Assistant, ChatHistoryStore


class ChatFeature:
    def __init__(
        self,
        assistant: Assistant,
        history: ChatHistoryStore,
        locations: LocationTracker,
        *,
        bot_username: str = "",
        history_limit: int = 10,
    ):
        self._assistant = assistant
        self._history = history
        self._locations = locations
        self._bot_username = bot_username
        self._history_limit = history_limit

    def handlers(self) -> list[BaseHandler]:
        return [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)]

    def _addressed_text(self, update: Update) -> str | None:
        """The message text to act on, or None when the bot should stay quiet."""
        message = update.message
        if message is None or not message.text:
            return None

        text = message.text.strip()
        # In groups, only answer when addressed.
        if message.chat.type in ("group", "supergroup"):
            if not (self._bot_username and self._bot_username in text):
                return None
            text = text.replace(self._bot_username, "").strip()
        return text or None

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = self._addressed_text(update)
        if text is None:
            return

        message = update.message
        user_id = update.effective_user.id
        session = UserSession(context.user_data)

        await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)

        progress = await ProgressTracker.start(update, title=text)
        location, history = await asyncio.gather(
            self._locations.current(session, user_id),
            self._history.recent(user_id, self._history_limit),
        )

        reply = await self._assistant.reply(
            text, history=history, location=location, progress=progress
        )

        if reply.notice:
            print(f"[search] partial failure: {reply.notice}")

        await progress.finish()
        if reply.kind == "products" and reply.products:
            await self._send_results(update, session, reply, location)
            transcript = formatting.transcript_for_history(reply.query, reply.products, reply.text)
        else:
            await message.reply_text(
                reply.text or "I don't have an answer for that.",
                parse_mode=ParseMode.HTML if "<" in reply.text else None,
            )
            transcript = reply.text

        await asyncio.gather(
            self._history.append(user_id, "user", text),
            self._history.append(user_id, "assistant", transcript),
        )

    @staticmethod
    async def _send_results(
        update: Update, session: UserSession, reply: AssistantReply, location: UserLocation
    ) -> None:
        """Post the summary card and stash the rows for the inline buttons."""
        session.store_results(reply.products, reply.query, location.display)
        await update.message.reply_text(
            formatting.format_results_summary(
                reply.products, reply.query, location.display, note=reply.text
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=results_keyboard(reply.products),
            disable_web_page_preview=True,
        )
