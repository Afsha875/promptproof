import asyncio

from promptproof.runner import run_suite
from promptproof.spec import Suite

BASE = {
    "provider": "fake",
    "prompts": {
        "extract": {
            "system": "sys",
            "cases": [
                {"name": "ok", "input": "hello world",
                 "assert": [{"type": "contains", "value": "hello"}]},
                {"name": "bad", "input": "goodbye",
                 "assert": [{"type": "contains", "value": "hello"}]},
            ],
        }
    },
}


class ScriptedProvider:
    """Yields queued outputs in order; then falls back to echo."""

    def __init__(self, outputs: list[str]):
        self.outputs = list(outputs)
        self.calls = 0

    async def complete(self, system, prompt, temperature):
        self.calls += 1
        return self.outputs.pop(0) if self.outputs else prompt


def test_pass_and_fail_cases_with_echo_provider():
    suite = Suite.model_validate(BASE)
    from promptproof.providers import EchoProvider

    result = asyncio.run(run_suite(suite, EchoProvider()))
    by_name = {c.case.name: c for c in result.cases}
    assert by_name["ok"].passed(1.0)
    assert not by_name["bad"].passed(1.0)
    assert not result.ok and len(result.failed_cases) == 1


def test_sampling_pass_rate_semantics():
    spec = dict(BASE, samples=3, pass_rate=0.6)
    spec["prompts"] = {
        "p": {"cases": [{"name": "flaky", "input": "x",
                         "assert": [{"type": "equals", "value": "good"}]}]}
    }
    suite = Suite.model_validate(spec)
    # 2 of 3 samples pass -> fraction 0.67 >= 0.6 -> case passes
    result = asyncio.run(run_suite(suite, ScriptedProvider(["good", "bad", "good"])))
    case = result.cases[0]
    assert case.pass_fraction == 2 / 3
    assert case.passed(0.6) and result.ok
    # with pass_rate 1.0 the same history fails
    assert not case.passed(1.0)


def test_provider_error_marks_case_errored():
    class Exploding:
        async def complete(self, *args):
            raise RuntimeError("connection refused")

    suite = Suite.model_validate(BASE)
    result = asyncio.run(run_suite(suite, Exploding()))
    assert all(c.error.startswith("RuntimeError") for c in result.cases)
    assert not result.ok


def test_template_renders_input():
    spec = {
        "provider": "fake",
        "prompts": {
            "p": {
                "template": "Extract from: {input}",
                "cases": [{"name": "t", "input": "abc",
                           "assert": [{"type": "equals", "value": "Extract from: abc"}]}],
            }
        },
    }
    result = asyncio.run(run_suite(Suite.model_validate(spec),
                                   __import__("promptproof.providers",
                                              fromlist=["EchoProvider"]).EchoProvider()))
    assert result.ok
