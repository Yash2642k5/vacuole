"""Plain data types shared by every layer. No I/O, no framework imports."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Literal

_WHITESPACE_RE = re.compile(r"\s+")

Sort = Literal["relevance", "price_asc", "price_desc", "rating"]


@dataclass
class Product:
    title: str
    link: str
    store: str = ""
    price_display: str = ""
    price_value: float | None = None
    old_price_display: str = ""
    rating: float | None = None
    reviews: int | None = None
    thumbnail: str = ""
    delivery: str = ""
    snippet: str = ""
    sponsored: bool = False
    extras: list[str] = field(default_factory=list)
    # The same product offered by other stores, cheapest first: [{store, price, link}].
    offers: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["extras"] = list(self.extras)
        data["offers"] = [dict(offer) for offer in self.offers]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Product":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def dedupe_key(self) -> str:
        """Group listings of the same product, regardless of which store sells it."""
        title = _WHITESPACE_RE.sub(" ", self.title.lower())
        title = re.sub(r"[^a-z0-9 ]+", "", title).strip()
        return title[:60]


@dataclass
class SearchOutcome:
    products: list[Product]
    errors: list[str] = field(default_factory=list)
    engines_used: list[str] = field(default_factory=list)


@dataclass
class SearchPlan:
    query: str = ""
    min_price: float | None = None
    max_price: float | None = None
    sort: Sort = "relevance"
    free_shipping: bool = False
    on_sale: bool = False
    stores: list[str] = field(default_factory=list)


@dataclass
class AssistantReply:
    kind: Literal["products", "text"] = "text"
    text: str = ""
    products: list[Product] = field(default_factory=list)
    query: str = ""
    notice: str = ""


@dataclass(frozen=True)
class ChatTurn:
    """One earlier message in a conversation. `role` is "user" or "assistant"."""

    role: str
    content: str


@dataclass
class UserLocation:
    """Everything the search engines need to localise a query."""

    label: str = "India"              # human readable, also sent as SerpApi `location`
    country: str = "in"               # `gl`
    language: str = "en"              # `hl`
    google_domain: str = "google.co.in"
    amazon_domain: str = "amazon.in"
    currency: str = "₹"
    city: str = ""
    postcode: str = ""
    source: str = "default"           # default | live | typed | saved

    @property
    def display(self) -> str:
        if self.source == "live":
            return f"📍 {self.label} (live)"
        if self.source == "default":
            return f"🌐 {self.label} (default)"
        return f"📍 {self.label}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "UserLocation | None":
        if not data:
            return None
        known = {f.name for f in fields(cls)}
        try:
            return cls(**{k: v for k, v in data.items() if k in known})
        except TypeError:
            return None


DEFAULT_LOCATION = UserLocation()
