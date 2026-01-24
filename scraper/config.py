"""
Configuration management for the scraper.

Loads settings from environment variables and .env file.
Uses the same configuration schema as the backend to ensure compatibility.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All settings can be overridden via environment variables or a .env file
    in the project root directory.
    
    Attributes:
        openpath_username: Email/username for OpenPath API authentication
        openpath_password: Password for OpenPath API authentication
        openpath_org_id: Organization ID in OpenPath (auto-detected if empty)
        openpath_base_url: Base URL for OpenPath API
        database_url: SQLAlchemy async database connection string
        sync_max_records: Maximum number of access log records to fetch per sync
    """
    
    # OpenPath API credentials
    openpath_username: str = ""
    openpath_password: str = ""
    openpath_org_id: str = ""
    openpath_base_url: str = "https://api.openpath.com"
    
    # Database connection
    database_url: str = "sqlite+aiosqlite:///./door_access.db"
    
    # Sync settings
    sync_max_records: int = 50000  # Max access logs to fetch per sync
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra env vars like SYNC_INTERVAL_MINUTES


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Settings are cached after first load to avoid repeated file I/O.
    The cache persists for the lifetime of the process.
    
    Returns:
        Settings instance with values from environment/.env file
    """
    return Settings()
