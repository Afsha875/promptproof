"""Assertion evaluation against a single model output."""

import json
import re
from dataclasses import dataclass
from typing import Any

from promptproof.spec import Assertion


@dataclass
class AssertionResult:
    assertion: Assertion
    passed: bool
    detail: str = ""


def _norm(text: str, a: Assertion) -> str:
    if a.strip:
        text = text.strip()
    if not a.case_sensitive:
        text = text.lower()
    return text


def _norm_value(a: Assertion) -> str:
    value = str(a.value if a.value is not None else "")
    return value if a.case_sensitive else value.lower()


def _json_get(data: Any, dotted: str) -> Any:
    current = data
    for part in dotted.split("."):
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            if part not in current:
                raise KeyError(part)
            current = current[part]
        else:
            raise KeyError(part)
    return current


def _extract_json(text: str) -> Any:
    """Parse JSON from output, tolerating markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\s*|\s*```$", "", cleaned, flags=re.MULTILINE).strip()
    return json.loads(cleaned)


def evaluate(output: str, assertion: Assertion) -> AssertionResult:
    a = assertion
    text = _norm(output, a)
    try:
        match a.type:
            case "equals":
                ok = text == _norm_value(a)
                return AssertionResult(a, ok, "" if ok else f"got {text[:120]!r}")
            case "contains":
                ok = _norm_value(a) in text
                return AssertionResult(a, ok, "" if ok else f"{a.value!r} not in output")
            case "not_contains":
                ok = _norm_value(a) not in text
                return AssertionResult(a, ok, "" if ok else f"forbidden {a.value!r} present")
            case "regex":
                ok = re.search(str(a.value), output, 0 if a.case_sensitive else re.I) is not None
                return AssertionResult(a, ok, "" if ok else f"no match for /{a.value}/")
            case "json_valid":
                _extract_json(output)
                return AssertionResult(a, True)
            case "json_field":
                data = _extract_json(output)
                actual = _json_get(data, a.path or "")
                if a.value is None:  # existence check only
                    return AssertionResult(a, True)
                ok = str(actual) == str(a.value)
                return AssertionResult(a, ok, "" if ok else f"{a.path}={actual!r}")
            case "max_chars":
                limit = int(a.value or 0)
                ok = len(output.strip()) <= limit
                return AssertionResult(a, ok, "" if ok else f"{len(output.strip())} > {limit}")
    except (json.JSONDecodeError, KeyError, ValueError, IndexError) as e:
        return AssertionResult(a, False, f"{type(e).__name__}: {e}")
    raise ValueError(f"unknown assertion type {a.type}")  # pragma: no cover
