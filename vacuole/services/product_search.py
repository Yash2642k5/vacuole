"""Fan a search out to every applicable engine and return one merged, ranked list."""

from __future__ import annotations

import asyncio
from typing import Sequence

from vacuole.domain.models import Product, SearchOutcome, SearchPlan, UserLocation
from vacuole.domain.ranking import (
    dedupe,
    exclude_accessories,
    sort_products,
    within_price_range,
)
from vacuole.ports import SearchEngine


class ProductSearchService:
    """Implements `ProductSearch` over any set of `SearchEngine`s."""

    def __init__(self, engines: Sequence[SearchEngine], *, default_limit: int = 8):
        self._engines = list(engines)
        self._default_limit = default_limit

    async def search(
        self, plan: SearchPlan, location: UserLocation, limit: int | None = None
    ) -> SearchOutcome:
        if not plan.query.strip():
            return SearchOutcome(products=[], errors=["Empty search query."])

        engines = [engine for engine in self._engines if engine.applies_to(plan)]
        results = await asyncio.gather(
            *(engine.search(plan, location) for engine in engines), return_exceptions=True
        )

        found: list[Product] = []
        errors: list[str] = []
        engines_used: list[str] = []

        for engine, result in zip(engines, results):
            if isinstance(result, BaseException):
                # Some exceptions stringify to nothing; keep the type so the log is useful.
                errors.append(f"{engine.name}: {str(result) or type(result).__name__}")
                continue
            if result:
                engines_used.append(engine.name)
                found.extend(result)

        # Price bounds are enforced locally too: not every engine has a price filter.
        relevant = exclude_accessories(dedupe(found), plan.query)
        merged = within_price_range(relevant, plan.min_price, plan.max_price)
        ranked = sort_products(merged, plan.sort)

        return SearchOutcome(
            products=ranked[: limit or self._default_limit],
            errors=errors,
            engines_used=engines_used,
        )
