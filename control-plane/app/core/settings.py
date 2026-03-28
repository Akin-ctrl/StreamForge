"""Application settings for Control Plane."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "StreamForge Control Plane"
    environment: str = "dev"
    database_url: str = "postgresql+psycopg://streamforge:streamforge@localhost:5432/streamforge"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    admin_username: str = "admin"
    admin_password: str = "admin123"
    allow_dev_admin_bootstrap: bool = False

    model_config = SettingsConfigDict(env_prefix="SF_", env_file=".env", extra="ignore")

    @property
    def is_dev_environment(self) -> bool:
        return self.environment.lower() in {"dev", "development", "local", "test"}


settings = Settings()
