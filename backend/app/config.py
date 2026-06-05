"""Application configuration using Pydantic Settings."""
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, field_validator
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "ICCBPO Certificate Checker"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "dev-secret-key-change-in-production-must-be-32-chars"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:80"]
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1", "*"]
    API_V1_PREFIX: str = "/api/v1"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://iccbpo:password@localhost:5432/iccbpo_cert_checker"
    DATABASE_URL_SYNC: str = "postgresql://iccbpo:password@localhost:5432/iccbpo_cert_checker"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # JWT
    JWT_SECRET_KEY: str = "jwt-secret-key-change-in-production-must-be-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # File Storage
    UPLOAD_DIR: str = "/app/uploads"
    SCREENSHOT_DIR: str = "/app/screenshots"
    REPORTS_DIR: str = "/app/reports"
    TEMP_DIR: str = "/app/temp"
    MAX_FILE_SIZE_MB: int = 50
    FILE_RETENTION_DAYS: int = 90

    # Encryption
    ENCRYPTION_KEY: Optional[str] = None

    # Playwright
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_TIMEOUT_MS: int = 30000
    SCREENSHOT_TIMEOUT_MS: int = 10000

    # OCR
    TESSERACT_CMD: str = "/usr/bin/tesseract"
    OCR_LANGUAGES: str = "eng+spa+por+fra"
    OCR_DPI: int = 300

    # Verification
    REQUEST_TIMEOUT_SECONDS: int = 30
    MAX_REDIRECTS: int = 5
    VERIFY_SSL: bool = True

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    NOTIFICATION_FROM: str = "noreply@iccbpo.com"
    NOTIFICATION_ENABLED: bool = False

    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = ""

    # MFA
    MFA_ISSUER: str = "ICCBPO CertChecker"
    MFA_ENABLED: bool = False

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Initial admin
    ADMIN_EMAIL: str = "admin@iccbpo.com"
    ADMIN_PASSWORD: str = "Admin@ICCBPO2024!"
    ADMIN_NAME: str = "System Admin"

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


settings = Settings()
