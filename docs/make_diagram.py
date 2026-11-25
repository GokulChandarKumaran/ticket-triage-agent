"""Draws docs/workflow.png - the agent workflow diagram used in the PDF and the slides."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

INK, TEAL, SAND, RED, GREEN, GREY = "#1F2A37", "#0F766E", "#F1F5F4", "#B42318", "#15803D", "#64748B"


def box(ax, x, y, w, h, text, fc, ec, color=INK, size=10.5, weight="normal"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", fc=fc, ec=ec, lw=1.6))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color=color, weight=weight, wrap=True)


def arrow(ax, a, b, color=INK, style="-|>", rad=0.0, ls="-"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=14, color=color, lw=1.5,
                                 connectionstyle=f"arc3,rad={rad}", linestyle=ls))


def main(out: Path):
    fig, ax = plt.subplots(figsize=(12, 7.2), dpi=200)
    ax.set_xlim(0, 12); ax.set_ylim(0, 7.2); ax.axis("off")

    box(ax, 0.1, 4.55, 2.3, 1.2, "Support ticket\n(customer text\ntreated as data)", "white", GREY, size=9.5)
    box(ax, 3.0, 4.4, 2.6, 1.5, "Claude decides\nnext action\n(adaptive thinking)", TEAL, TEAL, "white", 11.5, "bold")
    arrow(ax, (2.45, 5.15), (3.0, 5.15))

    tools = [("search_faq", "FAQ entries + scores"),
             ("lookup_customer", "plan, seats, SLA"),
             ("request_missing_info", "unsent draft D-xxxx"),
             ("propose_priority_and_task", "proposal TASK-xxxx")]
    for i, (name, res) in enumerate(tools):
        y = 5.2 - i * 1.05
        box(ax, 6.6, y, 2.6, 0.8, f"{name}\n→ {res}", SAND, TEAL, size=9.5)
        arrow(ax, (5.6, 5.15), (6.6, y + 0.4), TEAL)

    # observation loop back to the model
    arrow(ax, (6.6, 2.3), (4.0, 4.4), RED, rad=-0.3)
    ax.text(3.3, 2.9, "tool result or error\n(is_error) fed back;\nmodel picks again", fontsize=9.5, color=RED, ha="center")

    box(ax, 9.7, 4.4, 2.1, 1.5, "submit_next_\naction_note\n(final step)", "white", TEAL, size=10, weight="bold")
    arrow(ax, (4.3, 5.9), (10.75, 5.9), TEAL, rad=-0.15)
    ax.text(7.5, 6.6, "final step, when the model has enough evidence", fontsize=9, color=TEAL, ha="center")

    box(ax, 9.7, 2.2, 2.1, 1.6, "Verifier\nre-reads files on disk\n7 evidence checks", "white", GREEN, size=9.5)
    arrow(ax, (10.75, 4.4), (10.75, 3.8), GREEN)
    box(ax, 9.7, 0.3, 2.1, 1.3, "PM note\nVERIFIED /\nNOT VERIFIED", GREEN, GREEN, "white", 10, "bold")
    arrow(ax, (10.75, 2.2), (10.75, 1.6), GREEN)

    ax.text(0.2, 1.75, "Guardrails in the tools", fontsize=10, weight="bold", color=INK)
    for i, t in enumerate(["• P1/P2 rejected until lookup_customer succeeds",
                           "• evidence ids must come from earlier results",
                           "• note rejected if its draft/task does not exist",
                           "• no tool can send, refund, delete or edit tickets",
                           "• step limit of 8 model turns"]):
        ax.text(0.2 + (i // 3) * 4.4, 1.35 - (i % 3) * 0.36, t, fontsize=9, color=INK)

    fig.savefig(out, bbox_inches="tight", facecolor="white")
    print("wrote", out)


if __name__ == "__main__":
    main(Path(__file__).with_name("workflow.png"))
