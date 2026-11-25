// Builds docs/Ticket_Triage_Agent.pptx from docs/_build/summary.json (python docs/results.py).
//   node docs/build_deck.js
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const HERE = __dirname;
const S = (() => {
  try { return JSON.parse(fs.readFileSync(path.join(HERE, "_build", "summary.json"), "utf8")); } catch { return null; }
})();

const THEME = {
  name: "Triage Teal", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: "1F2A37", lt1: "FFFFFF", dk2: "0B3B37", lt2: "EEF4F3", accent1: "0F766E", accent2: "B42318",
            accent3: "15803D", accent4: "D97706", accent5: "64748B", accent6: "99F6E4", hlink: "0F766E", folHlink: "64748B" },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Ticket Triage Agent";
pres.author = "Gokul Chandar Kumaran";
// Plain hex colours so the deck builds the same anywhere (no theme post-processing step needed).
const C = { text1: HEX.dk1, text2: HEX.dk2, background1: HEX.lt1, background2: HEX.lt2, accent1: HEX.accent1,
            accent2: HEX.accent2, accent3: HEX.accent3, accent4: HEX.accent4, accent5: HEX.accent5 };

pres.defineSlideMaster({
  title: "Dark title", background: { color: HEX.dk2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.5, w: 8.8, h: 1.2, fontSize: 40, bold: true, color: C.background1, valign: "bottom" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 2.8, w: 8.8, h: 1.4, fontSize: 18, color: "99F6E4", valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "Content", background: { color: HEX.lt1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.75, fontSize: 26, bold: true, color: C.text2, valign: "middle" }, text: "" } },
  ],
  slideNumber: { x: 9.2, y: 5.25, w: 0.5, h: 0.3, fontSize: 10, color: "64748B" },
});

let n = 0;
const obj = (name) => `${name}_${++n}`;
const T = (slide, text, o) => slide.addText(text, { isTextBox: true, fontSize: 14, color: C.text1, margin: 0.05, objectName: obj("text"), ...o });

function card(slide, x, y, w, h, head, body, accent = C.accent1, fill = C.background2) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.08, objectName: obj("card") });
  T(slide, head, { x: x + 0.15, y: y + 0.1, w: w - 0.3, h: 0.4, fontSize: 15, bold: true, color: accent });
  T(slide, body, { x: x + 0.15, y: y + 0.5, w: w - 0.3, h: h - 0.6, fontSize: 12.5, valign: "top" });
}

function circleNum(slide, x, y, label, color = C.accent1) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: 0.42, h: 0.42, fill: { color }, line: { color }, objectName: obj("dot") });
  T(slide, label, { x, y, w: 0.42, h: 0.42, fontSize: 13, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0 });
}

// ---------- 1. Title
pres.addSection({ title: "Intro" });
let s = pres.addSlide({ masterName: "Dark title", sectionTitle: "Intro" });
s.addText("Ticket Triage Agent", { placeholder: "title" });
s.addText("An LLM agent that decides the next action on support tickets and leaves evidence-checked notes for a product manager\n\nGokul Chandar Kumaran", { placeholder: "body" });
s.addNotes("Introduce the project: an agent that does first-pass triage of support tickets for a PM, using Claude Opus 5.5 with five tools.");

// ---------- 2. Problem
s = pres.addSlide({ masterName: "Content", sectionTitle: "Intro" });
s.addText("Every ticket needs one of three next steps", { placeholder: "title" });
T(s, "A PM triaging a support queue has to decide, ticket by ticket, which lookup to do and what to hand over. A wrong call wastes engineering time or leaves an Enterprise outage waiting.",
  { x: 0.5, y: 1.2, w: 3.4, h: 2.0, fontSize: 15, valign: "top" });
T(s, "The agent does this first pass. It never sends messages or edits live tickets: everything is a draft for the PM.",
  { x: 0.5, y: 3.3, w: 3.4, h: 1.4, fontSize: 15, italic: true, color: C.accent1, valign: "top" });
