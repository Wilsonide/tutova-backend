from functools import lru_cache
from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )
    APP_NAME: str = "Tutova API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/tutova"
    JWT_SECRET_KEY: str = "development-only-change-this-secret-key-now"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = 15
    REFRESH_TOKEN_DAYS: int = 14
    REFRESH_COOKIE_NAME: str = "tutova_refresh"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    CORS_ORIGINS: str = "http://localhost:3000"
    BOOTSTRAP_ADMIN_EMAIL: str = "ich@gmail.com"
    BOOTSTRAP_ADMIN_PASSWORD: str = "@Abudon2026!!"
    CURRENT_NDA_VERSION: str = "v1"
    REQUIRED_TUTOR_VERIFICATION_TYPES: str = "IDENTITY,QUALIFICATION"
    PLATFORM_FEE_BPS: int = 0
    PAYMENT_PROVIDER: str = "NONE"
    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_PUBLIC_KEY: str = ""
    PAYSTACK_BASE_URL: str = "https://api.paystack.co"
    PAYSTACK_CALLBACK_URL: str = ""
    PAYSTACK_CHANNELS: str = "card,bank_transfer,ussd"
    PAYSTACK_TIMEOUT_SECONDS: float = 15.0
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    CLOUDINARY_PROFILE_PICTURE_MAX_SIZE: int = 5 * 1024 * 1024
    CLOUDINARY_IDENTITY_DOCUMENT_MAX_SIZE: int = 10 * 1024 * 1024
    CLOUDINARY_IDENTITY_DOCUMENT_URL_TTL_SECONDS: int = 300
    FRONTEND_BASE_URL: str = "http://localhost:3000"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_TLS: bool = True
    PASSWORD_RESET_TOKEN_MINUTES: int = 30
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT_SECONDS: int = 30
    DB_POOL_RECYCLE_SECONDS: int = 1800

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters")
        return value

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.PAYMENT_PROVIDER.upper() not in {"NONE", "PAYSTACK"}:
            raise ValueError("PAYMENT_PROVIDER must be NONE or PAYSTACK")
        if (
            self.PAYMENT_PROVIDER.upper() == "PAYSTACK"
            and not self.PAYSTACK_SECRET_KEY.strip()
        ):
            raise ValueError(
                "PAYSTACK_SECRET_KEY is required when PAYMENT_PROVIDER=PAYSTACK"
            )
        if self.PAYSTACK_TIMEOUT_SECONDS <= 0:
            raise ValueError("PAYSTACK_TIMEOUT_SECONDS must be positive")
        if self.PASSWORD_RESET_TOKEN_MINUTES <= 0:
            raise ValueError("PASSWORD_RESET_TOKEN_MINUTES must be positive")
        if self.DB_POOL_SIZE < 1 or self.DB_MAX_OVERFLOW < 0:
            raise ValueError("Database pool size must be positive and overflow non-negative")
        if self.DB_POOL_TIMEOUT_SECONDS <= 0 or self.DB_POOL_RECYCLE_SECONDS <= 0:
            raise ValueError("Database pool timeout and recycle values must be positive")
        if self.ENVIRONMENT.lower() == "production":
            if self.JWT_SECRET_KEY == "development-only-change-this-secret-key-now":
                raise ValueError("Set a unique JWT_SECRET_KEY in production")
            if not self.COOKIE_SECURE:
                raise ValueError("COOKIE_SECURE must be true in production")
            frontend_url = self.FRONTEND_BASE_URL.strip()
            if not frontend_url.startswith("https://"):
                raise ValueError("FRONTEND_BASE_URL must use HTTPS in production")
            origins = self.cors_origins
            if not origins or "*" in origins:
                raise ValueError("CORS_ORIGINS must contain explicit origins in production")
            if any(not origin.startswith("https://") for origin in origins):
                raise ValueError("Every production CORS_ORIGINS entry must use HTTPS")
            if not self.SMTP_HOST.strip() or not self.SMTP_FROM_EMAIL.strip():
                raise ValueError("SMTP_HOST and SMTP_FROM_EMAIL are required in production")
            if self.SMTP_USERNAME.strip() and not self.SMTP_PASSWORD:
                raise ValueError("SMTP_PASSWORD is required when SMTP_USERNAME is configured")
            if not 1 <= self.SMTP_PORT <= 65535:
                raise ValueError("SMTP_PORT must be between 1 and 65535")
            if self.PAYMENT_PROVIDER.upper() == "PAYSTACK":
                if not self.PAYSTACK_CALLBACK_URL.strip():
                    raise ValueError("PAYSTACK_CALLBACK_URL is required when Paystack is enabled in production")
                callback = urlparse(self.PAYSTACK_CALLBACK_URL.strip())
                frontend = urlparse(frontend_url)
                if callback.scheme != "https" or not callback.netloc:
                    raise ValueError("PAYSTACK_CALLBACK_URL must be an absolute HTTPS URL in production")
                if callback.netloc != frontend.netloc:
                    raise ValueError("PAYSTACK_CALLBACK_URL must use the same host as FRONTEND_BASE_URL")
        return self

    @property
    def paystack_channels(self) -> list[str]:
        return [
            channel.strip()
            for channel in self.PAYSTACK_CHANNELS.split(",")
            if channel.strip()
        ]

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
