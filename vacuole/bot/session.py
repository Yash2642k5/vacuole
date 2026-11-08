"""Per-user state kept in Telegram's `context.user_data`, behind named accessors."""

from __future__ import annotations

from typing import Any, MutableMapping

from vacuole.domain.models import DEFAULT_LOCATION, Product, UserLocation
from vacuole.services.location import LocationService


class UserSession:
    """Typed view over `context.user_data`, so handlers never touch raw string keys."""

    def __init__(self, data: MutableMapping[str, Any]):
        self._data = data

    # -- last search results ------------------------------------------------

    @property
    def products(self) -> list[Product]:
        return [Product.from_dict(row) for row in self._data.get("results", [])]

    @products.setter
    def products(self, products: list[Product]) -> None:
        self._data["results"] = [p.to_dict() for p in products]

    @property
    def query(self) -> str:
        return self._data.get("query", "")

    @property
    def location_display(self) -> str:
        return self._data.get("location_display", DEFAULT_LOCATION.display)

    def store_results(
        self, products: list[Product], query: str, location_display: str
    ) -> None:
        self.products = products
        self._data["query"] = query
        self._data["location_display"] = location_display

    # -- location cache -----------------------------------------------------

    @property
    def cached_location(self) -> UserLocation | None:
        return UserLocation.from_dict(self._data.get("location"))

    @cached_location.setter
    def cached_location(self, location: UserLocation) -> None:
        self._data["location"] = location.to_dict()


class LocationTracker:
    """Decides which location applies right now: live share > saved > India."""

    def __init__(self, service: LocationService):
        self._service = service

    async def current(self, session: UserSession, user_id: int) -> UserLocation:
        cached = session.cached_location
        if cached:
            return cached

        stored = await self._service.saved(user_id)
        if stored:
            session.cached_location = stored
            return stored

        return DEFAULT_LOCATION

    async def remember(self, session: UserSession, user_id: int, location: UserLocation) -> None:
        session.cached_location = location
        await self._service.remember(user_id, location)
