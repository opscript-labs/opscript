from __future__ import annotations

from typing import Callable, TypeVar

from opscript.errors import OpscriptProviderError, FailureCategory
from opscript.execution import active_execution_log_fields
from opscript.logger import format_log_event, get_logger

T = TypeVar("T")

RETRY_ELIGIBLE_CATEGORIES = {
    FailureCategory.PROVIDER_OPERATIONAL,
    FailureCategory.NETWORK,
    FailureCategory.TIMEOUT,
}

logger = get_logger()


class RetryPolicy:
    """
    Executes an operation according to the configured retry policy.
    """

    def __init__(self, max_attempts: int = 3):
        self._max_attempts = max_attempts

    def execute(
        self,
        operation: Callable[[], T],
    ) -> T:
        attempts = 0
        while True:
            attempts += 1
            try:
                return operation()
            except OpscriptProviderError as error:
                if (
                    error.category in RETRY_ELIGIBLE_CATEGORIES
                    and attempts < self._max_attempts
                ):
                    logger.warning(
                        format_log_event(
                            "retry_attempt",
                            attempt=attempts,
                            failure_category=error.category.name,
                            max_attempts=self._max_attempts,
                            **active_execution_log_fields(),
                        )
                    )
                    continue
                if error.category in RETRY_ELIGIBLE_CATEGORIES:
                    logger.error(
                        format_log_event(
                            "retry_exhausted",
                            attempt=attempts,
                            failure_category=error.category.name,
                            max_attempts=self._max_attempts,
                            **active_execution_log_fields(),
                        )
                    )
                raise
