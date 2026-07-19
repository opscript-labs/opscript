from __future__ import annotations

from datetime import datetime
from typing import Any

from platformiq.core import Identifier
from platformiq.model import Resource
from platformiq.model.value_objects import ResourceState


class ECRResourceMapper:
    """
    Converts AWS ECR repository representations into PlatformIQ resources.
    """

    def map(
        self,
        repository: dict,
    ) -> Resource:
        return Resource(
            id=Identifier.new(),
            external_id=repository["repositoryName"],
            state=ResourceState(
                properties={
                    "repository_uri": repository.get("repositoryUri"),
                    "registry_id": repository.get("registryId"),
                    "image_tag_mutability": repository.get("imageTagMutability"),
                    "image_scanning_configuration": repository.get(
                        "imageScanningConfiguration"
                    ),
                    "encryption_configuration": repository.get(
                        "encryptionConfiguration"
                    ),
                    "repository_arn": repository.get("repositoryArn"),
                    "created_at": self._created_at(repository.get("createdAt")),
                }
            ),
        )

    def _created_at(
        self,
        value: Any,
    ) -> Any:
        if value is None:
            return None

        if not isinstance(value, datetime):
            return value

        return value.isoformat()
