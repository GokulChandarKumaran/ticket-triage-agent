"""Loads the newest eval run from outputs/ and condenses it for the PDF and the slides.

    python docs/results.py   -> writes docs/_build/summary.json
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = Path(__file__).resolve().parent / "_build"
SAMPLE = Path(__file__).resolve().parent / "sample_run"  # committed copy of the run used in the docs


def latest_eval_dir() -> Path | None:
    runs = sorted((ROOT / "outputs").glob("eval_*/eval_results.json"))
    if runs:
        return runs[-1].parent
    return SAMPLE if (SAMPLE / "eval_results.json").exists() else None


def _short(v, n=150) -> str:
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return s if len(s) <= n else s[: n - 3] + "..."


def condense_trace(label: str, run_dir: Path) -> list[dict]:
    data = json.loads((run_dir / "traces" / f"{label}.json").read_text(encoding="utf-8"))
    rows = []
    for e in data["events"]:
        if e["type"] == "thinking":
            rows.append({"step": e["step"], "kind": "reasoning", "text": _short(e["text"], 220)})
        elif e["type"] == "tool_call":
            rows.append({"step": e["step"], "kind": "decision", "text": f"{e['tool']}({_short(e['input'], 130)})"})
        elif e["type"] == "tool_result":
            rows.append({"step": e["step"], "kind": "error" if e["is_error"] else "result",
                         "text": _short(e["output"], 170)})
    return rows


def summary() -> dict | None:
    run_dir = latest_eval_dir()
    if run_dir is None:
        return None
    records = json.loads((run_dir / "eval_results.json").read_text(encoding="utf-8"))
    rows = []
    for r in records:
        n = r["final_note"] or {}
        rows.append({
            "label": r["label"], "case": r["case"], "tools": r["tools_used"],
            "action": n.get("action", "-"), "priority": n.get("priority", "-"),
            "note": n.get("note", ""), "evidence": n.get("evidence_ids", []),
            "verified": r["verified"], "expected_ok": r["expected_check"]["passed"],
            "expected_detail": r["expected_check"]["detail"], "steps": r["steps"],
            "tool_errors": r["tool_errors"],
            "failed_checks": [c for c in r["checks"] if not c["passed"]],
        })
    labels = {r["label"] for r in rows}
    demos = [l for l in ("T-1005", "T-1003", "T-1006", "T-1001_fail-search_faq", "T-1009") if l in labels]
    return {
        "run_dir": str(run_dir.relative_to(ROOT)),
        "rows": rows,
        "n": len(rows),
        "verified": sum(r["verified"] for r in rows),
        "expected_ok": sum(r["expected_ok"] for r in rows),
        "tool_calls": sum(len(r["tools"]) for r in rows),
        "tool_errors": sum(r["tool_errors"] for r in rows),
        "distinct_paths": len({tuple(r["tools"]) for r in rows}),
        "tokens_in": sum(r["usage"]["input_tokens"] for r in records),
        "tokens_out": sum(r["usage"]["output_tokens"] for r in records),
        "traces": {l: condense_trace(l, run_dir) for l in demos},
    }


if __name__ == "__main__":
    BUILD.mkdir(exist_ok=True)
    s = summary()
    (BUILD / "summary.json").write_text(json.dumps(s, indent=2), encoding="utf-8")
    print("no eval run found" if s is None else f"summary of {s['run_dir']}: {s['verified']}/{s['n']} verified")
