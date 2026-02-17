from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Database
    db_name: str = "homeoffice_shop"
    db_user: str = "shop"
    db_password: str = "CHANGE_ME"
    db_host: str = "db"
    db_port: int = 5432

    # CORS
    cors_allowed_origins: str = "http://localhost:3000"

    # Auth - Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""

    # JWT
    jwt_secret_key: str = "CHANGE_ME"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 2

    # HiBob HRIS (base64-encoded "user:token" string)
    hibob_api_key: str = ""
    hibob_sync_interval_hours: int = 6

    # ScraperAPI (Amazon)
    scraperapi_api_key: str = ""
    amazon_tld: str = "de"
    amazon_country_code: str = "de"

    # SMTP
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_address: str = "noreply@your-company.com"
    smtp_from_name: str = "Home Office Shop"

    # Slack
    slack_webhook_url: str = ""

    # App
    secret_key: str = "CHANGE_ME"
    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    allowed_email_domains: str = "your-company.com"
    initial_admin_emails: str = "admin@your-company.com"

    # Uvicorn
    uvicorn_workers: int = 2

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def allowed_domains_list(self) -> list[str]:
        return [d.strip() for d in self.allowed_email_domains.split(",") if d.strip()]

    @property
    def initial_admin_emails_list(self) -> list[str]:
        return [e.strip() for e in self.initial_admin_emails.split(",") if e.strip()]

    model_config = {"env_file": ".env", "extra": "ignore"}

    def validate_secrets(self) -> None:
        """Raise if production-critical secrets are still defaults."""
        defaults = {"CHANGE_ME"}
        if self.jwt_secret_key in defaults:
            raise ValueError("jwt_secret_key must be changed from default")
        if self.secret_key in defaults:
            raise ValueError("secret_key must be changed from default")
        if self.db_password in defaults:
            raise ValueError("db_password must be changed from default")

    @property
    def upload_dir(self) -> Path:
        docker_path = Path("/app/uploads")
        if docker_path.exists():
            return docker_path
        local_path = Path("uploads")
        local_path.mkdir(exist_ok=True)
        return local_path


settings = Settings()
