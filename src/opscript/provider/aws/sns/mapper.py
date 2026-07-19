from __future__ import annotations

from platformiq.core import Identifier
from platformiq.model import Resource
from platformiq.model.value_objects import ResourceState


class SNSResourceMapper:
    """
    Converts AWS SNS topic ARNs into PlatformIQ resources.
    """

    def map(
        self,
        topic_arn: str,
    ) -> Resource:
        return Resource(
            id=Identifier.new(),
            external_id=topic_arn,
            state=ResourceState(properties={}),
        )
