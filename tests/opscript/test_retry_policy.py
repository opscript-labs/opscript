import logging

import pytest

from opscript.application.retry_policy import RetryPolicy
from opscript.errors import OpscriptProviderError, FailureCategory
from opscript.execution import (
    activate_execution,
    create_execution,
    get_active_execution,
)


def _field(message: str, name: str) -> str | None:
    prefix = f"{name}="
    for part in message.split():
        if part.startswith(prefix):
            return part[len(prefix) :]
    return None


def test_retry_policy_returns_operation_result():
    policy = RetryPolicy()

    result = policy.execute(lambda: "completed")

    assert result == "completed"


def test_retry_policy_propagates_operation_exception():
    policy = RetryPolicy()

    def operation():
        raise RuntimeError("operation failed")

    with pytest.raises(RuntimeError, match="operation failed"):
        policy.execute(operation)


def test_retry_policy_retries_on_eligible_provider_errors():
    attempts = 0
    policy = RetryPolicy(max_attempts=3)

    def operation():
        nonlocal attempts
        attempts += 1
        raise OpscriptProviderError(
            "retryable operational error",
            FailureCategory.PROVIDER_OPERATIONAL,
        )

    with pytest.raises(
        OpscriptProviderError, match="retryable operational error"
    ) as exc_info:
        policy.execute(operation)

    assert attempts == 3
    assert exc_info.value.category == FailureCategory.PROVIDER_OPERATIONAL


def test_retry_policy_does_not_retry_on_non_eligible_provider_errors():
    attempts = 0
    policy = RetryPolicy(max_attempts=3)

    def operation():
        nonlocal attempts
        attempts += 1
        raise OpscriptProviderError("non-retryable auth error", FailureCategory.AUTH)

    with pytest.raises(
        OpscriptProviderError, match="non-retryable auth error"
    ) as exc_info:
        policy.execute(operation)

    assert attempts == 1
    assert exc_info.value.category == FailureCategory.AUTH


def test_retry_policy_returns_value_on_success_after_retries():
    attempts = 0
    policy = RetryPolicy(max_attempts=3)

    def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise OpscriptProviderError(
                "transient network issue", FailureCategory.NETWORK
            )
        return "recovered"

    result = policy.execute(operation)

    assert result == "recovered"
    assert attempts == 3


def test_retry_policy_logs_retry_attempt_for_retryable_failure(caplog):
    attempts = 0
    policy = RetryPolicy(max_attempts=2)

    def operation():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OpscriptProviderError(
                "transient network issue",
                FailureCategory.NETWORK,
            )
        return "recovered"

    with caplog.at_level(logging.WARNING, logger="opscript"):
        result = policy.execute(operation)

    messages = [record.message for record in caplog.records]

    assert result == "recovered"
    assert (
        "event=retry_attempt attempt=1 failure_category=NETWORK max_attempts=2"
    ) in messages
    assert not any("execution_id=" in message for message in messages)
    assert get_active_execution() is None


def test_retry_policy_logs_retry_exhaustion(caplog):
    policy = RetryPolicy(max_attempts=2)

    def operation():
        raise OpscriptProviderError(
            "transient network issue",
            FailureCategory.NETWORK,
        )

    with caplog.at_level(logging.ERROR, logger="opscript"):
        with pytest.raises(OpscriptProviderError):
            policy.execute(operation)

    messages = [record.message for record in caplog.records]

    assert (
        "event=retry_exhausted attempt=2 failure_category=NETWORK max_attempts=2"
    ) in messages
    assert not any("execution_id=" in message for message in messages)
    assert get_active_execution() is None


def test_retry_policy_logs_active_execution_identity_on_retry_attempt(caplog):
    attempts = 0
    policy = RetryPolicy(max_attempts=3)
    execution = create_execution()

    def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise OpscriptProviderError(
                "transient network issue",
                FailureCategory.NETWORK,
            )
        return "recovered"

    with (
        activate_execution(execution),
        caplog.at_level(logging.WARNING, logger="opscript"),
    ):
        result = policy.execute(operation)

    retry_attempts = [
        record.message
        for record in caplog.records
        if record.message.startswith("event=retry_attempt ")
    ]
    exhausted = [
        record.message
        for record in caplog.records
        if record.message.startswith("event=retry_exhausted ")
    ]

    assert result == "recovered"
    assert attempts == 3
    assert len(retry_attempts) == 2
    assert exhausted == []
    assert [_field(message, "attempt") for message in retry_attempts] == ["1", "2"]
    assert all(
        _field(message, "execution_id") == execution.identity
        for message in retry_attempts
    )
    assert all("transient network issue" not in message for message in retry_attempts)
    assert get_active_execution() is None


def test_retry_policy_logs_active_execution_identity_on_retry_exhaustion(caplog):
    attempts = 0
    policy = RetryPolicy(max_attempts=2)
    execution = create_execution()

    def operation():
        nonlocal attempts
        attempts += 1
        raise OpscriptProviderError(
            "transient network issue",
            FailureCategory.NETWORK,
        )

    with (
        activate_execution(execution),
        caplog.at_level(logging.WARNING, logger="opscript"),
    ):
        with pytest.raises(OpscriptProviderError) as exc_info:
            policy.execute(operation)

    retry_attempts = [
        record.message
        for record in caplog.records
        if record.message.startswith("event=retry_attempt ")
    ]
    exhausted = [
        record.message
        for record in caplog.records
        if record.message.startswith("event=retry_exhausted ")
    ]

    assert attempts == 2
    assert exc_info.value.category == FailureCategory.NETWORK
    assert len(retry_attempts) == 1
    assert len(exhausted) == 1
    assert _field(retry_attempts[0], "attempt") == "1"
    assert _field(exhausted[0], "attempt") == "2"
    assert _field(retry_attempts[0], "execution_id") == execution.identity
    assert _field(exhausted[0], "execution_id") == execution.identity
    assert "transient network issue" not in retry_attempts[0]
    assert "transient network issue" not in exhausted[0]
    assert get_active_execution() is None


def test_retry_policy_non_retryable_failure_emits_no_retry_lifecycle(caplog):
    attempts = 0
    policy = RetryPolicy(max_attempts=3)
    execution = create_execution()

    def operation():
        nonlocal attempts
        attempts += 1
        raise OpscriptProviderError("auth denied", FailureCategory.AUTH)

    with (
        activate_execution(execution),
        caplog.at_level(logging.WARNING, logger="opscript"),
    ):
        with pytest.raises(OpscriptProviderError) as exc_info:
            policy.execute(operation)

    assert attempts == 1
    assert exc_info.value.category == FailureCategory.AUTH
    assert not any(
        record.message.startswith("event=retry_") for record in caplog.records
    )
    assert get_active_execution() is None
