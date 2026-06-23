"""Provider adapter errors."""

from __future__ import annotations


class ProviderTransportError(Exception):
    """Base transport error raised before a provider response is available."""


class ProviderTimeout(ProviderTransportError):
    """Provider request exceeded the configured timeout."""
