from promptproof.assertions import evaluate
from promptproof.spec import Assertion


def _a(**kw) -> Assertion:
    return Assertion(**kw)


def test_equals_with_strip_and_case():
    assert evaluate("  Jane@Acme.io \n", _a(type="equals", value="jane@acme.io",
                                            case_sensitive=False)).passed
    assert not evaluate("jane@acme.io", _a(type="equals", value="JANE@ACME.IO")).passed


def test_contains_and_not_contains():
    assert evaluate("The answer is 42.", _a(type="contains", value="42")).passed
    r = evaluate("The answer is 42.", _a(type="not_contains", value="42"))
    assert not r.passed and "forbidden" in r.detail


def test_regex():
    assert evaluate("order #A-1234 shipped", _a(type="regex", value=r"#[A-Z]-\d{4}")).passed
    assert not evaluate("no order id", _a(type="regex", value=r"#[A-Z]-\d{4}")).passed


def test_json_valid_tolerates_markdown_fences():
    assert evaluate('```json\n{"ok": true}\n```', _a(type="json_valid")).passed
    r = evaluate("not json at all", _a(type="json_valid"))
    assert not r.passed and "JSONDecodeError" in r.detail


def test_json_field_path_value_and_existence():
    output = '{"user": {"email": "j@x.io", "tags": ["a", "b"]}}'
    assert evaluate(output, _a(type="json_field", path="user.email", value="j@x.io")).passed
    assert evaluate(output, _a(type="json_field", path="user.tags.1", value="b")).passed
    assert evaluate(output, _a(type="json_field", path="user.email")).passed  # existence
    r = evaluate(output, _a(type="json_field", path="user.phone"))
    assert not r.passed and "KeyError" in r.detail
    r2 = evaluate(output, _a(type="json_field", path="user.email", value="wrong@x.io"))
    assert not r2.passed and "j@x.io" in r2.detail


def test_max_chars():
    assert evaluate("short", _a(type="max_chars", value=10)).passed
    r = evaluate("x" * 50, _a(type="max_chars", value=10))
    assert not r.passed and "50 > 10" in r.detail
