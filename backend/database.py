from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

from backend.config import get_settings

Base = declarative_base()


class User(Base):
    """User from OpenPath system."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    openpath_id = Column(String(100), unique=True, nullable=False, index=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(255))
    status = Column(String(50))  # active, suspended, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    access_logs = relationship("AccessLog", back_populates="user")
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name or ''} {self.last_name or ''}".strip() or "Unknown"


class Door(Base):
    """Door/Entry from OpenPath system."""
    __tablename__ = "doors"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    openpath_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    location = Column(String(255))
    status = Column(String(50))  # online, offline, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    access_logs = relationship("AccessLog", back_populates="door")


class AccessLog(Base):
    """Access log entry - when someone accessed a door."""
    __tablename__ = "access_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    openpath_id = Column(String(100), unique=True, nullable=False, index=True)
    user_openpath_id = Column(String(100), ForeignKey("users.openpath_id"), index=True)
    door_openpath_id = Column(String(100), ForeignKey("doors.openpath_id"), index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    event_type = Column(String(100))  # entry, exit, denied, etc.
    credential_type = Column(String(100))  # mobile, card, pin, etc.
    # Store extracted data directly for easier querying
    user_name = Column(String(255), index=True)
    user_email = Column(String(255))
    door_name = Column(String(255), index=True)
    result = Column(String(50))  # Granted, Denied, etc.
    raw_data = Column(Text)  # Store raw JSON for debugging
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="access_logs")
    door = relationship("Door", back_populates="access_logs")


class SyncStatus(Base):
    """Track sync status and last sync time."""
    __tablename__ = "sync_status"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sync_type = Column(String(50), unique=True, nullable=False)  # users, doors, access_logs
    last_sync_at = Column(DateTime)
    last_sync_count = Column(Integer, default=0)
    status = Column(String(50), default="never")  # never, success, failed, in_progress
    error_message = Column(Text)


# Database engine and session
settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Get database session."""
    async with async_session() as session:
        yield session
