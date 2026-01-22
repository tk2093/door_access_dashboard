#!/usr/bin/env python3
"""
Migration script to transfer data from local SQLite to PostgreSQL.

Usage:
    # Set the target PostgreSQL URL in environment or pass as argument
    export TARGET_DATABASE_URL="postgresql+asyncpg://user:pass@host/db?sslmode=require"
    uv run python -m backend.migrate_to_postgres

    # Or pass directly:
    uv run python -m backend.migrate_to_postgres "postgresql+asyncpg://user:pass@host/db?sslmode=require"
"""

import asyncio
import sys
import os
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import Base, User, Door, AccessLog, SyncStatus


# Default SQLite source database
SQLITE_URL = "sqlite+aiosqlite:///./door_access.db"
BATCH_SIZE = 500  # For large tables like access_logs


async def get_source_data(source_session: AsyncSession) -> dict:
    """Read all data from the source SQLite database."""
    print("Reading data from SQLite database...")
    
    # Read users
    result = await source_session.execute(select(User))
    users = result.scalars().all()
    print(f"  Found {len(users)} users")
    
    # Read doors
    result = await source_session.execute(select(Door))
    doors = result.scalars().all()
    print(f"  Found {len(doors)} doors")
    
    # Read access logs
    result = await source_session.execute(select(AccessLog))
    access_logs = result.scalars().all()
    print(f"  Found {len(access_logs)} access logs")
    
    # Read sync status
    result = await source_session.execute(select(SyncStatus))
    sync_statuses = result.scalars().all()
    print(f"  Found {len(sync_statuses)} sync status records")
    
    return {
        "users": users,
        "doors": doors,
        "access_logs": access_logs,
        "sync_statuses": sync_statuses,
    }


def model_to_dict(obj, exclude_id: bool = True) -> dict:
    """Convert SQLAlchemy model to dictionary."""
    data = {}
    for column in obj.__table__.columns:
        if exclude_id and column.name == "id":
            continue
        value = getattr(obj, column.name)
        data[column.name] = value
    return data


async def migrate_data(target_url: str, data: dict):
    """Migrate data to the target PostgreSQL database."""
    print(f"\nConnecting to PostgreSQL...")
    
    target_engine = create_async_engine(target_url, echo=False)
    target_session_maker = async_sessionmaker(
        target_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Create tables
    print("Creating tables in PostgreSQL...")
    async with target_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with target_session_maker() as session:
        # Migrate users
        print(f"\nMigrating {len(data['users'])} users...")
        for user in data["users"]:
            new_user = User(**model_to_dict(user))
            session.add(new_user)
        await session.commit()
        print("  Users migrated successfully")
        
        # Migrate doors
        print(f"Migrating {len(data['doors'])} doors...")
        for door in data["doors"]:
            new_door = Door(**model_to_dict(door))
            session.add(new_door)
        await session.commit()
        print("  Doors migrated successfully")
        
        # Migrate access logs in batches
        access_logs = data["access_logs"]
        total_logs = len(access_logs)
        print(f"Migrating {total_logs} access logs (in batches of {BATCH_SIZE})...")
        
        for i in range(0, total_logs, BATCH_SIZE):
            batch = access_logs[i:i + BATCH_SIZE]
            for log in batch:
                new_log = AccessLog(**model_to_dict(log))
                session.add(new_log)
            await session.commit()
            print(f"  Migrated {min(i + BATCH_SIZE, total_logs)}/{total_logs} access logs")
        
        print("  Access logs migrated successfully")
        
        # Migrate sync status
        print(f"Migrating {len(data['sync_statuses'])} sync status records...")
        for status in data["sync_statuses"]:
            new_status = SyncStatus(**model_to_dict(status))
            session.add(new_status)
        await session.commit()
        print("  Sync status migrated successfully")
    
    await target_engine.dispose()


async def verify_migration(target_url: str, original_counts: dict):
    """Verify that the migration was successful."""
    print("\nVerifying migration...")
    
    target_engine = create_async_engine(target_url, echo=False)
    target_session_maker = async_sessionmaker(
        target_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with target_session_maker() as session:
        # Count records in each table
        result = await session.execute(select(User))
        user_count = len(result.scalars().all())
        
        result = await session.execute(select(Door))
        door_count = len(result.scalars().all())
        
        result = await session.execute(select(AccessLog))
        log_count = len(result.scalars().all())
        
        result = await session.execute(select(SyncStatus))
        status_count = len(result.scalars().all())
    
    await target_engine.dispose()
    
    print(f"  Users: {user_count} (expected {original_counts['users']})")
    print(f"  Doors: {door_count} (expected {original_counts['doors']})")
    print(f"  Access Logs: {log_count} (expected {original_counts['access_logs']})")
    print(f"  Sync Status: {status_count} (expected {original_counts['sync_statuses']})")
    
    all_match = (
        user_count == original_counts["users"]
        and door_count == original_counts["doors"]
        and log_count == original_counts["access_logs"]
        and status_count == original_counts["sync_statuses"]
    )
    
    if all_match:
        print("\n✅ Migration verified successfully! All records transferred.")
    else:
        print("\n⚠️  Warning: Record counts don't match. Please check the data.")
    
    return all_match


async def main():
    """Main migration function."""
    # Get target PostgreSQL URL
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
    else:
        target_url = os.environ.get("TARGET_DATABASE_URL")
    
    if not target_url:
        print("Error: No target database URL provided.")
        print("\nUsage:")
        print("  export TARGET_DATABASE_URL='postgresql+asyncpg://user:pass@host/db'")
        print("  uv run python -m backend.migrate_to_postgres")
        print("\nOr:")
        print("  uv run python -m backend.migrate_to_postgres 'postgresql+asyncpg://...'")
        sys.exit(1)
    
    if not target_url.startswith("postgresql"):
        print("Error: Target URL must be a PostgreSQL connection string.")
        print("Example: postgresql+asyncpg://user:pass@host/dbname?sslmode=require")
        sys.exit(1)
    
    # Check if SQLite database exists
    if not os.path.exists("door_access.db"):
        print("Error: Local SQLite database 'door_access.db' not found.")
        print("Make sure you're running this from the project root directory.")
        sys.exit(1)
    
    print("=" * 60)
    print("SQLite to PostgreSQL Migration")
    print("=" * 60)
    print(f"\nSource: {SQLITE_URL}")
    print(f"Target: {target_url[:50]}..." if len(target_url) > 50 else f"Target: {target_url}")
    print()
    
    # Connect to source SQLite database
    source_engine = create_async_engine(SQLITE_URL, echo=False)
    source_session_maker = async_sessionmaker(
        source_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with source_session_maker() as session:
        # Read all data from SQLite
        data = await get_source_data(session)
    
    await source_engine.dispose()
    
    # Store original counts for verification
    original_counts = {
        "users": len(data["users"]),
        "doors": len(data["doors"]),
        "access_logs": len(data["access_logs"]),
        "sync_statuses": len(data["sync_statuses"]),
    }
    
    # Check if there's data to migrate
    total_records = sum(original_counts.values())
    if total_records == 0:
        print("\nNo data found in SQLite database. Nothing to migrate.")
        sys.exit(0)
    
    # Migrate data to PostgreSQL
    await migrate_data(target_url, data)
    
    # Verify migration
    await verify_migration(target_url, original_counts)
    
    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Update your .env file with the new DATABASE_URL:")
    print(f"   DATABASE_URL={target_url}")
    print("2. Restart your application")
    print("3. Verify the dashboard works correctly")
    print("4. (Optional) Delete the local door_access.db file")


if __name__ == "__main__":
    asyncio.run(main())
