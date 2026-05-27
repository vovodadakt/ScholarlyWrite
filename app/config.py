import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "mysql+aiomysql://root@localhost:3306/writing_platform?charset=utf8"
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 days

    encryption_key: str = ""  # base64-encoded 32-byte key for Fernet

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    default_ai_provider: str = "claude"
    default_ai_model: str = "claude-sonnet-4-20250514"

    debug: bool = True


settings = Settings()

if not settings.jwt_secret or settings.jwt_secret == "change-me":
    settings.jwt_secret = secrets.token_urlsafe(32)
    if not settings.debug:
        raise RuntimeError(
            "JWT_SECRET is not set in .env. "
            "A random secret has been generated for this session; "
            "set JWT_SECRET in .env for persistence."
        )

if not settings.encryption_key:
    from cryptography.fernet import Fernet

    settings.encryption_key = Fernet.generate_key().decode()
    if not settings.debug:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set in .env. "
            "Set it to a base64-encoded 32-byte key (generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')."
        )
