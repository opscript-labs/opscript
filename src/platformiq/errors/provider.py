from __future__ import annotations


class ProviderError(Exception):
    """
    Base error raised by infrastructure providers.

    Provider implementations should translate provider-specific
    failures into this platform-neutral exception.
    """
