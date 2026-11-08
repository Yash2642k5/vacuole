"""HTTP transport for SerpApi. Knows nothing about products or engines."""

from __future__ import annotations

from typing import Any

import httpx

from vacuole.adapters.serpapi.parsing import as_text
from vacuole.domain.errors import ProviderError

SEARCH_ENDPOINT = "https://serpapi.com/search.json"
LOCATIONS_ENDPOINT = "https://serpapi.com/locations.json"

# A single search should never hold the user hostage; we would rather return
# whatever one engine managed to deliver.
REQUEST_TIMEOUT = 18.0


class SerpApiError(ProviderError):
    """SerpApi is unreachable, unauthorised or returned an error payload."""


class SerpApiClient:
    def __init__(self, api_key: str, *, timeout: float = REQUEST_TIMEOUT):
        self._api_key = api_key
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        """Lazily build one shared client so connections are reused between searches."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                headers={"User-Agent": "vacuole-ecommerce-assistant/1.0"},
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    async def get(
        self, params: dict[str, Any], endpoint: str = SEARCH_ENDPOINT
    ) -> dict[str, Any]:
        if not self._api_key:
            raise SerpApiError("SERPAPI_API_KEY is not set in the environment.")

        payload = {k: v for k, v in params.items() if v not in (None, "", [])}
        payload["api_key"] = self._api_key

        try:
            response = await self._http().get(endpoint, params=payload)
        except httpx.TimeoutException as exc:
            raise SerpApiError(f"SerpApi timed out after {self._timeout:.0f}s.") from exc
        except httpx.HTTPError as exc:
            raise SerpApiError(f"Could not reach SerpApi: {exc}") from exc

        if response.status_code == 401:
            raise SerpApiError("SerpApi rejected the API key (401).")
        if response.status_code == 429:
            raise SerpApiError("SerpApi search quota exhausted (429).")

        try:
            data = response.json()
        except ValueError as exc:
            raise SerpApiError(
                f"SerpApi returned non-JSON (HTTP {response.status_code})."
            ) from exc

        if isinstance(data, dict) and data.get("error"):
            raise SerpApiError(as_text(data["error"]))
        if response.status_code >= 400:
            raise SerpApiError(f"SerpApi returned HTTP {response.status_code}.")
        return data if isinstance(data, dict) else {"results": data}
