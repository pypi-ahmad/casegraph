"""Application configuration via environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[1] / ".casegraph" / "casegraph.db"
_DEFAULT_ARTIFACTS_PATH = Path(__file__).resolve().parents[1] / ".casegraph" / "artifacts"


class Settings(BaseSettings):
    app_name: str = "CaseGraph"
    app_version: str = "0.1.0"
    debug: bool = False
    web_origin: str = "http://localhost:3000"
    provider_request_timeout_seconds: float = 15.0
    agent_runtime_url: str = "http://localhost:8100"
    agent_runtime_timeout_seconds: float = 10.0
    database_url: str = f"sqlite:///{_DEFAULT_DATABASE_PATH.as_posix()}"
    database_echo: bool = False
    artifacts_dir: str = _DEFAULT_ARTIFACTS_PATH.as_posix()

    model_config = SettingsConfigDict(env_prefix="CASEGRAPH_")


settings = Settings()