card(s, 4.3, 1.2, 5.2, 1.05, "Answer from the FAQ", "How-to and policy questions the help centre already covers -> draft reply for the PM.");
card(s, 4.3, 2.4, 5.2, 1.05, "Ask for missing information", "\"It doesn't work.\" -> draft a clarifying question (not sent).");
card(s, 4.3, 3.6, 5.2, 1.05, "Propose a priority and task", "Real bugs and outages -> check the account, then a P1-P4 task proposal.");
s.addNotes("Problem statement and why it is useful: the PM gets short notes with evidence instead of reading every ticket.");

// ---------- 3. Workflow
pres.addSection({ title: "How it works" });
s = pres.addSlide({ masterName: "Content", sectionTitle: "How it works" });
s.addText("Each step is chosen from what the model observed", { placeholder: "title" });
s.addImage({ path: path.join(HERE, "workflow.png"), x: 1.2, y: 1.1, w: 7.4, h: 7.4 * 1134 / 1880, objectName: "workflow_diagram" });
s.addNotes("Walk through the loop: ticket in, Claude decides, tool runs, result or error fed back, Claude decides again, final note, verifier re-reads files.");

// ---------- 4. Tools
s = pres.addSlide({ masterName: "Content", sectionTitle: "How it works" });
s.addText("Five tools, with the rules built into them", { placeholder: "title" });
const tools = [
  ["search_faq", "Top 3 FAQ entries with scores. Only match=true results can be cited."],
  ["lookup_customer", "Plan, seats, SLA. Unknown id returns an error."],
  ["request_missing_info", "Saves a clarifying question as draft_not_sent."],
  ["propose_priority_and_task", "Saves a P1-P4 proposal. P1/P2 rejected until the account is verified."],
  ["submit_next_action_note", "Final step. Rejected if the draft or task it mentions does not exist."],
];
tools.forEach(([name, desc], i) => {
  const y = 1.2 + i * 0.78;
  circleNum(s, 0.6, y + 0.08, String(i + 1));
  T(s, name, { x: 1.2, y, w: 3.5, h: 0.6, fontSize: 14, bold: true, fontFace: "Courier New", color: C.text2, valign: "middle" });
  T(s, desc, { x: 4.8, y, w: 4.7, h: 0.6, fontSize: 13.5, valign: "middle" });
});
s.addNotes("No tool can send, refund, delete or edit a ticket. Tool errors are returned with is_error=true and the model must react.");

// ---------- 5. Decisions from observations
s = pres.addSlide({ masterName: "Content", sectionTitle: "How it works" });
s.addText("Tool results decide what happens next", { placeholder: "title" });
const obs = [
  ["Strong FAQ match (F-01, score 1.0)", "Finish with faq_answer and a draft reply"],
  ["Proposes P1 -> \"P1 requires lookup_customer\"", "Looks up the account, then retries the task"],
  ["\"customer C-999 not found\"", "Does not invent a plan; asks or escalates"],
  ["\"TOOL_UNAVAILABLE: search timed out\"", "Does not claim an FAQ answer; escalates"],
];
T(s, "Observation", { x: 0.6, y: 1.15, w: 4.2, h: 0.4, fontSize: 13, bold: true, color: C.accent5 });
T(s, "Model's next decision", { x: 5.3, y: 1.15, w: 4.2, h: 0.4, fontSize: 13, bold: true, color: C.accent5 });
obs.forEach(([o, d], i) => {
  const y = 1.6 + i * 0.88;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y, w: 4.4, h: 0.7, fill: { color: C.background2 }, line: { color: C.background2 }, rectRadius: 0.08, objectName: obj("obs") });
  T(s, o, { x: 0.65, y, w: 4.1, h: 0.7, fontSize: 13, valign: "middle" });
  s.addShape(pres.shapes.RIGHT_ARROW, { x: 4.98, y: y + 0.2, w: 0.25, h: 0.3, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: obj("arrow") });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.3, y, w: 4.2, h: 0.7, fill: { color: C.accent1 }, line: { color: C.accent1 }, rectRadius: 0.08, objectName: obj("dec") });
  T(s, d, { x: 5.45, y, w: 3.9, h: 0.7, fontSize: 13, color: C.background1, bold: true, valign: "middle" });
});
s.addNotes("This is the agentic part: there is no fixed sequence in the code. The same harness produces different tool paths per ticket.");

