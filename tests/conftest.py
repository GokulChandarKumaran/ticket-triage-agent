"""Offline test doubles. These replace the API ONLY in tests, so the harness, tools and
verifier can be checked without credentials. The real agent always uses Claude."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from triage_agent.runner import load_tickets  # noqa: E402


def tool_use(name: str, inp: dict, i: int = 0):
    return SimpleNamespace(type="tool_use", id=f"toolu_{name}_{i}", name=name, input=inp)


def text(t: str):
    return SimpleNamespace(type="text", text=t)


def reply(*blocks, stop_reason=None):
    stop = stop_reason or ("tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn")
    return SimpleNamespace(stop_reason=stop, content=list(blocks), model="scripted-test-model",
                           usage=SimpleNamespace(input_tokens=10, output_tokens=5))


class ScriptedClient:
    """Mimics client.beta.messages.create; returns pre-written responses in order and
    records every request so tests can assert what the model was shown."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(copy.deepcopy({k: v for k, v in kwargs.items() if k == "messages"}))
        if not self._responses:
            raise AssertionError("scripted client ran out of responses")
        return self._responses.pop(0)


@pytest.fixture
def tickets():
    return {t["ticket_id"]: t for t in load_tickets()}


@pytest.fixture
def out_dir(tmp_path):
    return tmp_path


def tool_results_in(request: dict) -> list[dict]:
    last = request["messages"][-1]
    return [b for b in last["content"] if isinstance(b, dict) and b.get("type") == "tool_result"] \
        if isinstance(last["content"], list) else []


def as_json(s: str):
    return json.loads(s)
