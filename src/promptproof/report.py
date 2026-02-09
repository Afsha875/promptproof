"""Result rendering: terminal summary, JSON report, JUnit XML for CI."""

import json
from pathlib import Path
from xml.etree import ElementTree as ET

from promptproof.runner import SuiteResult


def terminal_summary(result: SuiteResult) -> str:
    lines: list[str] = []
    rate = result.suite.pass_rate
    ordered = sorted(result.cases, key=lambda c: (c.prompt, c.case.name))
    width = max((len(f"{c.prompt}::{c.case.name}") for c in ordered), default=0)
    for c in ordered:
        status = "PASS" if c.passed(rate) else "FAIL"
        frac = f"{sum(s.passed for s in c.samples)}/{len(c.samples)}"
        lines.append(f"  {status:<4}  {f'{c.prompt}::{c.case.name}':<{width}}  samples {frac}")
        if c.error:
            lines.append(f"        error: {c.error}")
        elif not c.passed(rate):
            worst = next(s for s in c.samples if not s.passed)
            for f in worst.failures:
                lines.append(f"        {f.assertion.type}: {f.detail}")
    passed = len(result.cases) - len(result.failed_cases)
    lines.append(
        f"\n{passed}/{len(result.cases)} cases passed "
        f"({result.suite.samples} sample(s)/case, pass_rate>={rate}) in {result.seconds}s"
    )
    return "\n".join(lines)


def json_report(result: SuiteResult) -> dict:
    return {
        "model": result.suite.model,
        "provider": result.suite.provider,
        "samples_per_case": result.suite.samples,
        "pass_rate_required": result.suite.pass_rate,
        "seconds": result.seconds,
        "cases": [
            {
                "prompt": c.prompt,
                "case": c.case.name,
                "passed": c.passed(result.suite.pass_rate),
                "pass_fraction": round(c.pass_fraction, 3),
                "error": c.error or None,
                "samples": [
                    {
                        "passed": s.passed,
                        "seconds": s.seconds,
                        "output": s.output,
                        "failures": [
                            {"type": f.assertion.type, "detail": f.detail} for f in s.failures
                        ],
                    }
                    for s in c.samples
                ],
            }
            for c in result.cases
        ],
    }


def junit_xml(result: SuiteResult) -> str:
    rate = result.suite.pass_rate
    root = ET.Element(
        "testsuites",
        name="promptproof",
        tests=str(len(result.cases)),
        failures=str(len(result.failed_cases)),
    )
    by_prompt: dict[str, list] = {}
    for c in result.cases:
        by_prompt.setdefault(c.prompt, []).append(c)
    for prompt, cases in by_prompt.items():
        suite_el = ET.SubElement(
            root,
            "testsuite",
            name=prompt,
            tests=str(len(cases)),
            failures=str(sum(1 for c in cases if not c.passed(rate))),
        )
        for c in cases:
            case_el = ET.SubElement(
                suite_el,
                "testcase",
                name=c.case.name,
                classname=prompt,
                time=str(sum(s.seconds for s in c.samples)),
            )
            if not c.passed(rate):
                detail = c.error or "; ".join(
                    f"{f.assertion.type}: {f.detail}"
                    for s in c.samples
                    if not s.passed
                    for f in s.failures
                )
                failure = ET.SubElement(
                    case_el,
                    "failure",
                    message=f"pass_fraction={c.pass_fraction:.2f} < {rate}",
                )
                failure.text = detail
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def write_reports(result: SuiteResult, json_path: Path | None, junit_path: Path | None) -> None:
    if json_path:
        json_path.write_text(json.dumps(json_report(result), indent=2))
    if junit_path:
        junit_path.write_text(junit_xml(result))
