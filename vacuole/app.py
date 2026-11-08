"""Composition root: the only module that knows which concrete classes are in use.

Swapping Firestore for another store, Groq for another model, or adding a search
engine is a change here and nowhere else.
"""

from __future__ import annotations

from typing import Protocol

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import Application, BaseHandler, ContextTypes

from vacuole.adapters.firestore import (
    FirestoreChatHistory,
    FirestoreLocationStore,
    create_firestore_client,
)
from vacuole.adapters.llm import FallbackTextModel, LangChainTextModel
from vacuole.adapters.nominatim import NominatimGeocoder
from vacuole.adapters.serpapi.client import SerpApiClient
from vacuole.adapters.serpapi.engines import AmazonEngine, GoogleShoppingEngine
from vacuole.adapters.serpapi.places import SerpApiPlaceLookup
from vacuole.bot.callbacks import ResultsCallbacks
from vacuole.bot.chat_feature import ChatFeature
from vacuole.bot.commands import BasicCommands
from vacuole.bot.location_feature import LocationFeature
from vacuole.bot.session import LocationTracker
from vacuole.config import Settings
from vacuole.pipeline.assistant import ShoppingAssistant
from vacuole.pipeline.planner import QueryPlanner
from vacuole.pipeline.responders import ChatResponder, ResultNarrator
from vacuole.services.location import LocationService
from vacuole.services.product_search import ProductSearchService


class Feature(Protocol):
    def handlers(self) -> list[BaseHandler]: ...


def build_assistant(settings: Settings, serp: SerpApiClient) -> ShoppingAssistant:
    from langchain_groq import ChatGroq

    # Fast, cheap model for routing, planning and the short result note. Every call on
    # the hot path uses this one; latency here is what the user feels.
    fast = LangChainTextModel(
        ChatGroq(
            model=settings.fast_model,
            temperature=0,
            max_retries=2,
            api_key=settings.groq_api_key,
        )
    )
    chat = FallbackTextModel(
        LangChainTextModel(
            ChatGroq(
                model=settings.chat_model,
                temperature=0.4,
                max_retries=2,
                api_key=settings.groq_chat_api_key,
            )
        ),
        fast,
        name="chat",
    )

    search = ProductSearchService(
        [GoogleShoppingEngine(serp), AmazonEngine(serp)],
        default_limit=settings.max_products,
    )
    return ShoppingAssistant(
        planner=QueryPlanner(fast, history_limit=settings.max_history_messages),
        search=search,
        narrator=ResultNarrator(fast),
        responder=ChatResponder(chat, history_limit=settings.max_history_messages),
    )


async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"[error] update {update} caused {context.error}")
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Something broke on my side. Please try that again."
            )
        except TelegramError:
            pass


def build_application(settings: Settings) -> Application:
    db = create_firestore_client(settings.firebase_credentials)
    serp = SerpApiClient(settings.serpapi_api_key)

    locations = LocationService(
        NominatimGeocoder(), SerpApiPlaceLookup(serp), FirestoreLocationStore(db)
    )
    tracker = LocationTracker(locations)

    # Order matters: handlers are matched first-come, first-served.
    features: list[Feature] = [
        BasicCommands(tracker),
        LocationFeature(locations, tracker),
        ResultsCallbacks(),
        ChatFeature(
            build_assistant(settings, serp),
            FirestoreChatHistory(db),
            tracker,
            bot_username=settings.bot_username,
            history_limit=settings.history_limit,
        ),
    ]

    async def on_shutdown(_: Application) -> None:
        await serp.aclose()

    application = (
        Application.builder().token(settings.telegram_token).post_shutdown(on_shutdown).build()
    )
    for feature in features:
        for handler in feature.handlers():
            application.add_handler(handler)
    application.add_error_handler(_on_error)
    return application


def main() -> None:
    import nest_asyncio

    nest_asyncio.apply()
    settings = Settings.from_env()
    if not settings.telegram_token:
        raise SystemExit("TOKEN is not set in the environment.")

    try:
        application = build_application(settings)
    except Exception as exc:
        raise SystemExit(f"Could not start: {exc}") from exc

    if settings.webhook_url:
        print(f"starting bot on webhook {settings.webhook_url}")
        application.run_webhook(
            listen="0.0.0.0",
            port=settings.port,
            url_path=settings.telegram_token,
            webhook_url=f"{settings.webhook_url.rstrip('/')}/{settings.telegram_token}",
        )
    else:
        # No tunnel configured: long polling works anywhere, including locally.
        print("starting bot on long polling (set WEBHOOK_URL to use a webhook)")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
