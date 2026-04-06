"""Agent runtime configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    app_name: str = "CaseGraph Agent Runtime"
    app_version: str = "0.1.0"
    debug: bool = False

    model_config = SettingsConfigDict(env_prefix="CASEGRAPH_RUNTIME_")


settings = RuntimeSettings()
