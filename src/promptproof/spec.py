"""Suite specification: pydantic models + YAML loading.

A suite is a set of prompts; each prompt has cases; each case has assertions.
Sampling is first-class: every case runs `samples` times and must pass in at
least `pass_rate` of them — nondeterminism is measured, not ignored.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

AssertionType = Literal[
    "equals", "contains", "not_contains", "regex", "json_valid", "json_field", "max_chars"
]


class Assertion(BaseModel):
    type: AssertionType
    value: str | int | None = None
    path: str | None = None  # dot path for json_field, e.g. "user.email"
    case_sensitive: bool = True
    strip: bool = True

    @field_validator("value")
    @classmethod
    def _stringify(cls, v):  # YAML numbers arrive as int; normalize later per-type
        return v


class Case(BaseModel):
    name: str
    input: str
    asserts: list[Assertion] = Field(alias="assert", min_length=1)

    model_config = {"populate_by_name": True}


class PromptSpec(BaseModel):
    system: str = ""
    template: str = "{input}"  # rendered with the case input
    cases: list[Case] = Field(min_length=1)


class Suite(BaseModel):
    provider: Literal["ollama", "anthropic", "fake"] = "ollama"
    model: str = "llama3.1:8b"
    temperature: float = 0.0
    samples: int = Field(default=1, ge=1, le=20)
    pass_rate: float = Field(default=1.0, gt=0.0, le=1.0)
    prompts: dict[str, PromptSpec] = Field(min_length=1)


def load_suite(path: Path) -> Suite:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path}: suite file must be a YAML mapping")
    return Suite.model_validate(data)
