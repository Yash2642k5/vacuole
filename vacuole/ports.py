"""The interfaces the application depends on.

Pipeline, services and bot code import these Protocols, never a concrete vendor class.
Adapters (Firestore, SerpApi, Groq, Nominatim) satisfy them structurally, and
`app.py` is the only place that picks which implementation to plug in.
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence

from vacuole.domain.models import (
    AssistantReply,
    ChatTurn,
    Product,
    SearchOutcome,
    SearchPlan,
    UserLocation,
)


class TextModel(Protocol):
    """Anything that turns a prompt into text."""

    async def complete(self, prompt: str) -> str: ...


class ProgressReporter(Protocol):
    """Receives named milestones while a request is processed."""

    async def step(self, key: str, detail: str = "") -> None: ...


class SearchEngine(Protocol):
    """One product source. Add a source by adding a class, not by editing the aggregator."""

    name: str

    def applies_to(self, plan: SearchPlan) -> bool: ...

    async def search(self, plan: SearchPlan, location: UserLocation) -> list[Product]: ...


class ProductSearch(Protocol):
    async def search(
        self, plan: SearchPlan, location: UserLocation, limit: int | None = None
    ) -> SearchOutcome: ...


class Assistant(Protocol):
    async def reply(
        self,
        user_input: str,
        *,
        history: Sequence[ChatTurn],
        location: UserLocation,
        progress: ProgressReporter | None = None,
    ) -> AssistantReply: ...


class ChatHistoryStore(Protocol):
    async def recent(self, user_id: str | int, limit: int) -> list[ChatTurn]: ...

    async def append(self, user_id: str | int, role: str, content: str) -> None: ...


class LocationStore(Protocol):
    async def load(self, user_id: str | int) -> UserLocation | None: ...

    async def save(self, user_id: str | int, location: UserLocation) -> None: ...


class ReverseGeocoder(Protocol):
    async def reverse(self, latitude: float, longitude: float) -> dict[str, Any] | None:
        """Return an address mapping (city, state, country, country_code, ...) or None."""
        ...


class PlaceLookup(Protocol):
    async def find(self, query: str) -> dict[str, Any] | None:
        """Return the best canonical match for free text like "Pune", or None."""
        ...
