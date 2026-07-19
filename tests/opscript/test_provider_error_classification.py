import pytest
from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ProxyConnectionError,
    ReadTimeoutError,
)

from opscript.application.retry_policy import RetryPolicy
from opscript.errors import (
    OpscriptProviderError,
    FailureCategory,
    classify_provider_error,
)


def client_error(
    code: str,
) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": f"{code} failure"}},
        "TestOperation",
    )


@pytest.mark.parametrize(
    ("error_code", "expected_category"),
    (
        ("AccessDenied", FailureCategory.AUTHORIZATION),
        ("AccessDeniedException", FailureCategory.AUTHORIZATION),
        ("UnauthorizedOperation", FailureCategory.AUTHORIZATION),
        ("AuthFailure", FailureCategory.AUTHORIZATION),
        ("ExpiredToken", FailureCategory.AUTH),
        ("InvalidClientTokenId", FailureCategory.AUTH),
        ("Throttling", FailureCategory.PROVIDER_OPERATIONAL),
        ("ThrottlingException", FailureCategory.PROVIDER_OPERATIONAL),
        ("RequestLimitExceeded", FailureCategory.PROVIDER_OPERATIONAL),
        ("ServiceUnavailable", FailureCategory.PROVIDER_OPERATIONAL),
        ("InternalError", FailureCategory.PROVIDER_OPERATIONAL),
    ),
)
def test_classifies_aws_client_error_codes(
    error_code,
    expected_category,
):
    error = client_error(error_code)

    classified = classify_provider_error(error)

    assert classified.category == expected_category
    assert classified.__cause__ == error


@pytest.mark.parametrize(
    ("error", "expected_category"),
    (
        (
            EndpointConnectionError(endpoint_url="https://ec2.example.com"),
            FailureCategory.NETWORK,
        ),
        (
            ProxyConnectionError(proxy_url="http://127.0.0.1:9"),
            FailureCategory.NETWORK,
        ),
        (
            ConnectTimeoutError(endpoint_url="https://ec2.example.com"),
            FailureCategory.TIMEOUT,
        ),
        (
            ReadTimeoutError(endpoint_url="https://ec2.example.com"),
            FailureCategory.TIMEOUT,
        ),
    ),
)
def test_classifies_botocore_network_and_timeout_errors(
    error,
    expected_category,
):
    classified = classify_provider_error(error)

    assert classified.category == expected_category
    assert classified.__cause__ == error


@pytest.mark.parametrize(
    "category",
    (
        FailureCategory.AUTHORIZATION,
        FailureCategory.AUTH,
    ),
)
def test_retry_policy_does_not_retry_authorization_or_authentication_failures(
    category,
):
    attempts = 0
    policy = RetryPolicy(max_attempts=3)

    def operation():
        nonlocal attempts
        attempts += 1
        raise OpscriptProviderError("non-retryable failure", category)

    with pytest.raises(OpscriptProviderError):
        policy.execute(operation)

    assert attempts == 1


@pytest.mark.parametrize(
    "category",
    (
        FailureCategory.NETWORK,
        FailureCategory.TIMEOUT,
        FailureCategory.PROVIDER_OPERATIONAL,
    ),
)
def test_retry_policy_still_retries_transient_provider_failures(
    category,
):
    attempts = 0
    policy = RetryPolicy(max_attempts=3)

    def operation():
        nonlocal attempts
        attempts += 1
        raise OpscriptProviderError("retryable failure", category)

    with pytest.raises(OpscriptProviderError):
        policy.execute(operation)

    assert attempts == 3
