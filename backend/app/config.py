from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE), env_file_encoding="utf-8", extra="ignore"
    )

    # fox 网关 / Anthropic 原生协议
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_model_light: str = "claude-haiku-4-5-20251001"

    # Jimaku
    jimaku_api_token: str = ""

    # 数据库
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'anime-nihongo.db'}"

    # VOICEVOX 本地 TTS 引擎
    voicevox_url: str = "http://localhost:50021"

    def validate_ai(self) -> bool:
        return bool(self.anthropic_api_key and self.anthropic_api_key != "your_key")


settings = Settings()
