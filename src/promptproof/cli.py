"""promptproof CLI: run a suite, print a summary, exit non-zero on failure."""

import argparse
import asyncio
import sys
from pathlib import Path

from promptproof.providers import build_provider
from promptproof.report import terminal_summary, write_reports
from promptproof.runner import run_suite
from promptproof.spec import load_suite


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="promptproof", description="Regression tests for LLM prompts"
    )
    parser.add_argument("suite", type=Path, help="YAML suite file")
    parser.add_argument("--report", type=Path, default=None, help="write JSON report here")
    parser.add_argument("--junit", type=Path, default=None, help="write JUnit XML here")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--model", default=None, help="override the suite's model")
    args = parser.parse_args(argv)

    try:
        suite = load_suite(args.suite)
    except Exception as e:
        print(f"invalid suite: {e}", file=sys.stderr)
        return 2

    if args.model:
        suite = suite.model_copy(update={"model": args.model})

    try:
        provider = build_provider(suite.provider, suite.model)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    print(f"promptproof: {suite.provider}:{suite.model}, "
          f"{suite.samples} sample(s)/case, pass_rate>={suite.pass_rate}\n")
    result = asyncio.run(run_suite(suite, provider, concurrency=args.concurrency))
    print(terminal_summary(result))
    write_reports(result, args.report, args.junit)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
