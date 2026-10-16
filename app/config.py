from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Savannah Clinic Booking API"
    app_env: str = "development"

    api_v1_prefix: str = "/api/v1"

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_database: str = "savanaclinic_booking"
    mysql_user: str = "savanaclinic_user"
    mysql_password: SecretStr

    clinic_timezone: str = "Africa/Nairobi"
    booking_min_notice_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()