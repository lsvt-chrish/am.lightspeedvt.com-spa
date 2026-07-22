"""App config from environment variables."""
from dotenv import load_dotenv
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

VETCOMM_STAGE_URL = "https://stage-portal.vetcomm.link"
VETCOMM_PROD_URL = "https://portal.vetcomm.org"


class Config(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Which environment this process is running in: "development" | "production".
    # Drives environment-dependent defaults below (e.g. vetcomm_api_base_url).
    app_env: str = "development"

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

    # Shared HTTP Basic credentials gating the board-admin endpoints
    # (/monday/boards/*). Interim solution until per-user accounts are
    # needed; empty password means the admin routes refuse all requests
    # rather than running open.
    ops_admin_username: str = "admin"
    ops_admin_password: str = ""

    # VetComm statement generation API (client-supplied key/secret).
    # base_url is the host only (no /api/v1 suffix) -- see docs/lms-statement-api.md
    # Left unset by default so it derives from app_env (stage in dev, prod in prod);
    # set it explicitly in .env to override (e.g. to hit prod from a local machine).
    vetcomm_api_base_url: str | None = None
    vetcomm_api_key: str = ""
    vetcomm_shared_secret: str = ""
    vetcomm_api_timeout: int = 30

    @field_validator("redirect_allowlist", mode="before")
    @classmethod
    def parse_redirect_allowlist(cls, v: str) -> list[str]:
        if isinstance(v, list):
            return [s.strip().lower() for s in v if s and str(s).strip()]
        return [s.strip().lower() for s in str(v).split(",") if s.strip()]

    @model_validator(mode="after")
    def default_vetcomm_base_url(self):
        # Docker Compose's ${VAR:-} substitution sets an empty string rather than
        # leaving the var unset, so treat "" the same as None (not explicitly set).
        if not self.vetcomm_api_base_url:
            self.vetcomm_api_base_url = (
                VETCOMM_PROD_URL if self.app_env == "production" else VETCOMM_STAGE_URL
            )
        return self

    @model_validator(mode="after")
    def require_real_secret_key_in_production(self):
        if self.app_env == "production" and self.secret_key in ("", "dev-secret-change-in-production"):
            raise ValueError("secret_key must be set to a real value when app_env=production")
        return self


# Singleton instance
settings = Config()

# Backward-compatible names for existing imports
APP_ENV = settings.app_env
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
OPS_ADMIN_USERNAME = settings.ops_admin_username
OPS_ADMIN_PASSWORD = settings.ops_admin_password
VETCOMM_API_BASE_URL = settings.vetcomm_api_base_url
VETCOMM_API_KEY = settings.vetcomm_api_key
VETCOMM_SHARED_SECRET = settings.vetcomm_shared_secret
VETCOMM_API_TIMEOUT = settings.vetcomm_api_timeout
