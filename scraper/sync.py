"""
Data synchronization logic for OpenPath data.

This module handles the business logic of syncing data from the OpenPath API
to the local database. It performs upserts (insert or update) to handle both
new records and updates to existing records.

The sync process:
1. Fetch data from OpenPath API
2. Transform API response to match database schema
3. Upsert records to database (insert new, update existing)
4. Track sync status for monitoring
"""

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from database import User, Door, AccessLog, SyncStatus, async_session
from openpath_client import OpenPathClient
from config import get_settings

logger = logging.getLogger(__name__)


class SyncService:
    """
    Service class to synchronize OpenPath data to the local database.
    
    Handles syncing of users, doors, and access logs with proper error
    handling and status tracking.
    
    Usage:
        service = SyncService()
        try:
            results = await service.sync_all()
            print(results)
        finally:
            await service.close()
    """
    
    def __init__(self):
        self.client = OpenPathClient()
        self.settings = get_settings()
    
    async def close(self):
        """Close the OpenPath client connection."""
        await self.client.close()
    
    async def _update_sync_status(
        self,
        session: AsyncSession,
        sync_type: str,
        status: str,
        count: int = 0,
        error: Optional[str] = None
    ):
        """
        Update the sync status record for a given sync type.
        
        Uses upsert to create or update the status record.
        
        Args:
            session: Active database session
            sync_type: Type of sync (users, doors, access_logs)
            status: Current status (in_progress, success, failed)
            count: Number of records synced
            error: Error message if sync failed
        """
        stmt = sqlite_insert(SyncStatus).values(
            sync_type=sync_type,
            last_sync_at=datetime.utcnow(),
            last_sync_count=count,
            status=status,
            error_message=error
        ).on_conflict_do_update(
            index_elements=['sync_type'],
            set_={
                'last_sync_at': datetime.utcnow(),
                'last_sync_count': count,
                'status': status,
                'error_message': error
            }
        )
        await session.execute(stmt)
    
    async def sync_users(self) -> dict:
        """
        Sync all users from OpenPath to the local database.
        
        Fetches all users from the API and upserts them to the database.
        Existing users are updated with the latest information.
        
        Returns:
            Dictionary with sync status and count:
            - status: "success" or "failed"
            - count: Number of users synced
            - error: Error message (only if failed)
        """
        async with async_session() as session:
            try:
                await self._update_sync_status(session, "users", "in_progress")
                await session.commit()
                
                users = await self.client.get_all_users()
                synced_count = 0
                
                for user_data in users:
                    user_id = str(user_data.get("id", ""))
                    if not user_id:
                        continue
                    
                    identity = user_data.get("identity", {})
                    
                    # Map API status codes to human-readable values
                    # A = active, I = inactive, S = suspended
                    status_map = {"A": "active", "I": "inactive", "S": "suspended"}
                    status = status_map.get(
                        user_data.get("status", ""),
                        user_data.get("status", "unknown")
                    )
                    
                    stmt = sqlite_insert(User).values(
                        openpath_id=user_id,
                        first_name=identity.get("firstName", ""),
                        last_name=identity.get("lastName", ""),
                        email=identity.get("email", ""),
                        status=status,
                        updated_at=datetime.utcnow()
                    ).on_conflict_do_update(
                        index_elements=['openpath_id'],
                        set_={
                            'first_name': identity.get("firstName", ""),
                            'last_name': identity.get("lastName", ""),
                            'email': identity.get("email", ""),
                            'status': status,
                            'updated_at': datetime.utcnow()
                        }
                    )
                    await session.execute(stmt)
                    synced_count += 1
                
                await self._update_sync_status(session, "users", "success", synced_count)
                await session.commit()
                
                logger.info(f"Synced {synced_count} users")
                return {"status": "success", "count": synced_count}
                
            except Exception as e:
                logger.error(f"Error syncing users: {str(e)}")
                await self._update_sync_status(session, "users", "failed", error=str(e))
                await session.commit()
                return {"status": "failed", "error": str(e)}
    
    async def sync_doors(self) -> dict:
        """
        Sync all doors/entries from OpenPath to the local database.
        
        Doors are physical entry points (doors, gates, etc.) in the system.
        
        Returns:
            Dictionary with sync status and count
        """
        async with async_session() as session:
            try:
                await self._update_sync_status(session, "doors", "in_progress")
                await session.commit()
                
                entries = await self.client.get_all_entries()
                synced_count = 0
                
                for entry_data in entries:
                    entry_id = str(entry_data.get("id", ""))
                    if not entry_id:
                        continue
                    
                    # Extract location from nested zone.site structure
                    zone = entry_data.get("zone", {})
                    site = zone.get("site", {})
                    location = site.get("name", "") or zone.get("name", "")
                    
                    # Extract status from entryState
                    entry_state = entry_data.get("entryState", {})
                    status = entry_state.get("name", "unknown")
                    
                    stmt = sqlite_insert(Door).values(
                        openpath_id=entry_id,
                        name=entry_data.get("name", "Unknown Door"),
                        location=location,
                        status=status,
                        updated_at=datetime.utcnow()
                    ).on_conflict_do_update(
                        index_elements=['openpath_id'],
                        set_={
                            'name': entry_data.get("name", "Unknown Door"),
                            'location': location,
                            'status': status,
                            'updated_at': datetime.utcnow()
                        }
                    )
                    await session.execute(stmt)
                    synced_count += 1
                
                await self._update_sync_status(session, "doors", "success", synced_count)
                await session.commit()
                
                logger.info(f"Synced {synced_count} doors")
                return {"status": "success", "count": synced_count}
                
            except Exception as e:
                logger.error(f"Error syncing doors: {str(e)}")
                await self._update_sync_status(session, "doors", "failed", error=str(e))
                await session.commit()
                return {"status": "failed", "error": str(e)}
    
    async def sync_access_logs(self, max_records: int = 50000) -> dict:
        """
        Sync access activity logs from OpenPath to the local database.
        
        Access logs are individual events like door unlocks or access denials.
        Uses insert-or-ignore to avoid duplicating existing records.
        
        Args:
            max_records: Maximum number of records to fetch from API.
                        Higher values give more historical data but take
                        longer to sync.
        
        Returns:
            Dictionary with sync status and count
        """
        async with async_session() as session:
            try:
                await self._update_sync_status(session, "access_logs", "in_progress")
                await session.commit()
                
                activity = await self.client.get_all_activity(max_records=max_records)
                synced_count = 0
                
                for event in activity:
                    # Generate unique ID from requestId or fallback to time+user
                    event_id = str(event.get("requestId", "")) or \
                               f"{event.get('time', '')}-{event.get('userId', '')}"
                    if not event_id or event_id == "-":
                        continue
                    
                    # Parse timestamp from ISO string or Unix timestamp
                    timestamp_str = event.get("timeIsoString")
                    if timestamp_str:
                        try:
                            timestamp = datetime.fromisoformat(
                                timestamp_str.replace("Z", "+00:00")
                            )
                        except ValueError:
                            try:
                                timestamp = datetime.utcfromtimestamp(event.get("time", 0))
                            except (ValueError, OSError):
                                timestamp = datetime.utcnow()
                    else:
                        timestamp = datetime.utcnow()
                    
                    # Extract user information
                    user_id = str(event.get("userId", "")) if event.get("userId") else None
                    user_name = event.get("userName", "")
                    user_email = event.get("userEmail", "")
                    
                    # Extract and clean door name from sourceDevice
                    # Format may be: "Reader X (ACU) Door X: [Door Name] Reader"
                    source_device = event.get("sourceDevice", {})
                    source_name = source_device.get("name", "")
                    door_name = source_name
                    
                    if ":" in source_name:
                        # Extract the meaningful part after the colon
                        door_name = source_name.split(":")[-1].strip()
                        # Remove trailing "Reader" suffix if present
                        if door_name.endswith(" Reader"):
                            door_name = door_name[:-7].strip()
                    
                    # Event classification
                    event_type = event.get("subCategory", event.get("category", "unknown"))
                    credential_type = event.get("credentialTypeModelName", "")
                    result = event.get("result", "")
                    
                    # Use insert-or-ignore to skip existing records
                    stmt = sqlite_insert(AccessLog).values(
                        openpath_id=event_id,
                        user_openpath_id=user_id,
                        door_openpath_id=None,  # Entry IDs not available in activity API
                        timestamp=timestamp,
                        event_type=event_type,
                        credential_type=credential_type,
                        user_name=user_name,
                        user_email=user_email,
                        door_name=door_name,
                        result=result,
                        raw_data=json.dumps(event)
                    ).on_conflict_do_nothing(index_elements=['openpath_id'])
                    
                    await session.execute(stmt)
                    synced_count += 1
                
                await self._update_sync_status(session, "access_logs", "success", synced_count)
                await session.commit()
                
                logger.info(f"Synced {synced_count} access logs")
                return {"status": "success", "count": synced_count}
                
            except Exception as e:
                logger.error(f"Error syncing access logs: {str(e)}")
                await self._update_sync_status(session, "access_logs", "failed", error=str(e))
                await session.commit()
                return {"status": "failed", "error": str(e)}
    
    async def sync_all(self, max_records: int = 50000) -> dict:
        """
        Run a complete sync of all data types.
        
        Syncs in order: users, doors, then access logs. This order ensures
        that foreign key references are valid when access logs are inserted.
        
        Args:
            max_records: Maximum access log records to fetch
            
        Returns:
            Dictionary with timestamps and results for each sync type:
            - started_at: ISO timestamp when sync started
            - completed_at: ISO timestamp when sync finished
            - users: Result dict from sync_users()
            - doors: Result dict from sync_doors()
            - access_logs: Result dict from sync_access_logs()
        """
        results = {
            "started_at": datetime.utcnow().isoformat(),
            "users": None,
            "doors": None,
            "access_logs": None
        }
        
        # Sync in dependency order
        results["users"] = await self.sync_users()
        results["doors"] = await self.sync_doors()
        results["access_logs"] = await self.sync_access_logs(max_records)
        
        results["completed_at"] = datetime.utcnow().isoformat()
        
        return results
    
    async def get_sync_status(self) -> list[dict]:
        """
        Get current sync status for all data types.
        
        Returns:
            List of status dictionaries, one for each sync type
        """
        async with async_session() as session:
            result = await session.execute(select(SyncStatus))
            statuses = result.scalars().all()
            return [
                {
                    "sync_type": s.sync_type,
                    "last_sync_at": s.last_sync_at.isoformat() if s.last_sync_at else None,
                    "last_sync_count": s.last_sync_count,
                    "status": s.status,
                    "error_message": s.error_message
                }
                for s in statuses
            ]
