import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "export_openapi.py"


@pytest.fixture(scope="module")
def export_openapi():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("export_openapi", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_whole_floats_are_written_like_javascript(export_openapi) -> None:  # type: ignore[no-untyped-def]
    # release-please rewrites openapi.json with JavaScript, which writes 16.0 as 16.
    value = {"maximum": 90.0, "examples": [16.0, 50.08804], "nested": {"minimum": -180.0}, "n": 3}

    assert export_openapi._whole_floats_as_ints(value) == {
        "maximum": 90,
        "examples": [16, 50.08804],
        "nested": {"minimum": -180},
        "n": 3,
    }


def test_the_committed_schema_has_no_whole_floats() -> None:
    text = (Path(__file__).parents[1] / "frontend" / "openapi.json").read_text()

    assert json.dumps(json.loads(text), indent=2, ensure_ascii=False) + "\n" == text
    assert ".0," not in text and ".0\n" not in text
