from __future__ import annotations

from time import perf_counter
from typing import Callable, Literal, TypeVar

from opscript.execution import create_execution, activate_execution
from opscript.logger import format_log_event, get_logger

T = TypeVar("T")
TerminalStatus = Literal["completed", "failed"]

logger = get_logger()


def run_accepted_runtime_operation(
    operation: Callable[[], T],
    *,
    terminal_status: Callable[[T], TerminalStatus],
) -> T:
    execution = create_execution()
    started_at = perf_counter()

    with activate_execution(execution):
        logger.info(
            format_log_event(
                "execution_started",
                execution_id=execution.identity,
                status="started",
            )
        )

        try:
            result = operation()
        except Exception:
            logger.error(
                format_log_event(
                    "execution_failed",
                    execution_id=execution.identity,
                    duration_ms=_duration_ms(started_at),
                    reason="uncaught_exception",
                    terminal_status="failed",
                )
            )
            raise

        status = terminal_status(result)
        if status == "completed":
            logger.info(
                format_log_event(
                    "execution_completed",
                    execution_id=execution.identity,
                    duration_ms=_duration_ms(started_at),
                    terminal_status="completed",
                )
            )
            return result

        logger.error(
            format_log_event(
                "execution_failed",
                execution_id=execution.identity,
                duration_ms=_duration_ms(started_at),
                reason="failure_result",
                terminal_status="failed",
            )
        )
        return result


def _duration_ms(started_at: float) -> int:
    return max(0, int((perf_counter() - started_at) * 1000))
