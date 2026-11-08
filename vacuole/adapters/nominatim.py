"""OpenStreetMap Nominatim reverse geocoding as a `ReverseGeocoder`."""

from __future__ import annotations

from typing import Any

import httpx

NOMINATIM_ENDPOINT = "https://nominatim.openstreetmap.org/reverse"
GEOCODE_TIMEOUT = 8.0


class NominatimGeocoder:
    def __init__(self, timeout: float = GEOCODE_TIMEOUT):
        self._timeout = timeout

    async def reverse(self, latitude: float, longitude: float) -> dict[str, Any] | None:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    NOMINATIM_ENDPOINT,
                    params={
                        "lat": f"{latitude:.6f}",
                        "lon": f"{longitude:.6f}",
                        "format": "jsonv2",
                        "zoom": 10,
                        "addressdetails": 1,
                    },
                    headers={
                        # Nominatim requires an identifying User-Agent.
                        "User-Agent": "vacuole-ecommerce-assistant/1.0 (telegram shopping bot)",
                        "Accept-Language": "en",
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None

        address = payload.get("address") if isinstance(payload, dict) else None
        return address if isinstance(address, dict) else None
