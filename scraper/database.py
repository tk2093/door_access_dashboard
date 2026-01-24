"""
Database models and session management for the scraper.

This module defines the SQLAlchemy ORM models that mirror the backend schema.
Both the scraper and backend must use identical table structures to share
the same database safely.

Models:
    - User: OpenPath user accounts
    - Door: Physical door/entry points
    - AccessLog: Individual access events (unlocks, denials, etc.)
    - SyncStatus: Tracks the last sync time and status for each data type
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

from config import get_settings

Base = declarative_base()


class User(Base):
    """
    Represents a user from the OpenPath system.
    
    Users are synced from the OpenPath API and stored locally for quick lookups
    and to maintain referential integrity with access logs.
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    openpath_id = Column(String(100), unique=True, nullable=False, index=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(255))
    status = Column(String(50))  # active, inactive, suspended
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    access_logs = relationship("AccessLog", back_populates="user")
    
    @property
    def full_name(self) -> str:
        """Returns the user's full name, or 'Unknown' if not available."""
        return f"{self.first_name or ''} {self.last_name or ''}".strip() or "Unknown"


class Door(Base):
    """
    Represents a door or entry point from the OpenPath system.
    
    Doors are physical access points (doors, gates, turnstiles) that users
    can unlock using their credentials.
    """
    __tablename__ = "doors"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    openpath_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    location = Column(String(255))
    status = Column(String(50))  # online, offline, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    access_logs = relationship("AccessLog", back_populates="door")


class AccessLog(Base):
    """
    Records an individual access event.
    
    Each record represents a single interaction between a user and a door,
    such as an unlock request, denial, or other access-related event.
    
    The raw_data field stores the complete JSON response from OpenPath
    for debugging and future data extraction needs.
    """
    __tablename__ = "access_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    openpath_id = Column(String(100), unique=True, nullable=False, index=True)
    user_openpath_id = Column(String(100), ForeignKey("users.openpath_id"), index=True)
    door_openpath_id = Column(String(100), ForeignKey("doors.openpath_id"), index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    event_type = Column(String(100))  # Entry Unlock, Access Denied, etc.
    credential_type = Column(String(100))  # mobile, card, pin, etc.
    # Denormalized fields for efficient querying without joins
    user_name = Column(String(255), index=True)
    user_email = Column(String(255))
    door_name = Column(String(255), index=True)
    result = Column(String(50))  # Granted, Denied, etc.
    raw_data = Column(Text)  # Complete JSON from OpenPath API
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="access_logs")
    door = relationship("Door", back_populates="access_logs")


class SyncStatus(Base):
    """
    Tracks synchronization status for each data type.
    
    Used to monitor sync health and determine when data was last updated.
    Each sync_type (users, doors, access_logs) has its own status record.
    """
    __tablename__ = "sync_status"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sync_type = Column(String(50), unique=True, nullable=False)  # users, doors, access_logs
    last_sync_at = Column(DateTime)
    last_sync_count = Column(Integer, default=0)
    status = Column(String(50), default="never")  # never, success, failed, in_progress
    error_message = Column(Text)


# Database engine configuration
settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """
    Initialize database tables.
    
    Creates all tables defined by the ORM models if they don't exist.
    Safe to call multiple times - existing tables are not modified.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """
    Close database connections.
    
    Should be called when the scraper finishes to clean up resources.
    """
    await engine.dispose()
