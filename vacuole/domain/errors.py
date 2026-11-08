"""Errors shared across layers, so callers never import a vendor-specific exception."""


class ProviderError(RuntimeError):
    """An external provider (search, geocoding, ...) failed or is misconfigured."""
