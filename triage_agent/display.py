"""Console output for demos: shows each model decision, tool call, tool result and verdict."""
from __future__ import annotations

import json
import sys
import textwrap

_USE_COLOR = sys.stdout.isatty()
_C = {"dim": "2", "cyan": "36", "yellow": "33", "green": "32", "red": "31", "magenta": "35", "bold": "1"}


def _c(text: str, color: str) -> str:
    return f"\033[{_C[color]}m{text}\033[0m" if _USE_COLOR else text


def _short(obj, limit: int = 600) -> str:
    s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    return s if len(s) <= limit else s[:limit] + " ..."


def _wrap(text: str, indent: str = "    ") -> str:
    return textwrap.fill(" ".join(text.split()), width=100, initial_indent=indent, subsequent_indent=indent)


def print_event(e: dict) -> None:
    t = e["type"]
    if t == "start":
        tk = e["ticket"]
        print(_c(f"\n=== Ticket {tk['ticket_id']}: {tk['subject']} ===", "bold"))
        print(_wrap(tk["body"]))
        if e["fail_tools"]:
            print(_c(f"    [test] simulating failure of: {', '.join(e['fail_tools'])}", "red"))
    elif t == "thinking":
        print(_c(f"  [step {e['step']}] MODEL REASONING (summary)", "magenta"))
        print(_c(_wrap(e["text"][:700]), "dim"))
    elif t == "text":
        print(_c(f"  [step {e['step']}] MODEL SAYS:", "magenta"), _short(e["text"], 300))
    elif t == "tool_call":
        print(_c(f"  [step {e['step']}] DECISION -> {e['tool']}", "cyan"), _short(e["input"], 400))
    elif t == "tool_result":
        tag, col = ("TOOL ERROR", "red") if e["is_error"] else ("TOOL RESULT", "yellow")
        print(_c(f"  [step {e['step']}] {tag} <- {e['tool']}", col), _short(e["output"]))
    elif t == "nudge":
        print(_c(f"  [step {e['step']}] HARNESS: {e['text']}", "red"))
    elif t in ("refusal", "api_error", "stopped"):
        print(_c(f"  !! {t.upper()}: {e.get('detail') or e.get('error') or e.get('reason')}", "red"))
    elif t == "fallback":
        print(_c(f"  [step {e['step']}] FALLBACK MODEL USED: {_short(e['detail'], 200)}", "red"))
    elif t == "final_note":
        n = e["note"]
        print(_c(f"  FINAL NOTE  action={n['action']}  priority={n['priority']}  evidence={n['evidence_ids']}", "green"))
        print(_wrap(n["note"]))


def print_checks(checks, header: str = "VERIFIER (checks against files and tool ledger)") -> None:
    print(_c(f"  {header}", "bold"))
    for ch in checks:
        mark = _c("PASS", "green") if ch.passed else _c("FAIL", "red")
        print(f"    {mark}  {ch.name:<24} {ch.detail}")
