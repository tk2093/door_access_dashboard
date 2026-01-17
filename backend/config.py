from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # OpenPath API
    openpath_username: str = ""
    openpath_password: str = ""
    openpath_org_id: str = ""
    openpath_base_url: str = "https://api.openpath.com"
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./door_access.db"
    
    # Sync settings
    sync_interval_minutes: int = 15
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
