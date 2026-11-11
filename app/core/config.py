from functools import lru_cache

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
        if self.ENVIRONMENT.lower() == "production":
            if self.JWT_SECRET_KEY == "development-only-change-this-secret-key-now":
                raise ValueError("Set a unique JWT_SECRET_KEY in production")
            if not self.COOKIE_SECURE:
                raise ValueError("COOKIE_SECURE must be true in production")
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
