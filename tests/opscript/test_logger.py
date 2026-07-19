import io
import logging
import pytest
from opscript.logger import format_log_event, get_logger


@pytest.fixture(autouse=True)
def restore_logging():
    # Save original state
    root = logging.getLogger()
    root_handlers = list(root.handlers)
    root_level = root.level

    cm = logging.getLogger("opscript")
    cm_handlers = list(cm.handlers)
    cm_level = cm.level
    cm_propagate = cm.propagate

    yield

    # Restore original state
    root.handlers = root_handlers
    root.setLevel(root_level)

    cm.handlers = cm_handlers
    cm.setLevel(cm_level)
    cm.propagate = cm_propagate


def test_get_logger_returns_opscript_logger():
    logger = get_logger()

    assert logger.name == "opscript"


def test_format_log_event_includes_event_name():
    output = format_log_event("workflow_started")

    assert output == "event=workflow_started"


def test_format_log_event_includes_sorted_fields():
    output = format_log_event(
        "workflow_completed",
        workflow="resource_evolution",
        comparisons=2,
        snapshots=3,
    )

    assert output == (
        "event=workflow_completed comparisons=2 snapshots=3 workflow=resource_evolution"
    )


def test_get_logger_no_root_handlers():
    root = logging.getLogger()
    root.handlers = []
    cm = logging.getLogger("opscript")
    cm.handlers = []

    logger = get_logger()

    owned = [h for h in logger.handlers if getattr(h, "_opscript_owned", False)]
    assert len(owned) == 1
    assert len(logger.handlers) == 1

    stream = io.StringIO()
    owned[0].stream = stream

    logger.info("hello")
    assert "[INFO] hello\n" in stream.getvalue()


def test_get_logger_with_root_handlers():
    root = logging.getLogger()
    stream = io.StringIO()
    root_handler = logging.StreamHandler(stream)
    root.handlers = [root_handler]

    cm = logging.getLogger("opscript")
    cm.handlers = []

    logger = get_logger()

    owned = [h for h in logger.handlers if getattr(h, "_opscript_owned", False)]
    assert len(owned) == 0
    assert logger.propagate is True

    logger.info("hello to root")
    assert "hello to root\n" in stream.getvalue()


def test_repeated_get_logger_calls_do_not_accumulate():
    root = logging.getLogger()
    root.handlers = []

    cm = logging.getLogger("opscript")
    cm.handlers = []

    for _ in range(5):
        get_logger()

    assert len(cm.handlers) == 1


def test_transition_between_contexts():
    root = logging.getLogger()
    root.handlers = []

    cm = logging.getLogger("opscript")
    cm.handlers = []

    logger = get_logger()
    assert len(cm.handlers) == 1

    stream = io.StringIO()
    root_handler = logging.StreamHandler(stream)
    root.handlers = [root_handler]

    logger = get_logger()
    assert len(cm.handlers) == 0
    assert logger.propagate is True

    logger.info("transition complete")
    assert "transition complete\n" in stream.getvalue()


def test_repeated_lambda_invocations():
    root = logging.getLogger()
    stream = io.StringIO()
    root_handler = logging.StreamHandler(stream)
    root.handlers = [root_handler]

    for _ in range(3):
        logger = get_logger()
        logger.info("lambda invocation")

    output = stream.getvalue()
    lines = [line for line in output.split("\n") if line]
    assert len(lines) == 3
    assert all(line == "lambda invocation" for line in lines)


def test_error_logging_remains_visible():
    root = logging.getLogger()
    root.handlers = []

    cm = logging.getLogger("opscript")
    cm.handlers = []

    logger = get_logger()
    owned = [h for h in logger.handlers if getattr(h, "_opscript_owned", False)][0]
    stream = io.StringIO()
    owned.stream = stream

    logger.error("critical failure")
    assert "[ERROR] critical failure\n" in stream.getvalue()
