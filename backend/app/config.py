from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "UGC Influencer Outreach"
    app_env: str = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://ugc:ugc_password@localhost:5432/ugc_db"
    database_url_sync: str = "postgresql://ugc:ugc_password@localhost:5432/ugc_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security
    secret_key: str = "change-me-to-a-random-string-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    # CORS
    frontend_url: str = "http://localhost:4317"
    base_url: str = "http://localhost:8917"

    # AI
    ai_provider: str = "claude"  # "claude" or "openai"
    claude_api_key: str = ""
    openai_api_key: str = ""

    # Email - SES
    ses_access_key_id: str = ""
    ses_secret_access_key: str = ""
    ses_region: str = "us-east-1"

    # Email - SendGrid
    sendgrid_api_key: str = ""

    # Email - SMTP
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    # Email sending behavior
    email_batch_size: int = 100
    email_batch_delay_seconds: int = 120
    export_max_rows: int = 10000

    # File uploads / attachments (local filesystem volume)
    upload_dir: str = "uploads"
    upload_max_bytes: int = 10 * 1024 * 1024  # 10 MB
    upload_allowed_content_types: set[str] = {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/svg+xml",
        "application/pdf",
        "text/plain",
        "text/csv",
        "application/zip",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    # WotoHub discovery
    woto_api_key: str = ""
    woto_api_base_url: str = "https://api.wotohub.com/api-gateway"
    woto_request_timeout_seconds: float = 30.0
    woto_page_size: int = 50
    woto_default_sync_limit: int = 50

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
