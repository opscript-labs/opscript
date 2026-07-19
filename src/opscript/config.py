from __future__ import annotations

import os
from dataclasses import dataclass, field

from platformiq.model import DiscoveryScope


DEFAULT_DISCOVERY_SCOPE = DiscoveryScope("opscript-runtime-v1-prod")
DEFAULT_LOCAL_DISCOVERY_SCOPE = DiscoveryScope("opscript-runtime-v1-local")


class ConfigurationError(Exception):
    """
    Raised when Opscript runtime configuration is invalid.
    """


@dataclass(frozen=True)
class OpscriptConfig:
    """
    Runtime configuration for Opscript application composition.
    """

    environment: str = "dev"
    log_level: str = "INFO"
    storage_backend: str = "memory"
    discovery_scope: DiscoveryScope = field(
        default_factory=lambda: DEFAULT_LOCAL_DISCOVERY_SCOPE
    )
    s3_bucket: str | None = None
    s3_key: str | None = None
    connect_timeout: float | None = None
    read_timeout: float | None = None
    sdk_total_max_attempts: int = 1

    def validate(self) -> None:
        if not self.environment:
            raise ConfigurationError("Opscript environment must not be empty.")

        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError(
                "Opscript log level must be one of: "
                "DEBUG, INFO, WARNING, ERROR, CRITICAL."
            )

        if self.storage_backend not in {"memory", "s3"}:
            raise ConfigurationError(
                "Opscript storage backend must be one of: memory, s3."
            )

        if not isinstance(self.discovery_scope, DiscoveryScope):
            raise ConfigurationError(
                "Opscript discovery scope must be a DiscoveryScope."
            )

        if self.environment == "prod" and self.storage_backend == "memory":
            raise ConfigurationError(
                "Opscript production environment must not use memory storage."
            )

        if self.storage_backend == "s3" and (not self.s3_bucket or not self.s3_key):
            raise ConfigurationError(
                "Opscript s3 storage requires both bucket and key."
            )

        for name, value in (
            ("connect timeout", self.connect_timeout),
            ("read timeout", self.read_timeout),
        ):
            if value is not None and value <= 0:
                raise ConfigurationError(f"Opscript {name} must be greater than 0.")

        if self.sdk_total_max_attempts <= 0:
            raise ConfigurationError(
                "Opscript OPSCRIPT_AWS_SDK_TOTAL_MAX_ATTEMPTS must be greater than 0."
            )


def _optional_float_from_environment(
    name: str,
) -> float | None:
    value = os.getenv(name)
    if value is None or value == "":
        return None

    try:
        return float(value)
    except ValueError as error:
        raise ConfigurationError(f"Opscript {name} must be a number.") from error


def _int_from_environment(
    name: str,
    default: int,
) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default

    try:
        return int(value)
    except ValueError as error:
        raise ConfigurationError(f"Opscript {name} must be an integer.") from error


def _discovery_scope_from_value(
    value: str | DiscoveryScope,
) -> DiscoveryScope:
    if isinstance(value, DiscoveryScope):
        return value

    if not isinstance(value, str):
        raise ConfigurationError(
            "Opscript discovery scope override must be a string or DiscoveryScope."
        )

    if not value.strip():
        raise ConfigurationError("Opscript discovery scope must not be empty.")

    try:
        return DiscoveryScope(value)
    except (TypeError, ValueError) as error:
        raise ConfigurationError(str(error)) from error


def _discovery_scope_from_environment(
    environment: str,
    discovery_scope_override: str | DiscoveryScope | None = None,
) -> DiscoveryScope:
    if discovery_scope_override is not None:
        return _discovery_scope_from_value(discovery_scope_override)

    configured_scope = os.getenv("OPSCRIPT_DISCOVERY_SCOPE")
    if configured_scope:
        return _discovery_scope_from_value(configured_scope)

    if environment == "prod":
        return DEFAULT_DISCOVERY_SCOPE

    return DEFAULT_LOCAL_DISCOVERY_SCOPE


def load_config_from_environment(
    discovery_scope_override: str | DiscoveryScope | None = None,
) -> OpscriptConfig:
    environment = os.getenv("OPSCRIPT_ENVIRONMENT", "dev")
    config = OpscriptConfig(
        environment=environment,
        log_level=os.getenv("OPSCRIPT_LOG_LEVEL", "INFO"),
        storage_backend=os.getenv("OPSCRIPT_STORAGE_BACKEND", "memory"),
        discovery_scope=_discovery_scope_from_environment(
            environment,
            discovery_scope_override=discovery_scope_override,
        ),
        s3_bucket=os.getenv("OPSCRIPT_S3_BUCKET"),
        s3_key=os.getenv("OPSCRIPT_S3_KEY"),
        connect_timeout=_optional_float_from_environment(
            "OPSCRIPT_AWS_CONNECT_TIMEOUT"
        ),
        read_timeout=_optional_float_from_environment("OPSCRIPT_AWS_READ_TIMEOUT"),
        sdk_total_max_attempts=_int_from_environment(
            "OPSCRIPT_AWS_SDK_TOTAL_MAX_ATTEMPTS",
            default=1,
        ),
    )

    config.validate()

    return config
