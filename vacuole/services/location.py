"""Resolve where the user is shopping from.

Priority: the live location they shared > a city they typed > a saved location >
India as the default. The resolved object carries everything the search engines need
(`location`, `gl`, `hl`, Google and Amazon domains).
"""

from __future__ import annotations

from vacuole.domain.errors import ProviderError
from vacuole.domain.models import DEFAULT_LOCATION, UserLocation
from vacuole.ports import LocationStore, PlaceLookup, ReverseGeocoder

# Countries where this assistant is actually useful, with their storefronts.
# Anything unlisted falls back to the Google domain only.
COUNTRY_PROFILES: dict[str, dict[str, str]] = {
    "in": {"google_domain": "google.co.in", "amazon_domain": "amazon.in", "currency": "₹", "language": "en"},
    "us": {"google_domain": "google.com", "amazon_domain": "amazon.com", "currency": "$", "language": "en"},
    "gb": {"google_domain": "google.co.uk", "amazon_domain": "amazon.co.uk", "currency": "£", "language": "en"},
    "uk": {"google_domain": "google.co.uk", "amazon_domain": "amazon.co.uk", "currency": "£", "language": "en"},
    "ae": {"google_domain": "google.ae", "amazon_domain": "amazon.ae", "currency": "AED", "language": "en"},
    "ca": {"google_domain": "google.ca", "amazon_domain": "amazon.ca", "currency": "C$", "language": "en"},
    "au": {"google_domain": "google.com.au", "amazon_domain": "amazon.com.au", "currency": "A$", "language": "en"},
    "sg": {"google_domain": "google.com.sg", "amazon_domain": "amazon.sg", "currency": "S$", "language": "en"},
    "de": {"google_domain": "google.de", "amazon_domain": "amazon.de", "currency": "€", "language": "de"},
    "fr": {"google_domain": "google.fr", "amazon_domain": "amazon.fr", "currency": "€", "language": "fr"},
    "jp": {"google_domain": "google.co.jp", "amazon_domain": "amazon.co.jp", "currency": "¥", "language": "ja"},
    "br": {"google_domain": "google.com.br", "amazon_domain": "amazon.com.br", "currency": "R$", "language": "pt"},
}

_CITY_KEYS = ("city", "town", "village", "municipality", "suburb", "county")


def build_location(
    label: str,
    country_code: str,
    *,
    city: str = "",
    postcode: str = "",
    source: str = "typed",
) -> UserLocation:
    code = (country_code or "in").lower()
    profile = COUNTRY_PROFILES.get(code, {})
    return UserLocation(
        label=label or DEFAULT_LOCATION.label,
        country=code,
        language=profile.get("language", "en"),
        google_domain=profile.get("google_domain", "google.com"),
        amazon_domain=profile.get("amazon_domain", "amazon.com"),
        currency=profile.get("currency", ""),
        city=city,
        postcode=postcode,
        source=source,
    )


class LocationService:
    def __init__(
        self, geocoder: ReverseGeocoder, places: PlaceLookup, store: LocationStore
    ):
        self._geocoder = geocoder
        self._places = places
        self._store = store

    async def from_coordinates(self, latitude: float, longitude: float) -> UserLocation:
        """Reverse-geocode shared coordinates into a city-level search location.

        SerpApi wants a place name rather than coordinates, and its docs recommend
        city-level precision. Falls back to the default if geocoding is unavailable.
        """
        address = await self._geocoder.reverse(latitude, longitude)
        if not address:
            return DEFAULT_LOCATION

        city = next((address[key] for key in _CITY_KEYS if address.get(key)), "")
        state = address.get("state") or address.get("region") or ""
        country = address.get("country") or ""
        country_code = (address.get("country_code") or "in").lower()

        label = ", ".join(part for part in (city, state, country) if part) or country or "India"
        return build_location(
            label,
            country_code,
            city=city,
            postcode=address.get("postcode") or "",
            source="live",
        )

    async def from_text(self, place: str) -> UserLocation | None:
        """Turn "Pune" into a SerpApi canonical location, or None if unrecognised."""
        place = (place or "").strip()
        if not place:
            return None

        try:
            match = await self._places.find(place)
        except ProviderError:
            match = None
        if not match:
            return None

        label = match.get("canonical_name") or match.get("name") or place
        country_code = (match.get("country_code") or "in").lower()
        return build_location(
            str(label).replace(",", ", "),
            country_code,
            city=str(match.get("name") or ""),
            source="typed",
        )

    async def saved(self, user_id: str | int) -> UserLocation | None:
        location = await self._store.load(user_id)
        if location and location.source == "live":
            # A saved live fix is historical, not current.
            location.source = "saved"
        return location

    async def remember(self, user_id: str | int, location: UserLocation) -> None:
        await self._store.save(user_id, location)