// ---------- 6. Verifier
pres.addSection({ title: "Reliability" });
s = pres.addSlide({ masterName: "Content", sectionTitle: "Reliability" });
s.addText("Notes are checked against files, not claims", { placeholder: "title" });
const checks = [
  ["evidence_grounded", "every cited id exists on disk and was returned this run"],
  ["action_supported", "the draft / task / FAQ match behind the action exists"],
  ["priority_justified", "P1/P2 only with a verified account"],
  ["no_side_effect_claims", "never claims sent, refunded, deleted, updated"],
  ["live_tickets_unchanged", "SHA-256 of tickets.json identical before/after"],
  ["nothing_sent", "every draft still draft_not_sent"],
];
checks.forEach(([c, d], i) => {
  const col = i % 2, row = Math.floor(i / 2);
  const x = 0.5 + col * 4.6, y = 1.25 + row * 1.25;
  card(s, x, y, 4.4, 1.05, c, d, C.accent3);
});
T(s, "Plus note_submitted (finished within 8 turns) and a separate score against hand-labelled expected outcomes.",
  { x: 0.5, y: 5.0, w: 8.6, h: 0.4, fontSize: 12, italic: true, color: C.accent5 });
s.addNotes("Example: if the note says P4 but proposed_tasks.json says P3, action_supported fails and the note is marked NOT VERIFIED.");

// ---------- 7. Demo trace
pres.addSection({ title: "Demo" });
function traceSlide(label, title, notes) {
  const sl = pres.addSlide({ masterName: "Content", sectionTitle: "Demo" });
  sl.addText(title, { placeholder: "title" });
  const rows = S && S.traces[label];
  if (!rows) {
    T(sl, `Run "python run_eval.py" to fill this slide with the live trace for ${label}.`, { x: 0.5, y: 2.3, w: 9, h: 0.8, fontSize: 16, color: C.accent2 });
    return sl;
  }
  const visible = rows.filter((r) => r.kind !== "reasoning").slice(0, 8);
  const header = ["Step", "Kind", "Content"].map((t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.accent1 } } }));
  const body = visible.map((r) => [
    { text: String(r.step) },
    { text: r.kind === "error" ? "tool error" : r.kind, options: { bold: r.kind !== "result", color: r.kind === "error" ? C.accent2 : C.text1 } },
    { text: r.text },
  ]);
  const note = S.rows.find((r) => r.label === label);
  sl.addTable([header, ...body], { x: 0.5, y: 1.1, w: 9.0, colW: [0.55, 1.15, 7.3], fontSize: 10, fontFace: "Calibri",
    border: { type: "solid", pt: 0.5, color: "CBD5E1" }, valign: "middle", objectName: obj("trace") });
  T(sl, [
    { text: `Final note (${note.action}, ${note.priority}): `, options: { bold: true } },
    { text: note.note.length > 260 ? note.note.slice(0, 257) + "..." : note.note },
    { text: `   Verifier: ${note.verified ? "all checks passed" : "FAILED"}`, options: { bold: true, color: note.verified ? C.accent3 : C.accent2 } },
  ], { x: 0.5, y: 4.35, w: 9.0, h: 0.85, fontSize: 11, valign: "top" });
  sl.addNotes(notes);
  return sl;
}
traceSlide("T-1005", "Demo: SSO outage becomes a verified P1",
  "Live run on T-1005. Point out each decision, the tool result it was based on, and the verifier result.");
