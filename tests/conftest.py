from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
NANOBOT = ROOT.parents[0] / "nanobot"

for path in (SRC, NANOBOT):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)
