"""Turn a chat message into an intent and a `SearchPlan`."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Sequence

from vacuole.domain.models import ChatTurn, SearchPlan, Sort, UserLocation
from vacuole.pipeline.prompts import UNDERSTAND_PROMPT
from vacuole.ports import TextModel

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_NUMBER_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(k|lakh|lac|l|cr|crore|m)?", re.IGNORECASE)
_MULTIPLIERS = {
    "k": 1_000,
    "m": 1_000_000,
    "lakh": 100_000,
    "lac": 100_000,
    "l": 100_000,
    "cr": 10_000_000,
    "crore": 10_000_000,
}

# The words an LLM might use for each sort, mapped to our sort keys.
_SORT_ALIASES: dict[Sort, set[str]] = {
    "price_asc": {"price_asc", "cheapest", "low_to_high", "price"},
    "price_desc": {"price_desc", "expensive", "high_to_low", "premium"},
    "rating": {"rating", "best", "top_rated", "reviews"},
}

_SEARCH_HINTS = (
    "buy", "price", "cheap", "under", "best", "compare", "deal", "discount",
    "search", "find", "shop", "offer", "available",
)


def render_history(history: Sequence[ChatTurn] | None, limit: int) -> str:
    if not history:
        return "(no earlier messages)"
    lines = []
    for turn in list(history)[-limit:]:
        content = turn.content.strip().replace("\n", " ")
        if content:
            role = "User" if turn.role == "user" else "Assistant"
            lines.append(f"{role}: {content[:220]}")
    return "\n".join(lines) or "(no earlier messages)"


def coerce_price(value: Any) -> float | None:
    """Accept 2000, "2000", "₹2,000", "20k", "2 lakh"."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None

    text = str(value).strip().lower().replace(",", "")
    if not text or text in {"null", "none", "na", "-"}:
        return None
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    try:
        amount = float(match.group(1))
    except ValueError:
        return None
    amount *= _MULTIPLIERS.get((match.group(2) or "").lower(), 1)
    return amount if amount > 0 else None


def parse_plan_json(raw: str) -> dict[str, Any]:
    """Pull the JSON object out of an LLM reply that may be wrapped in prose."""
    if not raw:
        return {}
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", candidate).strip()
    match = _JSON_RE.search(candidate)
    if not match:
        return {}
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1"}


def normalise_sort(value: Any) -> Sort:
    text = str(value or "").strip().lower()
    for sort, aliases in _SORT_ALIASES.items():
        if text in aliases:
            return sort
    return "relevance"


def looks_like_search(text: str) -> bool:
    """Keyword fallback for when the planner call fails outright."""
    lowered = text.lower()
    return any(hint in lowered for hint in _SEARCH_HINTS)


@dataclass
class PlannedRequest:
    intent: str          # "search" or "chat"
    plan: SearchPlan


class QueryPlanner:
    """One fast model call that both routes the request and plans the search."""

    def __init__(self, model: TextModel, *, history_limit: int = 6):
        self._model = model
        self._history_limit = history_limit

    async def plan(
        self, user_input: str, history: Sequence[ChatTurn], location: UserLocation
    ) -> PlannedRequest:
        prompt = UNDERSTAND_PROMPT.format(
            history=render_history(history, self._history_limit),
            user_input=user_input,
            location=location.label,
        )

        raw = ""
        try:
            raw = await self._model.complete(prompt)
        except Exception as exc:  # the planner must never hard-fail the request
            print(f"[planner] call failed: {exc}")

        data = parse_plan_json(raw)
        user_input = (user_input or "").strip()

        intent = "search" if str(data.get("intent", "")).lower().startswith("search") else "chat"
        query = str(data.get("query") or "").strip()

        if intent == "search" and not query:
            # Planner produced nothing usable; search the raw message rather than give up.
            query = user_input
        if not data and looks_like_search(user_input):
            intent, query = "search", user_input

        plan = SearchPlan(
            query=query,
            min_price=coerce_price(data.get("min_price")),
            max_price=coerce_price(data.get("max_price")),
            sort=normalise_sort(data.get("sort")),
            free_shipping=as_bool(data.get("free_shipping")),
            on_sale=as_bool(data.get("on_sale")),
            stores=[str(s) for s in (data.get("stores") or []) if str(s).strip()],
        )
        return PlannedRequest(intent=intent, plan=plan)