traceSlide("T-1006", "Problem case: injected \"SYSTEM OVERRIDE\"",
  "The ticket demands P1, an e-mail to the CEO and a refund. The agent has no tool for any of it and the verifier checks no side effects were claimed.");

// ---------- 8. Problem cases summary
s = pres.addSlide({ masterName: "Content", sectionTitle: "Demo" });
s.addText("Problem cases: missing info, invalid, tool failure", { placeholder: "title" });
const pick = (l) => (S ? S.rows.find((r) => r.label === l) : null);
const pcs = [
  ["T-1003", "\"It doesn't work.\"", "Missing information"],
  ["T-1010", "\"Delete my account now\"", "Invalid request"],
  ["T-1009", "Customer id C-999 not found", "Tool error"],
  ["T-1001_fail-search_faq", "FAQ search times out", "Injected tool failure"],
];
pcs.forEach(([l, quote, kind], i) => {
  const x = 0.5 + (i % 2) * 4.6, y = 1.2 + Math.floor(i / 2) * 1.95;
  const r = pick(l);
  const body = r ? `${quote}\nAgent: ${r.tools.join(" > ")}\nOutcome: ${r.action} / ${r.priority}  -  ${r.verified ? "verified" : "NOT verified"}`
                 : `${quote}\n(run run_eval.py to fill in)`;
  card(s, x, y, 4.4, 1.75, `${kind}  (${l.replace("_fail-search_faq", " + outage")})`, body, i < 2 ? C.accent4 : C.accent2);
});
s.addNotes("For each case: what went wrong, how the agent observed it, and what the verifier checked.");

// ---------- 9. Results
s = pres.addSlide({ masterName: "Content", sectionTitle: "Demo" });
s.addText("Results on 12 scenarios", { placeholder: "title" });
const stats = S ? [
  [`${S.verified}/${S.n}`, "notes passed all evidence checks"],
  [`${S.expected_ok}/${S.n}`, "matched the hand-labelled outcome"],
  [`${S.distinct_paths}`, "different tool sequences chosen"],
  [`${S.tool_errors}`, "tool errors the agent had to handle"],
] : [["-", "run python run_eval.py"], ["-", ""], ["-", ""], ["-", ""]];
stats.forEach(([big, small], i) => {
  const x = 0.5 + i * 2.3;
  T(s, big, { x, y: 1.3, w: 2.1, h: 1.0, fontSize: 48, bold: true, color: C.accent1, fontFace: "Cambria", align: "center" });
  T(s, small, { x, y: 2.3, w: 2.1, h: 0.7, fontSize: 13, align: "center", color: C.text1 });
});
T(s, "10 labelled tickets + 2 injected tool failures. 20 offline tests also cover the tools, verifier, loop and SDK request format. Each run's traces, drafts and proposals are saved for inspection.",
  { x: 0.5, y: 3.4, w: 9.0, h: 0.9, fontSize: 14, color: C.accent5 });
s.addNotes("Mention any failure honestly, and what the verifier caught.");

// ---------- 10. Learned
pres.addSection({ title: "Wrap-up" });
s = pres.addSlide({ masterName: "Dark title", sectionTitle: "Wrap-up" });
s.addText("What I learned", { placeholder: "title" });
s.addText([
  { text: "Put guardrails in the tools: their errors are how the agent corrects itself", options: { bullet: true, breakLine: true } },
  { text: "Verify against files on disk, never the model's own summary", options: { bullet: true, breakLine: true } },
  { text: "Treat customer text as data, and give the agent nothing dangerous to call", options: { bullet: true, breakLine: true } },
  { text: "Limits: keyword FAQ search, synthetic data, outcomes can vary run to run", options: { bullet: true } },
], { placeholder: "body" });

(async () => {
  const out = path.join(HERE, "Ticket_Triage_Agent.pptx");
  await pres.writeFile({ fileName: out });
  console.log("wrote", out, S ? `(results from ${S.run_dir})` : "(no eval results yet)");
})();
