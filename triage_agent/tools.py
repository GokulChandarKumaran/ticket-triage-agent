"""Tools the model can choose between, plus the sandbox they write to.

Every tool is local and side-effect-safe:
  * search_faq / lookup_customer only read sample data.
  * request_missing_info and propose_priority_and_task write DRAFTS to the
    run's output folder. Nothing is sent, and the live ticket file is never
    written.
  * submit_next_action_note ends the run.

Each successful call records the evidence ids it produced in the ToolContext
ledger, so the verifier can later check the model's claims against what the
tools actually returned.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

PRIORITIES = ["P1", "P2", "P3", "P4"]
TEAMS = ["auth", "billing", "data-export", "mobile", "platform", "privacy", "product"]
MISSING_FIELDS = [
    "customer_id",
    "steps_to_reproduce",
    "app_version",
    "device_os",
    "error_message",
    "file_details",
    "affected_users",
    "expected_behavior",
]
ACTIONS = ["faq_answer", "needs_info", "task_proposed", "escalate_human"]
FAQ_MATCH_THRESHOLD = 0.34  # minimum score for a result to count as a real match


class ToolError(Exception):
    """A tool rejected its input or could not run. Sent back with is_error=true."""


# --------------------------------------------------------------------------- #
# Tool schemas sent to the model
# --------------------------------------------------------------------------- #
def _schema(props: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": props,
        "required": required if required is not None else list(props),
        "additionalProperties": False,
    }


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "search_faq",
        "description": (
            "Search the product FAQ / help-center knowledge base. Use when the ticket "
            "looks like a how-to or policy question that documentation could answer. "
            "Returns up to 3 entries with a relevance score; only results with "
            "match=true are real matches. Do not use it for clear bug reports."
        ),
        "strict": True,
        "input_schema": _schema({"query": {"type": "string", "description": "Short keyword query."}}),
    },
    {
        "name": "lookup_customer",
        "description": (
            "Look up the customer's account record (plan, seats, SLA response hours, "
            "open tickets). Use before setting P1 or P2, or whenever plan or impact "
            "matters. Fails if the id does not exist."
        ),
        "strict": True,
        "input_schema": _schema({"customer_id": {"type": "string", "description": "e.g. C-204"}}),
    },
    {
        "name": "request_missing_info",
        "description": (
            "Draft a clarifying question for the customer when the ticket lacks the "
            "information needed to answer or triage it. The draft is saved for the "
            "product manager to review; it is NOT sent."
        ),
        "strict": True,
        "input_schema": _schema(
            {
                "ticket_id": {"type": "string"},
                "missing_fields": {
                    "type": "array",
                    "items": {"type": "string", "enum": MISSING_FIELDS},
                    "description": "Which pieces of information are missing.",
                },
                "question": {"type": "string", "description": "Polite question to the customer, under 80 words."},
            }
        ),
    },
    {
        "name": "propose_priority_and_task",
        "description": (
            "Prepare a PROPOSED priority and engineering/product task entry for this "
            "ticket. Saved to the proposals file for PM review; it does not change the "
            "live ticket. P1 and P2 are rejected unless lookup_customer succeeded in "
            "this run. evidence_ids must be ids returned by earlier tool calls."
        ),
        "strict": True,
        "input_schema": _schema(
            {
                "ticket_id": {"type": "string"},
                "priority": {"type": "string", "enum": PRIORITIES},
                "title": {"type": "string", "description": "Task title, under 12 words."},
                "owner_team": {"type": "string", "enum": TEAMS},
                "impact_summary": {"type": "string", "description": "Who is affected and how badly."},
                "rationale": {"type": "string", "description": "Why this priority, citing the policy."},
                "evidence_ids": {"type": "array", "items": {"type": "string"}},
            }
        ),
    },
    {
        "name": "submit_next_action_note",
        "description": (
            "Finish the ticket: submit the short next-action note for the product "
            "manager. Call exactly once, as the last step. evidence_ids must list the "
            "FAQ ids, customer ids, draft ids or task ids that support the note."
        ),
        "strict": True,
        "input_schema": _schema(
            {
                "ticket_id": {"type": "string"},
                "action": {"type": "string", "enum": ACTIONS},
                "priority": {"type": "string", "enum": PRIORITIES + ["none"]},
                "note": {"type": "string", "description": "Next-action note for the PM, at most 90 words."},
                "draft_reply": {
                    "type": "string",
                    "description": "Suggested customer reply for the PM to review, or empty string.",
                },
                "evidence_ids": {"type": "array", "items": {"type": "string"}},
            }
        ),
    },
]

TOOL_NAMES = [t["name"] for t in TOOL_SCHEMAS]


# --------------------------------------------------------------------------- #
# Run context: sandbox paths + ledger of observed evidence
# --------------------------------------------------------------------------- #
@dataclass
class ToolContext:
    ticket: dict
    output_dir: Path
    fail_tools: set[str] = field(default_factory=set)  # tool names to force-fail (testing)
    observed_ids: set[str] = field(default_factory=set)
    faq_matches: dict[str, float] = field(default_factory=dict)  # faq id -> best score seen
    customer_verified: str | None = None
    drafts: list[str] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)
    final_note: dict | None = None

    @property
    def drafts_path(self) -> Path:
        return self.output_dir / "drafts.json"

    @property
    def tasks_path(self) -> Path:
        return self.output_dir / "proposed_tasks.json"


def _load(name: str) -> Any:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def _append_record(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    records.append(record)
    path.write_text(json.dumps(records, indent=2), encoding="utf-8")


def _next_id(prefix: str, path: Path) -> str:
    count = len(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else 0
    return f"{prefix}-{count + 1:04d}"


def _require_ticket(ctx: ToolContext, ticket_id: str) -> None:
    if ticket_id != ctx.ticket["ticket_id"]:
        raise ToolError(f"ticket_id {ticket_id!r} does not match the ticket being triaged ({ctx.ticket['ticket_id']}).")


def _check_evidence(ctx: ToolContext, ids: list[str]) -> None:
    unknown = [i for i in ids if i not in ctx.observed_ids]
    if unknown:
        raise ToolError(
            f"evidence_ids {unknown} were not returned by any successful tool call in this run. "
            f"Known ids: {sorted(ctx.observed_ids) or 'none'}."
        )


# --------------------------------------------------------------------------- #
# Tool implementations
# --------------------------------------------------------------------------- #
_WORD = re.compile(r"[a-z0-9][a-z0-9\-]*")
_STOP = {"the", "a", "an", "to", "my", "i", "how", "do", "can", "is", "it", "of", "for", "and", "in", "on", "me", "where", "what"}


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


def search_faq(ctx: ToolContext, query: str) -> dict:
    q = _tokens(query)
    if not q:
        raise ToolError("query is empty after removing stop words; use specific keywords.")
    results = []
    for entry in _load("faq.json"):
        doc = set(entry["tags"]) | _tokens(entry["question"])
        overlap = q & doc
        score = round(len(overlap) / len(q), 2)
        if score > 0:
            results.append({"faq_id": entry["id"], "score": score, "match": score >= FAQ_MATCH_THRESHOLD,
                            "question": entry["question"], "answer": entry["answer"]})
    results.sort(key=lambda r: r["score"], reverse=True)
    results = results[:3]
    for r in results:
        if r["match"]:
            ctx.observed_ids.add(r["faq_id"])
            ctx.faq_matches[r["faq_id"]] = max(r["score"], ctx.faq_matches.get(r["faq_id"], 0))
    return {"query": query, "results": results,
            "summary": f"{sum(r['match'] for r in results)} matching entries" if results else "no matching entries"}


def lookup_customer(ctx: ToolContext, customer_id: str) -> dict:
    for c in _load("customers.json"):
        if c["customer_id"] == customer_id:
            ctx.observed_ids.add(customer_id)
            ctx.customer_verified = customer_id
            return c
    raise ToolError(f"customer {customer_id!r} not found in the account system.")


def request_missing_info(ctx: ToolContext, ticket_id: str, missing_fields: list[str], question: str) -> dict:
    _require_ticket(ctx, ticket_id)
    if not missing_fields:
        raise ToolError("missing_fields must list at least one field.")
    if len(question.split()) > 80:
        raise ToolError("question is longer than 80 words; shorten it.")
    draft_id = _next_id("D", ctx.drafts_path)
    record = {"draft_id": draft_id, "ticket_id": ticket_id, "missing_fields": missing_fields,
              "question": question, "status": "draft_not_sent"}
    _append_record(ctx.drafts_path, record)
    ctx.observed_ids.add(draft_id)
    ctx.drafts.append(draft_id)
    return record


def propose_priority_and_task(ctx: ToolContext, ticket_id: str, priority: str, title: str, owner_team: str,
                              impact_summary: str, rationale: str, evidence_ids: list[str]) -> dict:
    _require_ticket(ctx, ticket_id)
    if ctx.tasks:
        raise ToolError(f"a task ({ctx.tasks[0]}) was already proposed for this ticket.")
    if priority in ("P1", "P2") and not ctx.customer_verified:
        raise ToolError(f"{priority} requires a successful lookup_customer in this run to confirm plan/SLA. "
                        "Look up the customer first, or choose a lower priority and explain why.")
    _check_evidence(ctx, evidence_ids)
    task_id = _next_id("TASK", ctx.tasks_path)
    record = {"task_id": task_id, "ticket_id": ticket_id, "priority": priority, "title": title,
              "owner_team": owner_team, "impact_summary": impact_summary, "rationale": rationale,
              "evidence_ids": evidence_ids, "status": "proposed_pending_pm_review"}
    _append_record(ctx.tasks_path, record)
    ctx.observed_ids.add(task_id)
    ctx.tasks.append(task_id)
    return record


def submit_next_action_note(ctx: ToolContext, ticket_id: str, action: str, priority: str, note: str,
                            draft_reply: str, evidence_ids: list[str]) -> dict:
    _require_ticket(ctx, ticket_id)
    _check_evidence(ctx, evidence_ids)
    if len(note.split()) > 90:
        raise ToolError("note is longer than 90 words; shorten it.")
    if action == "task_proposed" and not ctx.tasks:
        raise ToolError("action is task_proposed but no task was proposed in this run.")
    if action == "needs_info" and not ctx.drafts:
        raise ToolError("action is needs_info but no clarifying-question draft exists in this run.")
    ctx.final_note = {"ticket_id": ticket_id, "action": action, "priority": priority, "note": note,
                      "draft_reply": draft_reply, "evidence_ids": evidence_ids}
    return {"status": "note_recorded", "ticket_id": ticket_id}


_IMPLS = {
    "search_faq": search_faq,
    "lookup_customer": lookup_customer,
    "request_missing_info": request_missing_info,
    "propose_priority_and_task": propose_priority_and_task,
    "submit_next_action_note": submit_next_action_note,
}

_SIMULATED_FAILURES = {
    "search_faq": "TOOL_UNAVAILABLE: knowledge-base search timed out after 10s (HTTP 504).",
    "lookup_customer": "TOOL_UNAVAILABLE: account service returned HTTP 503.",
}


def execute_tool(ctx: ToolContext, name: str, args: dict) -> tuple[dict | str, bool]:
    """Run a tool. Returns (result, is_error). Never raises for tool-level problems."""
    if name not in _IMPLS:
        return f"Unknown tool {name!r}. Available: {TOOL_NAMES}", True
    if name in ctx.fail_tools:
        return _SIMULATED_FAILURES.get(name, f"TOOL_UNAVAILABLE: {name} failed."), True
    try:
        return _IMPLS[name](ctx, **args), False
    except ToolError as e:
        return f"ERROR: {e}", True
    except TypeError as e:  # wrong / missing arguments
        return f"ERROR: bad arguments for {name}: {e}", True
