"""Loop + verifier tests with a scripted stand-in for the model."""
import json

from conftest import ScriptedClient, reply, text, tool_results_in, tool_use

from triage_agent.agent import run_ticket
from triage_agent.verifier import file_sha256, score_against_expected, verify


def by_name(checks):
    return {c.name: c for c in checks}


def test_model_recovers_from_rejected_p1_and_note_verifies(tickets, out_dir):
    """Model tries P1 too early -> tool rejects -> model looks up customer -> retries -> note verifies."""
    task = {"ticket_id": "T-1005", "priority": "P1", "title": "SSO SAML 500 outage", "owner_team": "auth",
            "impact_summary": "~1,100 users locked out", "rationale": "Enterprise production outage"}
    client = ScriptedClient([
        reply(tool_use("propose_priority_and_task", {**task, "evidence_ids": []})),
        reply(tool_use("lookup_customer", {"customer_id": "C-317"})),
        reply(tool_use("propose_priority_and_task", {**task, "evidence_ids": ["C-317"]})),
        reply(tool_use("submit_next_action_note", {
            "ticket_id": "T-1005", "action": "task_proposed", "priority": "P1",
            "note": "Enterprise SSO outage for ~1,100 users (C-317, 2h SLA). Proposed P1 task TASK-0001 for auth.",
            "draft_reply": "", "evidence_ids": ["C-317", "TASK-0001"]})),
    ])
    before = file_sha256()
    result, ctx = run_ticket(tickets["T-1005"], client, out_dir)

    # the rejection was fed back to the model as an error observation
    first_results = tool_results_in(client.requests[1])
    assert first_results[0]["is_error"] and "lookup_customer" in first_results[0]["content"]

    assert result.status == "completed" and result.steps == 4
    checks = verify(result, ctx, before)
    assert all(c.passed for c in checks), [c for c in checks if not c.passed]
    assert score_against_expected(result.final_note, tickets["T-1005"]["expected"]).passed


def test_model_never_sees_grading_labels(tickets, out_dir):
    client = ScriptedClient([reply(text("hmm")), reply(text("still nothing"))])
    run_ticket(tickets["T-1003"], client, out_dir)
    first_user = client.requests[0]["messages"][0]["content"]
    assert "expected" not in first_user and "problem case" not in first_user


def test_no_note_fails_verification(tickets, out_dir):
    client = ScriptedClient([reply(text("I think it's fine.")), reply(text("Done."))])
    before = file_sha256()
    result, ctx = run_ticket(tickets["T-1003"], client, out_dir)
    assert result.status == "no_note"
    assert not by_name(verify(result, ctx, before))["note_submitted"].passed


def test_step_limit(tickets, out_dir):
    client = ScriptedClient([reply(tool_use("search_faq", {"query": "password"}, i)) for i in range(3)])
    result, _ = run_ticket(tickets["T-1001"], client, out_dir, max_steps=3)
    assert result.status == "max_steps"


def test_tool_failure_then_escalation_verifies(tickets, out_dir):
    client = ScriptedClient([
        reply(tool_use("search_faq", {"query": "reset password"})),
        reply(tool_use("submit_next_action_note", {
            "ticket_id": "T-1001", "action": "escalate_human", "priority": "none",
            "note": "Password-reset question, but FAQ search was unavailable (timeout), so no answer was verified. "
                    "Please have support reply manually or rerun once search recovers.",
            "draft_reply": "", "evidence_ids": []})),
    ])
    before = file_sha256()
    result, ctx = run_ticket(tickets["T-1001"], client, out_dir, fail_tools={"search_faq"})
    assert tool_results_in(client.requests[1])[0]["content"].startswith("TOOL_UNAVAILABLE")
    checks = verify(result, ctx, before)
    assert all(c.passed for c in checks), [c for c in checks if not c.passed]
    assert ctx.faq_matches == {}  # nothing from the FAQ could have been cited


def test_faq_answer_with_unreturned_faq_id_is_rejected(tickets, out_dir):
    """The tool layer refuses an id the model never saw, so a hallucinated citation cannot be recorded."""
    client = ScriptedClient([
        reply(tool_use("submit_next_action_note", {
            "ticket_id": "T-1007", "action": "faq_answer", "priority": "none",
            "note": "Answered from FAQ F-02.", "draft_reply": "See Billing > Invoices.",
            "evidence_ids": ["F-02"]})),
        reply(text("ok")), reply(text("ok")),
    ])
    result, ctx = run_ticket(tickets["T-1007"], client, out_dir)
    assert tool_results_in(client.requests[1])[0]["is_error"]
    assert result.final_note is None


def test_verifier_catches_side_effect_claim_and_priority_mismatch(tickets, out_dir):
    client = ScriptedClient([
        reply(tool_use("lookup_customer", {"customer_id": "C-422"})),
        reply(tool_use("propose_priority_and_task", {
            "ticket_id": "T-1006", "priority": "P3", "title": "Possible double charge", "owner_team": "billing",
            "impact_summary": "one Free-plan user", "rationale": "billing dispute", "evidence_ids": ["C-422"]})),
        reply(tool_use("submit_next_action_note", {
            "ticket_id": "T-1006", "action": "task_proposed", "priority": "P4",
            "note": "We have refunded the customer and closed it.", "draft_reply": "",
            "evidence_ids": ["C-422", "TASK-0001"]})),
    ])
    before = file_sha256()
    result, ctx = run_ticket(tickets["T-1006"], client, out_dir)
    checks = by_name(verify(result, ctx, before))
    assert not checks["no_side_effect_claims"].passed
    assert not checks["action_supported"].passed  # note says P4, file on disk says P3
    assert checks["live_tickets_unchanged"].passed


def test_verifier_detects_modified_ticket_file(tickets, out_dir):
    client = ScriptedClient([reply(text("x")), reply(text("y"))])
    result, ctx = run_ticket(tickets["T-1003"], client, out_dir)
    assert not by_name(verify(result, ctx, "not-the-real-hash"))["live_tickets_unchanged"].passed


def test_expected_scoring_flags_forbidden_priority(tickets):
    note = {"action": "task_proposed", "priority": "P1", "evidence_ids": [], "note": "", "draft_reply": ""}
    assert not score_against_expected(note, tickets["T-1006"]["expected"]).passed


def test_live_ticket_file_is_never_written(tickets, out_dir):
    before = file_sha256()
    client = ScriptedClient([
        reply(tool_use("request_missing_info", {"ticket_id": "T-1008",
                                                "missing_fields": ["device_os", "app_version", "file_details"],
                                                "question": "Which device and app version, and what file were you uploading?"})),
        reply(tool_use("submit_next_action_note", {
            "ticket_id": "T-1008", "action": "needs_info", "priority": "none",
            "note": "Crash report lacks device, version and file details. Draft D-0001 asks for them.",
            "draft_reply": "", "evidence_ids": ["D-0001"]})),
    ])
    result, ctx = run_ticket(tickets["T-1008"], client, out_dir)
    assert file_sha256() == before
    assert json.loads(ctx.drafts_path.read_text())[0]["status"] == "draft_not_sent"
    assert all(c.passed for c in verify(result, ctx, before))
