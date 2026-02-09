"""Suite execution: every case runs `samples` times; a case passes when the
fraction of passing samples meets `pass_rate`. Cases run concurrently up to a
limit; samples within a case run sequentially (they hit the same model)."""

import asyncio
import time
from dataclasses import dataclass, field

from promptproof.assertions import AssertionResult, evaluate
from promptproof.providers import Provider
from promptproof.spec import Case, PromptSpec, Suite


@dataclass
class SampleResult:
    output: str
    passed: bool
    failures: list[AssertionResult]
    seconds: float


@dataclass
class CaseResult:
    prompt: str
    case: Case
    samples: list[SampleResult] = field(default_factory=list)
    error: str = ""

    @property
    def pass_fraction(self) -> float:
        if not self.samples:
            return 0.0
        return sum(1 for s in self.samples if s.passed) / len(self.samples)

    def passed(self, pass_rate: float) -> bool:
        return not self.error and self.pass_fraction >= pass_rate


@dataclass
class SuiteResult:
    suite: Suite
    cases: list[CaseResult] = field(default_factory=list)
    seconds: float = 0.0

    @property
    def failed_cases(self) -> list[CaseResult]:
        return [c for c in self.cases if not c.passed(self.suite.pass_rate)]

    @property
    def ok(self) -> bool:
        return not self.failed_cases


async def _run_case(
    provider: Provider, suite: Suite, prompt_name: str, spec: PromptSpec, case: Case
) -> CaseResult:
    result = CaseResult(prompt=prompt_name, case=case)
    prompt_text = spec.template.replace("{input}", case.input)
    for _ in range(suite.samples):
        start = time.perf_counter()
        try:
            output = await provider.complete(spec.system, prompt_text, suite.temperature)
        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"
            return result
        failures = [
            r for a in case.asserts if not (r := evaluate(output, a)).passed
        ]
        result.samples.append(
            SampleResult(
                output=output,
                passed=not failures,
                failures=failures,
                seconds=round(time.perf_counter() - start, 2),
            )
        )
    return result


async def run_suite(suite: Suite, provider: Provider, concurrency: int = 4) -> SuiteResult:
    semaphore = asyncio.Semaphore(concurrency)
    started = time.perf_counter()

    async def guarded(name: str, spec: PromptSpec, case: Case) -> CaseResult:
        async with semaphore:
            return await _run_case(provider, suite, name, spec, case)

    tasks = [
        guarded(name, spec, case)
        for name, spec in suite.prompts.items()
        for case in spec.cases
    ]
    cases = list(await asyncio.gather(*tasks))
    return SuiteResult(suite=suite, cases=cases, seconds=round(time.perf_counter() - started, 1))
