"""Application settings for Control Plane."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "StreamForge Control Plane"
    environment: str = "dev"
    database_url: str = "postgresql+psycopg://streamforge:streamforge@localhost:5432/streamforge"
    jwt_secret: str = ""
    config_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    auth_cookie_name: str = "sf_user_session"
    auth_cookie_samesite: str = "lax"
    auth_cookie_secure: bool | None = None
    auth_cookie_domain: str = ""
    auth_cookie_max_age_seconds: int = 60 * 60 * 12
    admin_username: str = ""
    admin_password: str = ""
    allow_dev_admin_bootstrap: bool = False

    model_config = SettingsConfigDict(env_prefix="SF_", env_file=".env", extra="ignore")

    @property
    def is_dev_environment(self) -> bool:
        return self.environment.lower() in {"dev", "development", "local", "test"}

    @property
    def resolved_auth_cookie_secure(self) -> bool:
        if self.auth_cookie_secure is not None:
            return self.auth_cookie_secure
        return not self.is_dev_environment

    def validate_startup_security(self) -> None:
        from app.core.security import validate_password_strength, validate_shared_secret_strength

        try:
            validate_shared_secret_strength(self.jwt_secret, field_name="SF_JWT_SECRET")
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc

        same_site = self.auth_cookie_samesite.strip().lower()
        if same_site not in {"lax", "strict", "none"}:
            raise RuntimeError("SF_AUTH_COOKIE_SAMESITE must be one of: lax, strict, none")
        if same_site == "none" and not self.resolved_auth_cookie_secure:
            raise RuntimeError("SF_AUTH_COOKIE_SAMESITE='none' requires a secure auth cookie")
        if self.auth_cookie_max_age_seconds <= 0:
            raise RuntimeError("SF_AUTH_COOKIE_MAX_AGE_SECONDS must be greater than zero")

        if not self.allow_dev_admin_bootstrap:
            return

        if not self.is_dev_environment:
            raise RuntimeError(
                "SF_ALLOW_DEV_ADMIN_BOOTSTRAP can only be enabled in dev/local/test environments",
            )

        username = self.admin_username.strip()
        password = self.admin_password
        if not username:
            raise RuntimeError("SF_ADMIN_USERNAME must be set when SF_ALLOW_DEV_ADMIN_BOOTSTRAP=true")
        if not password.strip():
            raise RuntimeError("SF_ADMIN_PASSWORD must be set when SF_ALLOW_DEV_ADMIN_BOOTSTRAP=true")

        try:
            validate_password_strength(password, username=username)
        except ValueError as exc:
            raise RuntimeError(
                f"SF_ADMIN_PASSWORD is invalid for dev bootstrap: {exc}",
            ) from exc


settings = Settings()
