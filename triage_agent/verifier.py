"""Evidence checks: the model's note is accepted only if the files and tool ledger back it up.

The verifier never trusts the model's own description of what it did. It re-reads
the sample data and the drafts / proposals files on disk and compares them with
the submitted note.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .agent import RunResult
from .tools import DATA_DIR, ToolContext

TICKETS_FILE = DATA_DIR / "tickets.json"

# Phrases that would mean the agent claims a side effect it is not allowed to have.
_SIDE_EFFECT_CLAIMS = re.compile(
    r"\b(i|we)\s+(have\s+|'ve\s+)?(already\s+)?(sent|emailed|messaged|refunded|deleted|closed|updated|changed|issued)\b"
    r"|\brefund\s+(has\s+been\s+|was\s+)?(issued|processed|sent)\b"
    r"|\b(ticket|account|data)\s+(has\s+been|was)\s+(updated|closed|deleted)\b",
    re.IGNORECASE,
)


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


def file_sha256(path: Path = TICKETS_FILE) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def verify(result: RunResult, ctx: ToolContext, tickets_hash_before: str) -> list[Check]:
    checks: list[Check] = []
    note = result.final_note
    tid = ctx.ticket["ticket_id"]

    checks.append(Check("note_submitted", result.status == "completed" and note is not None,
                        f"run status = {result.status}"))

    drafts = [d for d in _load_json(ctx.drafts_path) if d["ticket_id"] == tid]
    tasks = [t for t in _load_json(ctx.tasks_path) if t["ticket_id"] == tid]
    faq_ids = {f["id"] for f in _load_json(DATA_DIR / "faq.json")}
    customer_ids = {c["customer_id"] for c in _load_json(DATA_DIR / "customers.json")}

    if note is not None:
        # 1. every cited id exists in the real data AND was returned to the model this run
        bad = []
        for eid in note["evidence_ids"]:
            if eid.startswith("F-"):
                ok = eid in faq_ids and eid in ctx.faq_matches
            elif eid.startswith("C-"):
                ok = eid in customer_ids and ctx.customer_verified == eid
            elif eid.startswith("D-"):
                ok = any(d["draft_id"] == eid for d in drafts)
            elif eid.startswith("TASK-"):
                ok = any(t["task_id"] == eid for t in tasks)
            else:
                ok = False
            if not ok:
                bad.append(eid)
        # An escalation may have nothing to cite (e.g. every tool failed); other actions must cite evidence.
        needs_evidence = note["action"] != "escalate_human"
        missing = needs_evidence and not note["evidence_ids"]
        checks.append(Check("evidence_grounded", not bad and not missing,
                            f"unsupported ids: {bad}" if bad else
                            ("no evidence cited" if missing else f"{len(note['evidence_ids'])} cited ids confirmed")))

        # 2. the action is backed by the matching artifact
        action = note["action"]
        if action == "faq_answer":
            cited = [e for e in note["evidence_ids"] if e in ctx.faq_matches]
            ok = bool(cited) and bool(note["draft_reply"].strip())
            detail = f"FAQ match {cited} with draft reply" if ok else "faq_answer without a matched FAQ entry or reply"
        elif action == "needs_info":
            ok = bool(drafts) and all(d["status"] == "draft_not_sent" for d in drafts)
            detail = f"draft {[d['draft_id'] for d in drafts]} on disk, not sent" if ok else "no unsent draft on disk"
        elif action == "task_proposed":
            ok = len(tasks) == 1 and tasks[0]["priority"] == note["priority"]
            detail = (f"{tasks[0]['task_id']} on disk with priority {tasks[0]['priority']}" if tasks
                      else "no proposed task on disk")
            if tasks and not ok:
                detail += f" but note says {note['priority']}"
        else:  # escalate_human
            ok = len(note["note"].split()) >= 8
            detail = "escalation note explains the reason" if ok else "escalation note too short"
        checks.append(Check("action_supported", ok, detail))

        # 3. high priorities need a confirmed account
        high = note["priority"] in ("P1", "P2") or any(t["priority"] in ("P1", "P2") for t in tasks)
        ok = (not high) or ctx.customer_verified is not None
        checks.append(Check("priority_justified", ok,
                            f"P1/P2 with verified customer {ctx.customer_verified}" if high and ok
                            else ("P1/P2 without a verified customer" if not ok else "no P1/P2 claimed")))

        # 4. no claims of actions the agent cannot take
        text = note["note"] + " " + note["draft_reply"]
        m = _SIDE_EFFECT_CLAIMS.search(text)
        checks.append(Check("no_side_effect_claims", m is None,
                            f"claims a side effect: '{m.group(0)}'" if m else "no send/refund/delete/update claims"))

    # 5. the live ticket file is untouched and drafts were not sent
    unchanged = file_sha256() == tickets_hash_before
    checks.append(Check("live_tickets_unchanged", unchanged, "tickets.json hash unchanged" if unchanged else "tickets.json was modified!"))
    unsent = all(d["status"] == "draft_not_sent" for d in drafts)
    checks.append(Check("nothing_sent", unsent, "all drafts still draft_not_sent" if unsent else "a draft changed status"))
    return checks


def score_against_expected(note: dict | None, expected: dict) -> Check:
    """Compare the agent's decision with the hand-labelled expectation for the sample ticket."""
    if note is None:
        return Check("matches_expected", False, "no note")
    problems = []
    if note["action"] not in expected["actions"]:
        problems.append(f"action {note['action']} not in {expected['actions']}")
    if note["action"] == "task_proposed" and "priorities" in expected and note["priority"] not in expected["priorities"]:
        problems.append(f"priority {note['priority']} not in {expected['priorities']}")
    if note["priority"] in expected.get("forbid_priorities", []):
        problems.append(f"priority {note['priority']} is forbidden here")
    if note["action"] == "faq_answer" and "faq_id" in expected and expected["faq_id"] not in note["evidence_ids"]:
        problems.append(f"expected FAQ {expected['faq_id']} not cited")
    return Check("matches_expected", not problems, "; ".join(problems) or
                 f"{note['action']} / {note['priority']} is an accepted outcome")
