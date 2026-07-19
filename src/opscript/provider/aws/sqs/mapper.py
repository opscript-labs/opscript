from __future__ import annotations

from platformiq.core import Identifier
from platformiq.model import Resource
from platformiq.model.value_objects import ResourceState


class SQSResourceMapper:
    """
    Converts AWS SQS queue URLs into PlatformIQ resources.
    """

    def map(
        self,
        queue_url: str,
    ) -> Resource:
        return Resource(
            id=Identifier.new(),
            external_id=queue_url,
            state=ResourceState(properties={}),
        )
