"""SerpApi's locations API as a `PlaceLookup`."""

from __future__ import annotations

from typing import Any

from vacuole.adapters.serpapi.client import LOCATIONS_ENDPOINT, SerpApiClient


class SerpApiPlaceLookup:
    def __init__(self, client: SerpApiClient):
        self._client = client

    async def find(self, query: str) -> dict[str, Any] | None:
        """Resolve a free-text place into a SerpApi canonical location."""
        data = await self._client.get({"q": query, "limit": 5}, endpoint=LOCATIONS_ENDPOINT)
        results = data.get("results") if isinstance(data, dict) else None
        if isinstance(results, list) and results:
            return results[0] if isinstance(results[0], dict) else None
        return None
