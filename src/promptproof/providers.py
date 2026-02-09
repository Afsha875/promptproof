"""LLM providers over httpx. Ollama is the default (local, no key)."""

import os
from typing import Protocol

import httpx


class Provider(Protocol):
    async def complete(self, system: str, prompt: str, temperature: float) -> str: ...


class OllamaProvider:
    def __init__(self, model: str, base_url: str | None = None, timeout: float = 300.0):
        self._model = model
        self._base_url = (
            base_url or os.environ.get("PROMPTPROOF_OLLAMA_URL", "http://localhost:11434")
        ).rstrip("/")
        self._timeout = timeout

    async def complete(self, system: str, prompt: str, temperature: float) -> str:
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temperature},
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]


class AnthropicProvider:
    def __init__(self, model: str, api_key: str | None = None, timeout: float = 120.0):
        self._model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self._api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for provider=anthropic")
        self._timeout = timeout

    async def complete(self, system: str, prompt: str, temperature: float) -> str:
        body: dict = {
            "model": self._model,
            "max_tokens": 2048,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()
            return "".join(
                block["text"] for block in resp.json()["content"] if block["type"] == "text"
            )


class EchoProvider:
    """Returns the prompt unchanged. For dry-running a suite's assertions
    without any model: `provider: fake` makes every case's output equal its
    rendered input."""

    async def complete(self, system: str, prompt: str, temperature: float) -> str:
        return prompt


def build_provider(name: str, model: str) -> Provider:
    match name:
        case "ollama":
            return OllamaProvider(model)
        case "anthropic":
            return AnthropicProvider(model)
        case "fake":
            return EchoProvider()
    raise ValueError(f"unknown provider {name!r}")
