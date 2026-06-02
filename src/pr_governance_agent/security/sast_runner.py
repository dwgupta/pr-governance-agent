"""Optional Semgrep static analysis on PR patch content.

Writes each patch to a temp directory and runs ``semgrep --config p/python``.
Returns empty list when semgrep is not installed or ENABLE_SAST is off.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pr_governance_agent.state import Finding


def run_semgrep_on_patches(patches: list[dict[str, Any]]) -> list[Finding]:
    """Run Semgrep on unified diff text; map results to Finding objects."""
    if not patches or not shutil.which("semgrep"):
        return []

    findings: list[Finding] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for p in patches:
            name = p.get("filename", "file.txt").replace("/", "_")
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(p.get("patch") or "", encoding="utf-8")

        try:
            proc = subprocess.run(
                [
                    "semgrep",
                    "--config",
                    "p/python",
                    "--json",
                    "--quiet",
                    str(root),
                ],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError):
            return []

        # Semgrep exit 1 means findings present
        if proc.returncode not in (0, 1) or not proc.stdout.strip():
            return []

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return []

        for r in data.get("results", []):
            extra = r.get("extra", {})
            findings.append(
                Finding(
                    severity="high" if extra.get("severity") == "ERROR" else "medium",
                    category="sast",
                    message=extra.get("message", "Semgrep finding"),
                    file=r.get("path", ""),
                    citation="semgrep",
                )
            )
    return findings
