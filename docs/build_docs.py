"""Rebuilds both deliverables from the newest eval run:  python docs/build_docs.py"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for cmd in ([sys.executable, "results.py"], [sys.executable, "make_diagram.py"], [sys.executable, "harness_demo.py"], [sys.executable, "build_pdf.py"],
            ["node", "build_deck.js"]):
    subprocess.run(cmd, cwd=HERE, check=True)

# PowerPoint and cloud services dislike directory entries inside the .pptx zip; drop them.
import shutil
import zipfile

deck = HERE / "Ticket_Triage_Agent.pptx"
tmp = deck.with_suffix(".tmp")
with zipfile.ZipFile(deck) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        if not item.filename.endswith("/"):
            zout.writestr(item, zin.read(item.filename))
shutil.move(tmp, deck)
