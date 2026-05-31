from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_api_base: str | None = None

    github_token: str = ""
    sandbox_repo: str = ""
    allow_write_actions: bool = False
    use_pr_fixture: bool = False
    github_mcp_command: str = ""

    chroma_persist_dir: Path = ROOT_DIR / "data" / "chroma"
    checkpoint_dir: Path = ROOT_DIR / "data" / "checkpoints"

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

    def writes_allowed(self, repo: str, mode: str) -> bool:
        if mode != "auto":
            return False
        if not self.allow_write_actions:
            return False
        if not self.sandbox_repo:
            return False
        return repo.lower() == self.sandbox_repo.lower()


def get_settings() -> Settings:
    return Settings()
