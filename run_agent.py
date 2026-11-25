"""Triage one ticket (or all) with the live model and show every decision.

Examples:
    python run_agent.py --ticket T-1002
    python run_agent.py --ticket T-1001 --fail-tool search_faq     # tool-failure demo
    python run_agent.py --all
"""
from __future__ import annotations

import argparse
import sys

from triage_agent.runner import load_tickets, make_client, new_run_dir, triage_and_verify, write_pm_notes
from triage_agent.tools import TOOL_NAMES


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--ticket", help="ticket id from data/tickets.json, e.g. T-1002")
    g.add_argument("--all", action="store_true", help="triage every sample ticket")
    p.add_argument("--fail-tool", action="append", default=[], choices=TOOL_NAMES,
                   help="simulate an outage of this tool (repeatable)")
    p.add_argument("--quiet", action="store_true", help="hide the step-by-step trace")
    args = p.parse_args()

    tickets = load_tickets()
    if args.ticket:
        tickets = [t for t in tickets if t["ticket_id"] == args.ticket]
        if not tickets:
            print(f"Unknown ticket {args.ticket}. Known: {[t['ticket_id'] for t in load_tickets()]}")
            return 2

    client = make_client()
    out_dir = new_run_dir("run")
    records = [triage_and_verify(t, client, out_dir, fail_tools=args.fail_tool, verbose=not args.quiet,
                                 label=t["ticket_id"] + ("_fail-" + "-".join(args.fail_tool) if args.fail_tool else ""))
               for t in tickets]
    notes = write_pm_notes(records, out_dir)
    ok = sum(r["verified"] for r in records)
    print(f"\n{ok}/{len(records)} notes verified. PM notes: {notes}")
    print(f"Drafts / proposed tasks / traces: {out_dir}")
    return 0 if ok == len(records) else 1


if __name__ == "__main__":
    sys.exit(main())
