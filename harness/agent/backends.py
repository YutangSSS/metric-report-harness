"""Model backends. The agent only needs two calls: JSON that matches a schema, and plain text.

- ApiBackend:      Anthropic SDK (needs ANTHROPIC_API_KEY or an `ant auth login` profile)
- ClaudeCliBackend: the local `claude` CLI in print mode (uses the Claude Code login, no API key)
- ScriptedBackend:  canned answers, for tests; never calls a model
"""
from __future__ import annotations

import json
import subprocess
from typing import Any, Callable, Protocol

MODEL = "claude-opus-5-5"


class Backend(Protocol):
    name: str

    def json(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]: ...

    def text(self, system: str, prompt: str) -> str: ...


class ModelError(RuntimeError):
    pass


class ApiBackend:
    name = "api"

    def __init__(self, model: str = MODEL, effort: str = "low"):
        import anthropic

        self.client = anthropic.Anthropic()
        self.model = model
        self.effort = effort

    def _call(self, system: str, prompt: str, fmt: dict | None):
        output_config: dict[str, Any] = {"effort": self.effort}
        if fmt:
            output_config["format"] = fmt
        # Server-side fallback: if a safety classifier declines, the API retries on a fallback model.
        resp = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=system,
            output_config=output_config,
            messages=[{"role": "user", "content": prompt}],
        )
        if resp.stop_reason == "refusal":
            raise ModelError(f"model declined: {getattr(resp.stop_details, 'category', None)}")
        if resp.stop_reason == "max_tokens":
            raise ModelError("model output was cut off at max_tokens")
        return "".join(b.text for b in resp.content if b.type == "text")

    def json(self, system, prompt, schema):
        return json.loads(self._call(system, prompt, {"type": "json_schema", "schema": schema}))

    def text(self, system, prompt):
        return self._call(system, prompt, None)


class ClaudeCliBackend:
    """Runs `claude -p` with no tools, no session saved, and our own system prompt."""

    name = "claude-cli"

    def __init__(self, model: str = MODEL, timeout: int = 180):
        self.model, self.timeout = model, timeout

    def _run(self, system: str, prompt: str, schema: dict | None) -> dict[str, Any]:
        cmd = ["claude", "-p", "--model", self.model, "--output-format", "json", "--tools", "",
               "--no-session-persistence", "--system-prompt", system]
        if schema:
            cmd += ["--json-schema", json.dumps(schema)]
        out = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=self.timeout)
        if out.returncode != 0:
            raise ModelError(f"claude CLI failed: {out.stderr.strip()[:300]}")
        data = json.loads(out.stdout)
        if data.get("is_error"):
            raise ModelError(f"claude CLI error: {data.get('subtype')}")
        return data

    def json(self, system, prompt, schema):
        data = self._run(system, prompt, schema)
        return data.get("structured_output") or json.loads(data["result"])

    def text(self, system, prompt):
        return self._run(system, prompt, None)["result"]


class ScriptedBackend:
    """Returns canned answers chosen by a function of the prompt. For tests and offline demos."""

    name = "scripted"

    def __init__(self, json_answer: Callable[[str], dict] | None = None, text_answer: Callable[[str], str] | None = None):
        self._json, self._text = json_answer, text_answer

    def json(self, system, prompt, schema):
        if self._json is None:
            raise ModelError("no scripted JSON answer")
        return self._json(prompt)

    def text(self, system, prompt):
        if self._text is None:
            raise ModelError("no scripted text answer")
        return self._text(prompt)


def get_backend(name: str) -> Backend:
    if name == "api":
        return ApiBackend()
    if name in ("cli", "claude-cli"):
        return ClaudeCliBackend()
    raise ValueError(f"unknown backend {name!r} (use api or cli)")
