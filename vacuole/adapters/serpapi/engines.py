"""SerpApi-backed `SearchEngine` implementations."""

from __future__ import annotations

from typing import Any

from vacuole.adapters.serpapi.client import SerpApiClient, SerpApiError
from vacuole.adapters.serpapi.parsing import parse_amazon_product, parse_google_product
from vacuole.domain.models import Product, SearchPlan, UserLocation

SORT_GOOGLE = {"price_asc": "1", "price_desc": "2"}
SORT_AMAZON = {
    "price_asc": "price-asc-rank",
    "price_desc": "price-desc-rank",
    "rating": "review-rank",
}


class GoogleShoppingEngine:
    """The widest net: it spans Flipkart, Croma, Amazon, Tata Cliq..."""

    name = "google_shopping"

    def __init__(self, client: SerpApiClient):
        self._client = client

    def applies_to(self, plan: SearchPlan) -> bool:
        return True

    async def search(self, plan: SearchPlan, location: UserLocation) -> list[Product]:
        place = location.label if location.source != "default" else None
        params: dict[str, Any] = {
            "engine": "google_shopping",
            "q": plan.query,
            "location": place,
            "gl": location.country,
            "hl": location.language,
            "google_domain": location.google_domain,
            "min_price": int(plan.min_price) if plan.min_price else None,
            "max_price": int(plan.max_price) if plan.max_price else None,
            "sort_by": SORT_GOOGLE.get(plan.sort),
            "free_shipping": "true" if plan.free_shipping else None,
            "on_sale": "true" if plan.on_sale else None,
        }

        try:
            data = await self._client.get(params)
        except SerpApiError as exc:
            # SerpApi rejects any location it has no canonical match for. A reverse-
            # geocoded city can easily miss, and losing every result over it would be
            # the worse outcome, so retry country-wide instead.
            if place and "location" in str(exc).lower():
                print(f"[serp] location {place!r} not supported, retrying country-wide")
                params["location"] = None
                data = await self._client.get(params)
            else:
                raise

        raw: list[dict[str, Any]] = []
        for key in ("shopping_results", "inline_shopping_results"):
            entries = data.get(key)
            if isinstance(entries, list):
                raw.extend(entry for entry in entries if isinstance(entry, dict))

        # Newer layouts nest results under categories.
        for group in data.get("categorized_shopping_results") or []:
            if isinstance(group, dict) and isinstance(group.get("shopping_results"), list):
                raw.extend(e for e in group["shopping_results"] if isinstance(e, dict))

        return [parse_google_product(item) for item in raw]


class AmazonEngine:
    """Amazon's own index: richer ratings and review counts than Shopping gives."""

    name = "amazon"

    def __init__(self, client: SerpApiClient):
        self._client = client

    def applies_to(self, plan: SearchPlan) -> bool:
        """Skip Amazon when the user explicitly named other stores."""
        if not plan.stores:
            return True
        return any("amazon" in store.lower() for store in plan.stores)

    async def search(self, plan: SearchPlan, location: UserLocation) -> list[Product]:
        data = await self._client.get(
            {
                "engine": "amazon",
                "k": plan.query,
                "amazon_domain": location.amazon_domain,
                "s": SORT_AMAZON.get(plan.sort),
            }
        )
        entries = data.get("organic_results")
        if not isinstance(entries, list):
            return []
        return [parse_amazon_product(e) for e in entries if isinstance(e, dict)]
