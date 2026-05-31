#!/usr/bin/env python3
"""Copy capstone-poc-planner rules into .cursor/rules/ for Cursor indexing.

Edit only under .cursor/skills/capstone-poc-planner/ (phases/*.mdc and capstone-poc-planner.mdc),
then run from the project root:

    python scripts/sync_cursor_rules.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / ".cursor" / "skills" / "capstone-poc-planner"
PHASES_SRC = SRC / "phases"
ORCHESTRATOR_SRC = SRC / "capstone-poc-planner.mdc"
RULES_DEST = ROOT / ".cursor" / "rules"


def sync() -> list[str]:
    if not PHASES_SRC.is_dir():
        raise FileNotFoundError(f"Missing phases directory: {PHASES_SRC}")

    RULES_DEST.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for src in sorted(PHASES_SRC.glob("*.mdc")):
        dest = RULES_DEST / src.name
        shutil.copy2(src, dest)
        copied.append(dest.name)

    if not ORCHESTRATOR_SRC.is_file():
        raise FileNotFoundError(f"Missing orchestrator: {ORCHESTRATOR_SRC}")

    shutil.copy2(ORCHESTRATOR_SRC, RULES_DEST / "capstone-poc-planner.mdc")
    copied.append("capstone-poc-planner.mdc")

    return copied


def main() -> int:
    try:
        copied = sync()
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"Synced {len(copied)} file(s) to {RULES_DEST}:")
    for name in copied:
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
