"""Application configuration loaded from environment and `.env`.

All runtime flags (GitHub, OpenAI, RAG, LangSmith) are centralized here via
pydantic-settings. Call ``get_settings()`` once at process start so LangSmith
env vars are applied before LangChain imports.
"""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root (capstone/) — two levels up from this package file.
ROOT_DIR = Path(__file__).resolve().parents[2]


def apply_langsmith_env(settings: "Settings") -> None:
    """Export LangSmith settings to os.environ so LangChain/LangGraph tracing works."""
    if settings.langsmith_api_key.strip():
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key.strip()
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key.strip()
    if settings.langsmith_project.strip():
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project.strip()
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project.strip()
    if settings.langsmith_endpoint.strip():
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint.strip()
    if settings.langsmith_tracing:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
    else:
        os.environ.pop("LANGSMITH_TRACING", None)
        os.environ.pop("LANGCHAIN_TRACING_V2", None)


class Settings(BaseSettings):
    """Typed settings with defaults; values override from environment / `.env`."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM (OpenAI-compatible) ---
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_api_base: str | None = None

    # LangSmith — https://smith.langchain.com (tracing + token usage)
    langsmith_tracing: bool = Field(
        default=False,
        validation_alias=AliasChoices("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"),
    )
    langsmith_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LANGSMITH_API_KEY", "LANGCHAIN_API_KEY"),
    )
    langsmith_project: str = Field(
        default="pr-governance-agent",
        validation_alias=AliasChoices("LANGSMITH_PROJECT", "LANGCHAIN_PROJECT"),
    )
    langsmith_endpoint: str = Field(
        default="",
        validation_alias=AliasChoices("LANGSMITH_ENDPOINT", "LANGCHAIN_ENDPOINT"),
    )

    # --- GitHub integration ---
    github_token: str = ""
    sandbox_repo: str = ""  # owner/repo allowlist for auto approve/merge
    allow_write_actions: bool = False
    use_pr_fixture: bool = False  # offline JSON fixtures instead of live API
    github_mcp_command: str = ""  # optional shell command for MCP bridge

    # --- Persistence paths ---
    chroma_persist_dir: Path = ROOT_DIR / "data" / "chroma"
    checkpoint_dir: Path = ROOT_DIR / "data" / "checkpoints"

    # --- RAG retrieval ---
    rag_retrieve_n: int = 20  # wide recall from vector search
    rag_top_k: int = 5  # final chunks after cross-encoder rerank
    rag_rerank_enabled: bool = True
    rag_rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # --- PR diff limits (avoid OOM on huge PRs) ---
    max_diff_files: int = 30
    max_diff_lines: int = 500

    # --- Feature toggles ---
    enable_sast: bool = False
    post_pr_comments: bool = False
    heuristic_only: bool = False  # skip LLM; use regex rules only
    use_sqlite_checkpoint: bool = True

    # --- Email notifications (optional; always logs to data/notification.log) ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notify_from: str = ""
    notify_to: str = ""

    @property
    def llm_enabled(self) -> bool:
        """True when OpenAI key is set and heuristic-only mode is off."""
        return bool(self.openai_api_key.strip()) and not self.heuristic_only

    @property
    def langsmith_enabled(self) -> bool:
        return self.langsmith_tracing and bool(self.langsmith_api_key.strip())

    def writes_allowed(self, repo: str, mode: str) -> bool:
        """Auto approve/merge only in auto mode with explicit flags and sandbox match."""
        if mode != "auto":
            return False
        if not self.allow_write_actions:
            return False
        if not self.sandbox_repo:
            return False
        return repo.lower() == self.sandbox_repo.lower()


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton; clears cache in tests via ``get_settings.cache_clear()``."""
    settings = Settings()
    apply_langsmith_env(settings)
    return settings
