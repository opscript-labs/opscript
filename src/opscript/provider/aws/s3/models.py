from __future__ import annotations

from platformiq.core import Identifier
from platformiq.model import Resource


class S3ResourceMapper:
    """
    Converts AWS S3 bucket representations into PlatformIQ resources.
    """

    def map(
        self,
        bucket_name: str,
    ) -> Resource:
        return Resource(
            id=Identifier.new(),
            external_id=bucket_name,
        )
