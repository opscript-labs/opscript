import logging
from typing import Any


def get_logger():
    logger = logging.getLogger("opscript")
    root_logger = logging.getLogger()

    # Identify existing opscript-owned handlers
    owned_handlers = [
        h for h in logger.handlers if getattr(h, "_opscript_owned", False)
    ]

    # Propagation should be True to propagate to root handler
    logger.propagate = True
    logger.setLevel(logging.INFO)

    if root_logger.handlers:
        # Root has handlers, remove all opscript-owned handlers
        for handler in owned_handlers:
            logger.removeHandler(handler)
    else:
        # Root has no handlers, we want exactly one opscript-owned handler
        if not owned_handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("[%(levelname)s] %(message)s")
            handler.setFormatter(formatter)
            handler._opscript_owned = True
            logger.addHandler(handler)
        elif len(owned_handlers) > 1:
            for handler in owned_handlers[1:]:
                logger.removeHandler(handler)

    return logger


def format_log_event(
    event: str,
    **fields: Any,
) -> str:
    parts = [f"event={event}"]

    for key in sorted(fields):
        value = fields[key]
        parts.append(f"{key}={value}")

    return " ".join(parts)
