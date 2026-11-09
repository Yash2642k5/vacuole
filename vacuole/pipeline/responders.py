"""Produce the words of a reply: a one-line result note, or a plain chat answer."""

from __future__ import annotations

from typing import Sequence

from vacuole.domain.models import ChatTurn, Product, SearchOutcome, SearchPlan
from vacuole.pipeline.planner import render_history
from vacuole.pipeline.prompts import CHAT_PROMPT, NOTE_PROMPT
from vacuole.ports import TextModel

CHAT_FAILURE_TEXT = "I'm having trouble thinking right now — could you say that again?"
OFF_TOPIC_TEXT = (
    "I can only help with shopping and product questions. Tell me what you're looking "
    "for — e.g. “best earbuds under 2000” — and I'll find and compare options."
)


class ResultNarrator:
    """One short remark about a result set. Cards themselves are rendered in code."""

    def __init__(self, model: TextModel, *, digest_size: int = 6):
        self._model = model
        self._digest_size = digest_size

    async def note(self, query: str, products: Sequence[Product]) -> str:
        digest = "\n".join(
            f"- {p.title} | {p.price_display or 'price n/a'} | {p.store or 'unknown store'}"
            f" | rating {p.rating if p.rating is not None else 'n/a'}"
            for p in products[: self._digest_size]
        )
        try:
            text = await self._model.complete(NOTE_PROMPT.format(query=query, digest=digest))
        except Exception as exc:
            print(f"[narrator] note call failed: {exc}")
            return ""
        return " ".join(text.split())[:300]


class ChatResponder:
    """Answers questions that need no product data."""

    def __init__(self, model: TextModel, *, history_limit: int = 6):
        self._model = model
        self._history_limit = history_limit

    async def respond(self, user_input: str, history: Sequence[ChatTurn]) -> str:
        prompt = CHAT_PROMPT.format(
            history=render_history(history, self._history_limit),
            user_input=user_input,
        )
        try:
            text = (await self._model.complete(prompt)).strip()
        except Exception as exc:
            print(f"[chat] all models failed: {exc}")
            text = ""
        return text or CHAT_FAILURE_TEXT


def no_results_message(plan: SearchPlan, outcome: SearchOutcome) -> str:
    if outcome.errors and not outcome.engines_used:
        return (
            "I couldn't reach the product search just now. Please try again in a moment — "
            "if it keeps failing, the SerpApi key or quota may need a look."
        )
    bounds = []
    if plan.min_price:
        bounds.append(f"above {plan.min_price:,.0f}")
    if plan.max_price:
        bounds.append(f"below {plan.max_price:,.0f}")
    limit = f" {' and '.join(bounds)}" if bounds else ""
    return (
        f"I found nothing for “{plan.query}”{limit}. Try a broader description, "
        "a different brand, or a wider budget."
    )
