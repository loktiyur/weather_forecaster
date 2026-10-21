"""Reads what the real logging setup writes: JSON lines, parsed into dicts."""

import io
import json
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from app.core.logging import HANDLER_NAME, configure_logging

LogLines = Callable[[], list[dict[str, Any]]]


@contextmanager
def json_logs(level: str = "INFO") -> Iterator[LogLines]:
    """Configure logging as in a container (JSON), but into a buffer; restore it afterwards."""
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    buffer = io.StringIO()
    configure_logging(level, "json", stream=buffer)
    try:
        yield lambda: [json.loads(line) for line in buffer.getvalue().splitlines()]
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)


def our_handler() -> logging.Handler:
    [handler] = [h for h in logging.getLogger().handlers if h.get_name() == HANDLER_NAME]
    return handler
