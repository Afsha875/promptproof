import json
from xml.etree import ElementTree as ET

import pytest
from pydantic import ValidationError

from promptproof.cli import main
from promptproof.report import json_report, junit_xml
from promptproof.runner import run_suite
from promptproof.spec import Suite, load_suite

SUITE_YAML = """
provider: fake
samples: 1
prompts:
  greeting:
    cases:
      - name: passes
        input: "hello there"
        assert:
          - type: contains
            value: hello
      - name: fails
        input: "goodbye"
        assert:
          - type: contains
            value: hello
"""


@pytest.fixture
def suite_file(tmp_path):
    p = tmp_path / "suite.yaml"
    p.write_text(SUITE_YAML)
    return p


def test_load_suite_validates(suite_file, tmp_path):
    suite = load_suite(suite_file)
    assert suite.provider == "fake"
    bad = tmp_path / "bad.yaml"
    bad.write_text("prompts: {}")
    with pytest.raises(ValidationError):
        load_suite(bad)


def test_cli_exit_codes_and_reports(suite_file, tmp_path, capsys):
    report = tmp_path / "r.json"
    junit = tmp_path / "j.xml"
    code = main([str(suite_file), "--report", str(report), "--junit", str(junit)])
    assert code == 1  # one failing case
    out = capsys.readouterr().out
    assert "PASS" in out and "FAIL" in out and "1/2 cases passed" in out

    data = json.loads(report.read_text())
    assert data["provider"] == "fake"
    assert {c["case"]: c["passed"] for c in data["cases"]} == {"passes": True, "fails": False}

    tree = ET.fromstring(junit.read_text())
    assert tree.attrib["failures"] == "1"
    failure = tree.find(".//testcase[@name='fails']/failure")
    assert failure is not None and "pass_fraction" in failure.attrib["message"]


def test_cli_invalid_suite_returns_2(tmp_path):
    p = tmp_path / "invalid.yaml"
    p.write_text("prompts: {}")
    assert main([str(p)]) == 2


async def test_json_report_includes_sample_outputs():
    suite = Suite.model_validate(json.loads(json.dumps({
        "provider": "fake",
        "prompts": {"p": {"cases": [
            {"name": "c", "input": "data", "assert": [{"type": "contains", "value": "data"}]}
        ]}},
    })))
    from promptproof.providers import EchoProvider

    result = await run_suite(suite, EchoProvider())
    payload = json_report(result)
    assert payload["cases"][0]["samples"][0]["output"] == "data"
    assert "testsuite" in junit_xml(result)
