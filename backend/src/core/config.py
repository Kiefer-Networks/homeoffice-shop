from pathlib import Path
from urllib.parse import urlparse

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Database
    db_name: str = "homeoffice_shop"
    db_user: str = "shop"
    db_password: str = "CHANGE_ME"
    db_host: str = "db"
    db_port: int = 5432
    db_ssl: bool = False

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

    # App
    debug: bool = False
    secret_key: str = "CHANGE_ME"
    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    allowed_email_domains: str = "your-company.com"
    initial_admin_emails: str = "admin@your-company.com"

    # Backup
    backup_dir: str = "/app/backups"
    backup_retention_count: int = 10

    @property
    def database_url(self) -> str:
        base = (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )
        return f"{base}?ssl=require" if self.db_ssl else base

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
        if len(self.jwt_secret_key) < 32:
            raise ValueError(
                "jwt_secret_key must be at least 32 characters (256 bits) per RFC 7518 Section 3.2"
            )
        if self.secret_key in defaults:
            raise ValueError("secret_key must be changed from default")
        if len(self.secret_key) < 32:
            raise ValueError("secret_key must be at least 32 characters")
        for url_name in ("backend_url", "frontend_url"):
            url_val = getattr(self, url_name)
            parsed = urlparse(url_val)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError(f"{url_name} must be a valid http(s) URL")
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
