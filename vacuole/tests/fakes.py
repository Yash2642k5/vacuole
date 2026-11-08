"""In-memory stand-ins for the ports, used by the tests."""

from __future__ import annotations

from vacuole.domain.models import Product, SearchPlan, UserLocation


class FakeModel:
    """Returns canned replies in order; raises if a reply is an Exception."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts: list[str] = []

    async def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        reply = self.replies.pop(0) if self.replies else ""
        if isinstance(reply, Exception):
            raise reply
        return reply


class FakeEngine:
    def __init__(self, name, products=None, *, error=None, applies=True):
        self.name = name
        self._products = products or []
        self._error = error
        self._applies = applies

    def applies_to(self, plan: SearchPlan) -> bool:
        return self._applies

    async def search(self, plan: SearchPlan, location: UserLocation) -> list[Product]:
        if self._error:
            raise self._error
        return list(self._products)


class RecordingProgress:
    def __init__(self):
        self.steps: list[str] = []

    async def step(self, key: str, detail: str = "") -> None:
        self.steps.append(key)


def product(title="Phone", price=100.0, store="Shop", **kw) -> Product:
    return Product(
        title=title,
        link=kw.pop("link", f"https://example.com/{title}/{store}"),
        store=store,
        price_display=f"₹{price:,.0f}" if price is not None else "",
        price_value=price,
        **kw,
    )
