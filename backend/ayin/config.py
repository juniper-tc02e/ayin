"""Application settings.

Reads from environment / .env (never commit a real .env). Every secret has a
clearly-insecure dev default so the stack boots locally; production deploys
must override them (enforced by `Settings.assert_production_safe`).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-only-insecure-secret"  # noqa: S105 — sentinel, not a real secret


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── App ──────────────────────────────────────────────────
    app_env: str = "development"
    app_secret: str = _DEV_SECRET
    api_base_url: str = "http://localhost:8000"
    web_base_url: str = "http://localhost:3000"

    # ── Datastores ───────────────────────────────────────────
    database_url: str = "postgresql://ayin:change-me-local-only@localhost:5432/ayin"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "ayin-artifacts"
    s3_access_key: str = "change-me-local-only"
    s3_secret_key: str = "change-me-local-only"

    # ── PII vault (M1-5; master key is KMS-backed in prod) ───
    vault_master_key: str = ""
    pii_retention_days: int = 30

    # ── Email (dev: MailDev sink from docker-compose) ────────
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    email_from: str = "Ayin <no-reply@ayin.local>"
    email_console_fallback: bool = True  # no SMTP reachable → print to log (dev only)

    # ── Auth (FR-AUTH-1) ─────────────────────────────────────
    access_token_ttl_minutes: int = 60 * 24  # session cookie JWT
    verification_token_ttl_minutes: int = 60 * 24
    step_up_ttl_minutes: int = 5  # elevated window before credential-level data
    auth_cookie_name: str = "ayin_session"
    cookie_secure: bool = False  # True in production (https)

    # ── ToS / AUP gate (FR-AUTH-2) ───────────────────────────
    tos_current_version: str = "2026-06-10"

    # ── Private beta (M5-1): require an invite code at signup ─
    beta_invite_required: bool = False

    # ── Demo deployment (hackathon judge flow) ───────────────
    # When true: the synthetic FakeConnector is enabled even in production
    # (it carries counsel sign-off — nothing external), and scripts/seed_demo
    # seeds the public demo account on boot. NEVER true in a real production
    # deployment — it puts a known-credential account + a fake source on the box.
    demo_mode: bool = False

    # ── Safety / limits (FR-SCAN-3; env values are fallback/seed —
    #    live values come from the rate_limit_policies table, M1-6) ──
    rate_limit_scans_per_day: int = 5
    rate_limit_burst: int = 2

    # ── Scan orchestration (M1-1) ────────────────────────────
    # "inline" runs the pipeline synchronously (dev/test);
    # "celery" enqueues to workers (compose/production).
    scan_execution: str = "inline"
    job_stale_after_seconds: int = 300

    # ── Connectors (M1-2..4; keys empty = connector disabled) ─
    breach_api_key: str = ""
    breach_api_base_url: str = "https://haveibeenpwned.com/api/v3"
    search_api_key: str = ""
    search_api_base_url: str = "https://api.search.brave.com/res/v1"
    broker_registry_path: str = "ayin/connectors/broker/registry.yaml"

    # ── LLM orchestrator (Qwen Cloud / OpenAI-compatible) ────
    # Disabled by default → the pipeline uses deterministic templates. Enable
    # for the agentic path. Dev points QWEN_BASE_URL at a local Ollama (no key
    # needed); prod points it at Qwen Cloud with QWEN_API_KEY — a one-variable
    # swap. The LLM is an ASSIST only: safety gates and scoring never depend on
    # it, and every generated claim is validated against a source finding.
    llm_enabled: bool = False
    qwen_base_url: str = "http://localhost:11434/v1"  # Ollama default; Qwen Cloud in prod
    qwen_api_key: str = ""  # empty is fine for local Ollama
    # Dev default is a NON-thinking model: qwen3's thinking mode burns the
    # token budget invisibly through OpenAI-compatible endpoints (Ollama /v1
    # neither disables nor surfaces it — verified 2026-06-12). On Qwen Cloud
    # use a commercial model (qwen-plus) or disable thinking via
    # QWEN_EXTRA_BODY='{"enable_thinking": false}'.
    qwen_model: str = "qwen2.5:3b"
    qwen_timeout_seconds: float = 30.0
    # JSON object merged into every chat-completions request body — the seam
    # for provider-specific knobs (e.g. DashScope's enable_thinking) without
    # touching code. Empty = no extras.
    qwen_extra_body: str = ""

    @property
    def sqlalchemy_url(self) -> str:
        """DATABASE_URL with the psycopg3 driver pinned for SQLAlchemy."""
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def assert_production_safe(self) -> None:
        """Refuse to start in production with dev secrets. Called at app startup."""
        if not self.is_production:
            return
        problems = []
        if self.app_secret == _DEV_SECRET or len(self.app_secret) < 32:
            problems.append("APP_SECRET is unset/weak")
        if "change-me" in self.database_url:
            problems.append("DATABASE_URL uses the placeholder password")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true in production")
        if not self.vault_master_key:
            problems.append("VAULT_MASTER_KEY is required in production (KMS-backed)")
        if problems:
            raise RuntimeError(f"Refusing to start in production: {'; '.join(problems)}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
