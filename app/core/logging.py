"""Logging setup with structlog: readable lines locally, one JSON object per line in containers.

Our own log calls and those of the libraries (uvicorn, httpx, `logging.getLogger` in our
modules) go through the same processors, so every line has the same fields, and every line
written during a request carries its id (bound in `app/api/middleware.py`).
"""

import logging
import sys
from typing import Literal, TextIO

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

LogFormat = Literal["text", "json"]

HANDLER_NAME = "weather-forecaster"


def _drop_duplicates(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    # Copies of `event` on standard library records: uvicorn's version with terminal colour
    # codes, and `message`, set when another handler has formatted the record already.
    event_dict.pop("color_message", None)
    event_dict.pop("message", None)
    return event_dict


# Run for every line, whether it comes from structlog or from a standard library logger.
_SHARED: list[Processor] = [
    structlog.contextvars.merge_contextvars,  # request_id, while a request is handled
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    _drop_duplicates,
]


def configure_logging(level: str, log_format: LogFormat, stream: TextIO | None = None) -> None:
    """Send all logs through one handler and format. Safe to call repeatedly."""
    renderer: list[Processor] = (
        [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ]
        if log_format == "json"
        else [structlog.dev.ConsoleRenderer(colors=False)]
    )
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.set_name(HANDLER_NAME)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            # Standard library records: `extra=` fields become fields of the line as well
            # (added first, so the shared processors can still drop or change them).
            foreign_pre_chain=[structlog.stdlib.ExtraAdder(), *_SHARED],
            processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, *renderer],
        )
    )

    root = logging.getLogger()
    for existing in [h for h in root.handlers if h.get_name() == HANDLER_NAME]:
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *_SHARED,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Uvicorn's server messages use the same handler and format (through the root logger).
    uvicorn = logging.getLogger("uvicorn")
    uvicorn.handlers.clear()
    uvicorn.propagate = True
    # Its access log is replaced by ours (`app.access`): that one has the request id and
    # leaves out the health checks Docker sends every few seconds.
    logging.getLogger("uvicorn.access").disabled = True
