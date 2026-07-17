"""App config from environment variables."""
from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Config(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql://app:appsecret@localhost:5432/appdb"

    # Server (for uvicorn or other runners)
    host: str = "0.0.0.0"
    port: int = 8000

    # Session (signed cookies)
    secret_key: str = "dev-secret-change-in-production"

    # Attribute Pass-Through Link (APL)
    redirect_allowlist: list[str] = []
    apl_rate_limit: str = "100 per minute"
    apl_user_cache_ttl: int = 300

    # Certifications (LightSpeed VT REST API)
    certifications_cache_ttl: int = 300
    certifications_user_cache_ttl: int = 300
    lightspeed_api_timeout: int = 30

    # Monday.com webhook ingestion (ops dashboard)
    # Monday automations don't sign outgoing webhook payloads, so the shared
    # secret is embedded in the webhook URL itself, e.g.
    # https://.../api/monday/webhook?token=<monday_webhook_token>
    monday_webhook_token: str = ""

    # Subdomain in https://<subdomain>.monday.com -- used to build direct
    # links from ops-dashboard item drill-downs back to Monday.com.
    monday_account_subdomain: str = "lightspeed-vt-company"

    @field_validator("redirect_allowlist", mode="before")
    @classmethod
    def parse_redirect_allowlist(cls, v: str) -> list[str]:
        if isinstance(v, list):
            return [s.strip().lower() for s in v if s and str(s).strip()]
        return [s.strip().lower() for s in str(v).split(",") if s.strip()]


# Singleton instance
settings = Config()

# Backward-compatible names for existing imports
DATABASE_URL = settings.database_url
HOST = settings.host
PORT = settings.port
SECRET_KEY = settings.secret_key
REDIRECT_ALLOWLIST = settings.redirect_allowlist
APL_BLOCKED_ATTRIBUTES = [
    "password",
    "apiKey",
    "apiSecret",
    "secret",
    "token",
]
APL_RATE_LIMIT = settings.apl_rate_limit
APL_USER_CACHE_TTL = settings.apl_user_cache_ttl
CERTIFICATIONS_CACHE_TTL = settings.certifications_cache_ttl
CERTIFICATIONS_USER_CACHE_TTL = settings.certifications_user_cache_ttl
LIGHTSPEED_API_TIMEOUT = settings.lightspeed_api_timeout
MONDAY_WEBHOOK_TOKEN = settings.monday_webhook_token
MONDAY_ACCOUNT_SUBDOMAIN = settings.monday_account_subdomain
