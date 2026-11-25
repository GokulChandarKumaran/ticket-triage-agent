"""Rebuilds both deliverables from the newest eval run:  python docs/build_docs.py"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for cmd in ([sys.executable, "results.py"], [sys.executable, "make_diagram.py"], [sys.executable, "build_pdf.py"],
            ["node", "build_deck.js"]):
    subprocess.run(cmd, cwd=HERE, check=True)
