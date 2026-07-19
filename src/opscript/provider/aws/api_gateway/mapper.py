from __future__ import annotations

from datetime import datetime
from typing import Any

from platformiq.core import Identifier
from platformiq.model import Resource
from platformiq.model.value_objects import ResourceState


class APIGatewayResourceMapper:
    """
    Converts AWS API Gateway REST API representations into PlatformIQ resources.
    """

    def map(
        self,
        rest_api: dict,
    ) -> Resource:
        return Resource(
            id=Identifier.new(),
            external_id=rest_api["id"],
            state=ResourceState(
                properties={
                    "name": rest_api.get("name"),
                    "description": rest_api.get("description"),
                    "created_date": self._created_date(rest_api.get("createdDate")),
                    "version": rest_api.get("version"),
                    "api_key_source": rest_api.get("apiKeySource"),
                    "endpoint_configuration": rest_api.get("endpointConfiguration"),
                    "binary_media_types": rest_api.get("binaryMediaTypes"),
                    "minimum_compression_size": rest_api.get("minimumCompressionSize"),
                    "disable_execute_api_endpoint": rest_api.get(
                        "disableExecuteApiEndpoint"
                    ),
                    "policy": rest_api.get("policy"),
                    "warnings": rest_api.get("warnings"),
                    "tags": rest_api.get("tags"),
                }
            ),
        )

    def _created_date(
        self,
        value: Any,
    ) -> Any:
        if value is None:
            return None

        if not isinstance(value, datetime):
            return value

        return value.isoformat()
