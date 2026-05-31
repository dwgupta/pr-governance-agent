import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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

    github_token: str = ""
    sandbox_repo: str = ""
    allow_write_actions: bool = False
    use_pr_fixture: bool = False
    github_mcp_command: str = ""

    chroma_persist_dir: Path = ROOT_DIR / "data" / "chroma"
    checkpoint_dir: Path = ROOT_DIR / "data" / "checkpoints"

    rag_retrieve_n: int = 20
    rag_top_k: int = 5
    rag_rerank_enabled: bool = True
    rag_rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    max_diff_files: int = 30
    max_diff_lines: int = 500

    enable_sast: bool = False
    post_pr_comments: bool = False
    heuristic_only: bool = False
    use_sqlite_checkpoint: bool = True  # USE_SQLITE_CHECKPOINT

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notify_from: str = ""
    notify_to: str = ""

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key.strip()) and not self.heuristic_only

    @property
    def langsmith_enabled(self) -> bool:
        return self.langsmith_tracing and bool(self.langsmith_api_key.strip())

    def writes_allowed(self, repo: str, mode: str) -> bool:
        if mode != "auto":
            return False
        if not self.allow_write_actions:
            return False
        if not self.sandbox_repo:
            return False
        return repo.lower() == self.sandbox_repo.lower()


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    apply_langsmith_env(settings)
    return settings
