from __future__ import annotations

from typing import Protocol

import boto3
from botocore.config import Config


class AWSClientFactory(Protocol):
    """
    Opscript infrastructure seam for creating AWS service clients.
    """

    def client(self, service_name: str):
        raise NotImplementedError


class Boto3AWSClientFactory:
    """
    AWS client factory backed by boto3.
    """

    def __init__(
        self,
        connect_timeout: int | float | None = None,
        read_timeout: int | float | None = None,
        retry_mode: str | None = None,
        retry_total_max_attempts: int | None = None,
    ):
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.retry_mode = retry_mode
        self.retry_total_max_attempts = retry_total_max_attempts

    def client(self, service_name: str):
        if (
            self.connect_timeout is None
            and self.read_timeout is None
            and self.retry_mode is None
            and self.retry_total_max_attempts is None
        ):
            return boto3.client(service_name)

        config_values = {
            "connect_timeout": self.connect_timeout,
            "read_timeout": self.read_timeout,
        }

        if self.retry_mode is not None or self.retry_total_max_attempts is not None:
            config_values["retries"] = {
                "mode": self.retry_mode,
                "total_max_attempts": self.retry_total_max_attempts,
            }

        config = Config(**config_values)

        return boto3.client(service_name, config=config)
