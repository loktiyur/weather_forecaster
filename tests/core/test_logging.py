import io
import logging

import pytest
import structlog

from app.core.config import Settings
from app.core.logging import configure_logging
from tests.logs import json_logs, our_handler


def test_structlog_lines_have_level_logger_time_and_fields() -> None:
    with json_logs() as lines:
        structlog.get_logger("app.test").warning("cache is down", key="geo:en:prague:")

    [line] = lines()
    assert line["event"] == "cache is down"
    assert line["key"] == "geo:en:prague:"
    assert (line["level"], line["logger"]) == ("warning", "app.test")
    assert line["timestamp"].endswith("Z")


def test_standard_library_lines_get_the_same_format_and_their_extras() -> None:
    with json_logs() as lines:
        logging.getLogger("httpx").info(
            "HTTP Request: %s", "GET /x", extra={"status": 200, "color_message": "\x1b[36m"}
        )

    [line] = lines()
    assert line["event"] == "HTTP Request: GET /x"
    assert (line["logger"], line["level"], line["status"]) == ("httpx", "info", 200)
    assert "color_message" not in line  # uvicorn's copy with terminal colours


def test_the_bound_request_id_is_on_every_line() -> None:
    with json_logs() as lines, structlog.contextvars.bound_contextvars(request_id="abc"):
        structlog.get_logger("app.test").info("ours")
        logging.getLogger("httpx").info("a library's")

    assert [line["request_id"] for line in lines()] == ["abc", "abc"]


def test_exceptions_are_part_of_the_json_line() -> None:
    with json_logs() as lines:
        try:
            raise ValueError("broken")
        except ValueError:
            logging.getLogger("app.test").exception("failed")

    [line] = lines()
    assert "ValueError: broken" in line["exception"]


def test_lines_below_the_level_are_dropped() -> None:
    with json_logs("WARNING") as lines:
        structlog.get_logger("app.test").info("hidden")
        logging.getLogger("app.test").info("hidden too")
        structlog.get_logger("app.test").warning("shown")

    assert [line["event"] for line in lines()] == ["shown"]


def test_text_format_is_readable() -> None:
    buffer = io.StringIO()
    with json_logs():  # only to restore the logging setup afterwards
        configure_logging("INFO", "text", stream=buffer)
        structlog.get_logger("app.test").info("hello", city="Prague")

    output = buffer.getvalue()
    assert "hello" in output
    assert "city=Prague" in output
    assert not output.lstrip().startswith("{")


def test_configure_logging_is_idempotent_and_routes_uvicorn_through_it() -> None:
    with json_logs():
        configure_logging("WARNING", "json")
        configure_logging("WARNING", "json")

        assert our_handler() is not None  # exactly one (unpacking would fail otherwise)
        assert logging.getLogger().level == logging.WARNING
        assert logging.getLogger("uvicorn").propagate is True
        assert logging.getLogger("uvicorn").handlers == []
        assert logging.getLogger("uvicorn.access").disabled is True


def test_log_settings() -> None:
    settings = Settings(_env_file=None, log_level="debug", log_format="json")

    assert (settings.log_level, settings.log_format) == ("DEBUG", "json")
    with pytest.raises(ValueError):
        Settings(_env_file=None, log_level="LOUD")
