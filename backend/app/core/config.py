from typing import Any, List, Optional, Union
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "VixenOne"
    ENV: str = "development"
    API_PORT: int = 8000
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173"]

    # Database
    DATABASE_URL: str = "postgresql+psycopg://vixenone:vixenone@postgres:5432/vixenone"

    # Firebase Auth
    FIREBASE_PROJECT_ID: str = "demo-vixenone"
    FIREBASE_AUTH_EMULATOR_HOST: Optional[str] = None

    # AI / Gemini
    GEMINI_API_KEY: Optional[SecretStr] = None
    GEMINI_MODEL: str = "gemini-3.6-flash"

    # File Storage
    STORAGE_BACKEND: str = "local"
    UPLOAD_DIR: str = "/app/uploads"

    @property
    def is_production(self) -> bool:
        return self.ENV.strip().lower() in ("production", "prod")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @field_validator("FIREBASE_AUTH_EMULATOR_HOST", mode="before")
    @classmethod
    def assemble_emulator_host(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    @field_validator("GEMINI_API_KEY", mode="before")
    @classmethod
    def assemble_gemini_api_key(cls, v: Any) -> Optional[SecretStr]:
        if v is None:
            return None
        if isinstance(v, SecretStr):
            return v
        s = str(v).strip()
        return SecretStr(s) if s else None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
