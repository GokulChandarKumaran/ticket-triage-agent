"""Runs the agent through the REAL anthropic SDK with a mocked HTTP transport, to check
that requests serialize correctly and responses (thinking + tool_use) round-trip."""
import json

import anthropic
import httpx2 as httpx

from triage_agent.agent import MODEL, run_ticket


def _msg(content, stop="tool_use"):
    return {"id": "msg_test", "type": "message", "role": "assistant", "model": MODEL,
            "content": content, "stop_reason": stop, "stop_sequence": None,
            "usage": {"input_tokens": 100, "output_tokens": 20}}


def test_real_sdk_request_and_response_shapes(tickets, out_dir):
    canned = [
        _msg([{"type": "thinking", "thinking": "Looks like a how-to question; check the FAQ.", "signature": "sig"},
              {"type": "tool_use", "id": "toolu_1", "name": "search_faq", "input": {"query": "download invoices pdf"}}]),
        _msg([{"type": "tool_use", "id": "toolu_2", "name": "submit_next_action_note", "input": {
            "ticket_id": "T-1007", "action": "faq_answer", "priority": "none",
            "note": "Invoice question answered by FAQ F-02. Send the draft reply.",
            "draft_reply": "You can download PDF invoices from Billing > Invoices.", "evidence_ids": ["F-02"]}}]),
    ]
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=canned[len(bodies) - 1])

    client = anthropic.Anthropic(api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    result, ctx = run_ticket(tickets["T-1007"], client, out_dir)

    assert result.status == "completed" and result.final_note["action"] == "faq_answer"
    first = bodies[0]
    assert first["model"] == MODEL
    assert first["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert first["fallbacks"] == "default"
    assert {t["name"] for t in first["tools"]} >= {"search_faq", "lookup_customer", "request_missing_info",
                                                   "propose_priority_and_task", "submit_next_action_note"}
    assert all(t["strict"] and t["input_schema"]["additionalProperties"] is False for t in first["tools"])
    # second request replays the thinking + tool_use block unchanged, then the tool result
    second = bodies[1]["messages"]
    assert second[1]["role"] == "assistant" and second[1]["content"][0]["type"] == "thinking"
    tr = second[2]["content"][0]
    assert tr["type"] == "tool_result" and tr["tool_use_id"] == "toolu_1" and tr["is_error"] is False
    assert "F-02" in tr["content"]
    assert any(e["type"] == "thinking" for e in result.events)
