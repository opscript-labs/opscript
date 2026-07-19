from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Iterator
from uuid import uuid4


@dataclass(frozen=True)
class Execution:
    identity: str = field(default_factory=lambda: uuid4().hex)


_active_execution: ContextVar[Execution | None] = ContextVar(
    "opscript_active_execution",
    default=None,
)


def create_execution() -> Execution:
    return Execution()


def get_active_execution() -> Execution | None:
    return _active_execution.get()


def active_execution_log_fields() -> dict[str, str]:
    execution = get_active_execution()
    if execution is None:
        return {}

    return {"execution_id": execution.identity}


@contextmanager
def activate_execution(execution: Execution) -> Iterator[Execution]:
    token = _active_execution.set(execution)
    try:
        yield execution
    finally:
        _active_execution.reset(token)
