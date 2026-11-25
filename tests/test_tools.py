import json

from triage_agent.agent import public_ticket
from triage_agent.tools import ToolContext, execute_tool


def ctx_for(ticket, out_dir, **kw):
    return ToolContext(ticket=public_ticket(ticket), output_dir=out_dir, **kw)


def test_faq_search_finds_password_entry(tickets, out_dir):
    ctx = ctx_for(tickets["T-1001"], out_dir)
    res, err = execute_tool(ctx, "search_faq", {"query": "reset forgotten password"})
    assert not err
    assert res["results"][0]["faq_id"] == "F-01" and res["results"][0]["match"]
    assert "F-01" in ctx.observed_ids


def test_faq_search_weak_results_are_not_evidence(tickets, out_dir):
    ctx = ctx_for(tickets["T-1001"], out_dir)
    res, err = execute_tool(ctx, "search_faq", {"query": "quantum spaceship billing warp drive"})
    assert not err
    weak = [r for r in res["results"] if not r["match"]]
    assert weak, "expected at least one low-score hit"
    assert not any(r["faq_id"] in ctx.observed_ids for r in weak)  # weak hits never become evidence


def test_unknown_customer_is_an_error_result(tickets, out_dir):
    ctx = ctx_for(tickets["T-1009"], out_dir)
    res, err = execute_tool(ctx, "lookup_customer", {"customer_id": "C-999"})
    assert err and "not found" in res
    assert ctx.customer_verified is None


def test_p1_requires_customer_lookup_first(tickets, out_dir):
    ctx = ctx_for(tickets["T-1005"], out_dir)
    args = {"ticket_id": "T-1005", "priority": "P1", "title": "SSO outage", "owner_team": "auth",
            "impact_summary": "all users", "rationale": "Enterprise outage", "evidence_ids": []}
    res, err = execute_tool(ctx, "propose_priority_and_task", args)
    assert err and "lookup_customer" in res
    assert not ctx.tasks_path.exists()

    execute_tool(ctx, "lookup_customer", {"customer_id": "C-317"})
    res, err = execute_tool(ctx, "propose_priority_and_task", {**args, "evidence_ids": ["C-317"]})
    assert not err and res["status"] == "proposed_pending_pm_review"
    saved = json.loads(ctx.tasks_path.read_text())
    assert saved[0]["priority"] == "P1" and saved[0]["task_id"] == res["task_id"]

    res, err = execute_tool(ctx, "propose_priority_and_task", {**args, "evidence_ids": ["C-317"]})
    assert err and "already proposed" in res


def test_unseen_evidence_ids_are_rejected(tickets, out_dir):
    ctx = ctx_for(tickets["T-1004"], out_dir)
    res, err = execute_tool(ctx, "propose_priority_and_task", {
        "ticket_id": "T-1004", "priority": "P4", "title": "Dark mode", "owner_team": "product",
        "impact_summary": "nice to have", "rationale": "feature request", "evidence_ids": ["F-10"]})
    assert err and "F-10" in res


def test_missing_info_draft_is_saved_unsent(tickets, out_dir):
    ctx = ctx_for(tickets["T-1003"], out_dir)
    res, err = execute_tool(ctx, "request_missing_info", {
        "ticket_id": "T-1003", "missing_fields": ["steps_to_reproduce", "customer_id"],
        "question": "Could you tell us what you were trying to do and your account id?"})
    assert not err and res["status"] == "draft_not_sent"
    assert json.loads(ctx.drafts_path.read_text())[0]["draft_id"] == res["draft_id"]


def test_wrong_ticket_id_rejected(tickets, out_dir):
    ctx = ctx_for(tickets["T-1003"], out_dir)
    res, err = execute_tool(ctx, "request_missing_info", {
        "ticket_id": "T-1002", "missing_fields": ["customer_id"], "question": "?"})
    assert err and "does not match" in res


def test_simulated_tool_outage(tickets, out_dir):
    ctx = ctx_for(tickets["T-1001"], out_dir, fail_tools={"search_faq"})
    res, err = execute_tool(ctx, "search_faq", {"query": "password"})
    assert err and res.startswith("TOOL_UNAVAILABLE")
    assert not ctx.observed_ids


def test_note_cannot_claim_unbacked_action(tickets, out_dir):
    ctx = ctx_for(tickets["T-1003"], out_dir)
    res, err = execute_tool(ctx, "submit_next_action_note", {
        "ticket_id": "T-1003", "action": "needs_info", "priority": "none",
        "note": "Asked customer for details.", "draft_reply": "", "evidence_ids": []})
    assert err and "no clarifying-question draft" in res
    assert ctx.final_note is None
