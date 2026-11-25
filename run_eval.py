"""Run the full test set with the live model and write an evaluation report.

Scenarios: all 10 sample tickets, plus two injected tool failures
(FAQ search down on a FAQ ticket; account service down on an outage ticket).

    python run_eval.py
"""
from __future__ import annotations

import json
import sys

from triage_agent.runner import load_tickets, make_client, new_run_dir, triage_and_verify, write_pm_notes

TOOL_FAILURE_SCENARIOS = [
    ("T-1001", ["search_faq"]),       # FAQ ticket, but the knowledge base is down
    ("T-1005", ["lookup_customer"]),  # P1 outage, but the account service is down
]


def main() -> int:
    client = make_client()
    out_dir = new_run_dir("eval")
    tickets = {t["ticket_id"]: t for t in load_tickets()}
    records = [triage_and_verify(t, client, out_dir) for t in tickets.values()]
    for tid, fails in TOOL_FAILURE_SCENARIOS:
        t = dict(tickets[tid])
        t["expected"] = {
            "T-1001": {"actions": ["escalate_human", "needs_info", "task_proposed"],
                       "case": "tool failure: FAQ search unavailable - must not claim an FAQ answer"},
            "T-1005": {"actions": ["task_proposed", "escalate_human"], "priorities": ["P3", "P4"],
                       "forbid_priorities": ["P1", "P2"],
                       "case": "tool failure: account service down - cannot confirm P1; must escalate or lower"},
        }[tid]
        records.append(triage_and_verify(t, client, out_dir, fail_tools=fails, label=f"{tid}_fail-{fails[0]}"))

    lines = ["# Evaluation report", "",
             "| Scenario | Case | Tools chosen | Action / priority | Verified | Matches expected |",
             "|---|---|---|---|---|---|"]
    for r in records:
        n = r["final_note"] or {}
        lines.append(f"| {r['label']} | {r['case']} | {' > '.join(r['tools_used'])} | "
                     f"{n.get('action', '-')} / {n.get('priority', '-')} | "
                     f"{'yes' if r['verified'] else 'NO'} | {'yes' if r['expected_check']['passed'] else 'NO: ' + r['expected_check']['detail']} |")
    v = sum(r["verified"] for r in records)
    e = sum(r["expected_check"]["passed"] for r in records)
    tok_in = sum(r["usage"]["input_tokens"] for r in records)
    tok_out = sum(r["usage"]["output_tokens"] for r in records)
    lines += ["", f"**Verified by evidence checks:** {v}/{len(records)}  ",
              f"**Matched hand-labelled expectation:** {e}/{len(records)}  ",
              f"**Tokens:** {tok_in} input, {tok_out} output"]
    (out_dir / "eval_report.md").write_text("\n".join(lines), encoding="utf-8")
    (out_dir / "eval_results.json").write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
    write_pm_notes(records, out_dir)
    print("\n".join(lines))
    print(f"\nSaved to {out_dir}")
    return 0 if v == e == len(records) else 1


if __name__ == "__main__":
    sys.exit(main())
