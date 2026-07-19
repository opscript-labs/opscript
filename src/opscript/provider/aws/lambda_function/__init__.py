from __future__ import annotations

from platformiq.core import Identifier
from platformiq.model import Resource


class LambdaResourceMapper:
    """
    Converts AWS Lambda representations into PlatformIQ resources.
    """

    def map(
        self,
        function_name: str,
    ) -> Resource:
        return Resource(
            id=Identifier.new(),
            external_id=function_name,
        )
