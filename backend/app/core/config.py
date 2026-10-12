from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "VixenOne"
    API_PORT: int = 8000
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173"]

    # Database
    DATABASE_URL: str = "postgresql+psycopg://vixenone:vixenone@postgres:5432/vixenone"

    # Firebase Auth
    FIREBASE_PROJECT_ID: str = "demo-vixenone"
    FIREBASE_AUTH_EMULATOR_HOST: str = "firebase-auth-emulator:9099"

    # File Storage
    STORAGE_BACKEND: str = "local"
    UPLOAD_DIR: str = "/app/uploads"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
