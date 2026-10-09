from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_DIR.parent


class Settings(BaseSettings):
    jwt_secret_key: str = ""
    jwt_expire_minutes: int = 60
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openrouter/free"
    openrouter_vision_model: str = ""
    openrouter_timeout_seconds: float = 30.0
    tutor_code_sandbox_url: str = ""
    tutor_code_sandbox_api_key: str = ""
    tutor_code_sandbox_python_version: str = "3.10.0"
    code_sandbox_url: str = ""
    code_sandbox_timeout_seconds: float = 10.0
    code_sandbox_api_key: str = ""
    tutor_upload_dir: str = str(_BACKEND_DIR / "data" / "tutor_uploads")
    database_url: str = "sqlite:///./adaptive_learning.db"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=(_BACKEND_DIR / ".env", _REPO_ROOT / ".env"),
        extra="ignore",
    )


settings = Settings()
