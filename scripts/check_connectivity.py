#!/usr/bin/env python3
"""Connectivity checks for external integrations used by PR Governance Agent."""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Callable

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pr_governance_agent.config import get_settings
from pr_governance_agent.rag.chroma_store import ChromaStore


def _ok(name: str, details: str) -> tuple[str, str, str]:
    return ("PASS", name, details)


def _warn(name: str, details: str) -> tuple[str, str, str]:
    return ("WARN", name, details)


def _fail(name: str, details: str) -> tuple[str, str, str]:
    return ("FAIL", name, details)


def check_github() -> tuple[str, str, str]:
    settings = get_settings()
    if not settings.github_token.strip():
        return _warn("github", "GITHUB_TOKEN is not set")
    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get("https://api.github.com/user", headers=headers)
        if resp.status_code == 200:
            login = (resp.json() or {}).get("login", "unknown")
            return _ok("github", f"Authenticated as {login}")
        return _fail("github", f"HTTP {resp.status_code}: {resp.text[:120]}")
    except Exception as exc:
        return _fail("github", str(exc))


def check_openai() -> tuple[str, str, str]:
    settings = get_settings()
    if not settings.openai_api_key.strip():
        return _warn("openai", "OPENAI_API_KEY is not set")

    url = (settings.openai_api_base or "https://api.openai.com/v1").rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(url, headers=headers)
        if resp.status_code == 200:
            return _ok("openai", f"Reached models API at {url}")
        return _fail("openai", f"HTTP {resp.status_code}: {resp.text[:120]}")
    except Exception as exc:
        return _fail("openai", str(exc))


def check_langchain() -> tuple[str, str, str]:
    settings = get_settings()
    if not settings.openai_api_key.strip():
        return _warn("langchain", "OPENAI_API_KEY is not set")
    try:
        from langchain_openai import ChatOpenAI

        kwargs: dict = {
            "model": settings.openai_model,
            "api_key": settings.openai_api_key,
            "temperature": 0,
            # Some models (e.g. gpt-5.x) cannot complete within max_tokens=1.
            "max_tokens": 32,
        }
        if settings.openai_api_base:
            kwargs["base_url"] = settings.openai_api_base

        llm = ChatOpenAI(**kwargs)
        resp = llm.invoke("Reply with exactly the word OK and nothing else.")
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        if not text.strip():
            return _fail("langchain", "ChatOpenAI returned an empty response")
        return _ok("langchain", f"ChatOpenAI invocation succeeded ({settings.openai_model})")
    except Exception as exc:
        return _fail("langchain", str(exc))


def check_langsmith() -> tuple[str, str, str]:
    settings = get_settings()
    if not settings.langsmith_api_key.strip():
        return _warn("langsmith", "LANGSMITH_API_KEY is not set")
    endpoint = (settings.langsmith_endpoint or "https://api.smith.langchain.com").rstrip("/")
    project = settings.langsmith_project.strip() or "default"
    try:
        import uuid

        from langsmith import Client

        client = Client(api_key=settings.langsmith_api_key, api_url=endpoint)
        _ = next(client.list_projects(limit=1), None)

        # Read access alone is not enough — verify run ingest (write) works.
        probe_id = uuid.uuid4()
        client.create_run(
            id=probe_id,
            name="pr_governance_connectivity_probe",
            run_type="chain",
            inputs={"probe": "ok"},
            project_name=project,
        )
        return _ok(
            "langsmith",
            f"LangSmith read+write OK at {endpoint} (project={project})",
        )
    except Exception as exc:
        message = str(exc)
        if "403" in message or "Forbidden" in message:
            return _fail(
                "langsmith",
                "API key cannot ingest runs (403). Create a LangSmith API key with "
                "write access at https://smith.langchain.com/settings and ensure "
                f"LANGSMITH_PROJECT={project!r} exists in that workspace.",
            )
        return _fail("langsmith", message)


def check_chroma() -> tuple[str, str, str]:
    try:
        store = ChromaStore()
        req = store.get_or_create_collection("requirements").count()
        sec = store.get_or_create_collection("security_policies").count()
        detail = f"Chroma reachable (requirements={req}, security_policies={sec})"
        if req == 0 and sec == 0:
            return _warn("chroma", detail + "; run scripts/ingest_docs.py")
        return _ok("chroma", detail)
    except Exception as exc:
        return _fail("chroma", str(exc))


def check_semgrep() -> tuple[str, str, str]:
    path = shutil.which("semgrep")
    if not path:
        return _warn("semgrep", "Semgrep not found on PATH")
    return _ok("semgrep", f"Found at {path}")


def check_mcp() -> tuple[str, str, str]:
    settings = get_settings()
    command = settings.github_mcp_command.strip()
    if not command:
        return _warn("mcp", "GITHUB_MCP_COMMAND is not set")
    payload = json.dumps({"repo": "dwgupta/migration-sandbox-capstone", "pr_number": 1})
    try:
        proc = subprocess.run(
            command,
            shell=True,
            input=payload,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.returncode != 0:
            return _fail("mcp", proc.stderr.strip() or "command failed")
        data = json.loads(proc.stdout or "{}")
        required = {"repo", "pr_number", "patches"}
        if not required.issubset(set(data.keys())):
            return _fail("mcp", f"output missing keys: {sorted(required - set(data.keys()))}")
        return _ok("mcp", "Bridge command returned expected PR payload")
    except Exception as exc:
        return _fail("mcp", str(exc))


def check_smtp() -> tuple[str, str, str]:
    settings = get_settings()
    if not settings.smtp_host.strip():
        return _warn("smtp", "SMTP_HOST is not set")
    target = (settings.smtp_host, int(settings.smtp_port))
    try:
        with socket.create_connection(target, timeout=10):
            return _ok("smtp", f"TCP connection established to {target[0]}:{target[1]}")
    except Exception as exc:
        return _fail("smtp", str(exc))


CHECKS: dict[str, Callable[[], tuple[str, str, str]]] = {
    "github": check_github,
    "openai": check_openai,
    "langchain": check_langchain,
    "langsmith": check_langsmith,
    "chroma": check_chroma,
    "semgrep": check_semgrep,
    "mcp": check_mcp,
    "smtp": check_smtp,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Connectivity checks for PR governance integrations")
    parser.add_argument(
        "--only",
        nargs="+",
        choices=sorted(CHECKS.keys()),
        help="Run only specific checks",
    )
    args = parser.parse_args()

    selected = args.only or list(CHECKS.keys())
    rows: list[tuple[str, str, str]] = []
    for key in selected:
        rows.append(CHECKS[key]())

    for status, name, details in rows:
        print(f"[{status}] {name}: {details}")

    # Non-zero if any hard failure occurred.
    return 1 if any(status == "FAIL" for status, _, _ in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
