from __future__ import annotations

from enum import Enum, auto
import botocore.exceptions
from platformiq.errors.provider import ProviderError


class FailureCategory(Enum):
    """
    Failure categories for Opscript operational error classification.
    """

    PROVIDER_OPERATIONAL = auto()
    NETWORK = auto()
    TIMEOUT = auto()
    STORAGE = auto()
    CONFIGURATION = auto()
    AUTH = auto()
    AUTHORIZATION = auto()
    VALIDATION = auto()
    INTERNAL_DEFECT = auto()
    UNSUPPORTED_OPERATION = auto()


class OpscriptProviderError(ProviderError):
    """
    Classified provider error that inherits from platformiq's ProviderError
    and carries a local operational FailureCategory.
    """

    def __init__(
        self,
        message: str,
        category: FailureCategory,
        original_exception: Exception | None = None,
    ):
        super().__init__(message)
        self.category = category
        self.original_exception = original_exception
        if original_exception:
            self.__cause__ = original_exception


def classify_provider_error(error: Exception) -> OpscriptProviderError:
    """
    Classifies a raw provider/client exception into a OpscriptProviderError.
    """
    if isinstance(error, OpscriptProviderError):
        return error

    message = str(error)

    # Check for timeout exception types
    if isinstance(
        error,
        (
            TimeoutError,
            botocore.exceptions.ConnectTimeoutError,
            botocore.exceptions.ReadTimeoutError,
        ),
    ):
        return OpscriptProviderError(
            message,
            FailureCategory.TIMEOUT,
            original_exception=error,
        )

    # Check for network exception types
    if isinstance(
        error,
        (
            ConnectionError,
            botocore.exceptions.EndpointConnectionError,
            botocore.exceptions.HTTPClientError,
            botocore.exceptions.ProxyConnectionError,
        ),
    ):
        return OpscriptProviderError(
            message,
            FailureCategory.NETWORK,
            original_exception=error,
        )

    # Check for botocore ClientError which includes credentials and auth
    if isinstance(error, botocore.exceptions.ClientError):
        error_code = error.response.get("Error", {}).get("Code", "")

        # Auth / Authorization / Access Denied
        if error_code in (
            "AccessDenied",
            "AccessDeniedException",
            "UnauthorizedOperation",
            "AuthFailure",
        ):
            return OpscriptProviderError(
                message,
                FailureCategory.AUTHORIZATION,
                original_exception=error,
            )

        # Configuration / Invalid credentials
        if error_code in (
            "InvalidAccessKeyId",
            "InvalidClientTokenId",
            "SignatureDoesNotMatch",
            "ExpiredToken",
            "UnrecognizedClientException",
        ):
            return OpscriptProviderError(
                message,
                FailureCategory.AUTH,
                original_exception=error,
            )

        # Missing configuration / Invalid parameters
        if error_code in ("InvalidParameterValue", "ValidationException"):
            return OpscriptProviderError(
                message,
                FailureCategory.VALIDATION,
                original_exception=error,
            )

        # Throttling / Operational
        if error_code in (
            "Throttling",
            "ThrottlingException",
            "RequestLimitExceeded",
            "ProvisionedThroughputExceededException",
            "ServiceUnavailable",
            "InternalError",
        ):
            return OpscriptProviderError(
                message,
                FailureCategory.PROVIDER_OPERATIONAL,
                original_exception=error,
            )

    # If it's a plain unclassified platformiq ProviderError, treat as INTERNAL_DEFECT (non-retryable)
    if isinstance(error, ProviderError):
        return OpscriptProviderError(
            message,
            FailureCategory.INTERNAL_DEFECT,
            original_exception=error,
        )

    # For any other unclassified exception, treat as INTERNAL_DEFECT
    return OpscriptProviderError(
        message,
        FailureCategory.INTERNAL_DEFECT,
        original_exception=error,
    )
