"""Sorting, de-duplication and filtering of product lists.

Sort modes live in a registry. Adding one (say "newest") means adding a `SortOption`
here; the aggregator, the planner and the Telegram buttons all read the registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from vacuole.domain.models import Product

Sorter = Callable[[Iterable[Product]], list[Product]]


@dataclass(frozen=True)
class SortOption:
    key: str
    label: str                  # reads after "Sorted by ...", e.g. "cheapest first"
    sort: Sorter
    button: str | None = None   # inline-button caption; None means no button


def _by_relevance(products: Iterable[Product]) -> list[Product]:
    """Keep engine order but push sponsored and price-less rows down."""
    return sorted(
        products,
        key=lambda p: (p.sponsored, p.price_value is None, not p.thumbnail),
    )


def _by_price_asc(products: Iterable[Product]) -> list[Product]:
    return sorted(products, key=lambda p: (p.price_value is None, p.price_value or 0.0))


def _by_price_desc(products: Iterable[Product]) -> list[Product]:
    return sorted(products, key=lambda p: (p.price_value is None, -(p.price_value or 0.0)))


def _by_rating(products: Iterable[Product]) -> list[Product]:
    return sorted(products, key=lambda p: (-(p.rating or 0.0), -(p.reviews or 0)))


RELEVANCE = SortOption("relevance", "most relevant first", _by_relevance)

SORT_OPTIONS: dict[str, SortOption] = {
    option.key: option
    for option in (
        RELEVANCE,
        SortOption("price_asc", "cheapest first", _by_price_asc, button="💰 Cheapest"),
        SortOption("price_desc", "most expensive first", _by_price_desc),
        SortOption("rating", "top rated first", _by_rating, button="⭐ Top rated"),
    )
}


def get_sort_option(key: str | None) -> SortOption:
    return SORT_OPTIONS.get(key or "", RELEVANCE)


def sort_products(products: Iterable[Product], key: str | None) -> list[Product]:
    return get_sort_option(key).sort(products)


def button_options() -> list[SortOption]:
    return [option for option in SORT_OPTIONS.values() if option.button]


# ---------------------------------------------------------------------------
# De-duplication
# ---------------------------------------------------------------------------


def _richness(product: Product) -> tuple:
    """Cheapest wins; detail breaks ties. Used to pick which listing to show."""
    return (
        product.price_value if product.price_value is not None else float("inf"),
        -(product.reviews or 0),
        not product.thumbnail,
        product.sponsored,
    )


def dedupe(products: Iterable[Product]) -> list[Product]:
    """Merge listings of one product into a single row carrying the rival offers.

    The same earbuds showing up from Flipkart and Amazon is two prices for one thing,
    not two results. Showing the title twice reads as a bug and burns a result slot, so
    the cheapest offer leads and the others ride along on `offers`.
    """
    groups: dict[str, list[Product]] = {}
    for product in products:
        if not product.title or not product.link:
            continue
        groups.setdefault(product.dedupe_key(), []).append(product)

    merged: list[Product] = []
    for candidates in groups.values():
        candidates = sorted(candidates, key=_richness)
        winner = candidates[0]

        seen_stores = {winner.store.lower()}
        for other in candidates[1:]:
            store = other.store.lower()
            if store in seen_stores or not other.store:
                continue
            seen_stores.add(store)
            winner.offers.append(
                {"store": other.store, "price": other.price_display, "link": other.link}
            )
        # Keep whichever rating/review data exists, even if a cheaper row lacked it.
        if winner.rating is None:
            rated = next((c for c in candidates if c.rating is not None), None)
            if rated is not None:
                winner.rating, winner.reviews = rated.rating, rated.reviews
        if not winner.thumbnail:
            with_image = next((c for c in candidates if c.thumbnail), None)
            if with_image is not None:
                winner.thumbnail = with_image.thumbnail
        merged.append(winner)

    return merged


def within_price_range(
    products: Iterable[Product], min_price: float | None, max_price: float | None
) -> list[Product]:
    """Unpriced rows are kept: dropping them would hide products we know nothing about."""
    kept = list(products)
    if min_price is not None:
        kept = [p for p in kept if p.price_value is None or p.price_value >= min_price]
    if max_price is not None:
        kept = [p for p in kept if p.price_value is None or p.price_value <= max_price]
    return kept
