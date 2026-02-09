# promptproof

**pytest for prompts: declare what your LLM outputs must look like, run it like a test suite, wire it into CI.**

Edit a system prompt, swap a model, bump a temperature - and quietly break an extraction pipeline three services downstream. promptproof makes prompt behavior a tested contract: YAML suites of cases with assertions, sampling-aware pass rates (because LLM output is nondeterministic and pretending otherwise is how regressions ship), exit codes and JUnit XML so CI treats prompt regressions like failing tests.

```yaml
provider: ollama          # or anthropic; "fake" echoes input for dry-runs
model: llama3.1:8b
temperature: 0.0
samples: 3                # run each case 3 times...
pass_rate: 1.0            # ...and require all 3 to pass

prompts:
  extract_email:
    system: >-
      Extract the email address from the user's text.
      Reply with only the email address and nothing else.
      If there is no email address, reply with exactly NONE.
    cases:
      - name: simple
        input: "You can reach Jane at jane@acme.io after Tuesday."
        assert:
          - type: equals
            value: jane@acme.io
            case_sensitive: false
```

Real output of `promptproof examples/extraction.yaml` on this machine (llama3.1:8b via Ollama):

```
promptproof: ollama:llama3.1:8b, 3 sample(s)/case, pass_rate>=1.0

  PASS  classify_sentiment::clearly-negative  samples 3/3
  PASS  classify_sentiment::clearly-positive  samples 3/3
  PASS  extract_email::no-email-present       samples 3/3
  PASS  extract_email::simple                 samples 3/3
  PASS  structured_person::ada                samples 3/3

5/5 cases passed (3 sample(s)/case, pass_rate>=1.0) in 10.4s
```

## It caught a real bug during its own development

`examples/caught-regression.yaml` is kept in the repo as a specimen: llama3.1:8b, asked to extract emails verbatim, silently normalizes "jane dot doe at acme dot io" into `jane.doe@acme.io` - fabricating an address the user never wrote. In a CRM or compliance pipeline, that's invented data.

```
  FAIL  extract_email_verbatim::spelled-out-address-must-not-be-invented  samples 0/3
        not_contains: forbidden '@' present

0/1 cases passed (3 sample(s)/case, pass_rate>=1.0) in 2.5s
```

Exit code 1 -> your CI goes red. That's the tool doing its job.

## Assertions

| type | checks |
|---|---|
| `equals` | exact match (`strip`, `case_sensitive` options) |
| `contains` / `not_contains` | substring presence/absence |
| `regex` | pattern match against raw output |
| `json_valid` | output parses as JSON (markdown fences tolerated) |
| `json_field` | dot-path lookup (`user.tags.1`) equals a value, or just exists |
| `max_chars` | output length budget |

## Sampling semantics (the honest part)

Every case runs `samples` times; a case passes when the fraction of passing samples >= `pass_rate`. `samples: 3, pass_rate: 1.0` demands determinism; `samples: 5, pass_rate: 0.8` tolerates one flake in five and tells you the measured fraction instead of hiding it. Provider errors (connection refused, bad key) are reported as errors, never as silent passes.

## Install & run

```bash
git clone https://github.com/afshafathima/promptproof && cd promptproof
uv sync
uv run promptproof examples/extraction.yaml --report report.json --junit results.xml
```

Needs Ollama with `ollama pull llama3.1:8b` for the default provider, or `ANTHROPIC_API_KEY` + `provider: anthropic`. `provider: fake` echoes each case's rendered input back - dry-run your assertions with no model at all.

In GitHub Actions, publish `results.xml` with any JUnit reporter and prompt regressions show up like failing unit tests.

## Development

```bash
uv run pytest -q        # 14 tests: assertions, sampling semantics, runner, CLI, reports
uv run ruff check src tests && uv run mypy src
```

CI runs lint, types, tests, and validates every example suite on each push.

## What I'd build next

- `promptproof diff a.json b.json` - compare two report files across models/prompt versions.
- Cost/latency budgets as assertions (`max_seconds`, `max_tokens`).
- An LLM-graded `rubric` assertion, kept separate from the deterministic ones and clearly labeled as judge-based.

## Maintainer

Afsha Fathima is a Python Backend Developer with over 4 years of experience building backend applications, REST APIs, and service integrations. She maintains this project with a focus on creating reliable, testable, and maintainable AI-integrated solutions.

Email: fathimaafsha08@gmail.com
LinkedIn: https://www.linkedin.com/in/afsha-fathima-lnu-a29996298/