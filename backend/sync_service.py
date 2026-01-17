import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.database import User, Door, AccessLog, SyncStatus, async_session
from backend.openpath_client import OpenPathClient

logger = logging.getLogger(__name__)


class SyncService:
    """Service to sync data from OpenPath API to local database."""
    
    def __init__(self):
        self.client = OpenPathClient()
    
    async def close(self):
        """Close the OpenPath client."""
        await self.client.close()
    
    async def _update_sync_status(
        self, 
        session: AsyncSession, 
        sync_type: str, 
        status: str, 
        count: int = 0, 
        error: Optional[str] = None
    ):
        """Update sync status in database."""
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
    
    async def _get_last_sync_time(self, session: AsyncSession, sync_type: str) -> Optional[datetime]:
        """Get last successful sync time for a sync type."""
        result = await session.execute(
            select(SyncStatus).where(
                SyncStatus.sync_type == sync_type,
                SyncStatus.status == "success"
            )
        )
        sync_status = result.scalar_one_or_none()
        return sync_status.last_sync_at if sync_status else None
    
    async def sync_users(self) -> dict:
        """Sync users from OpenPath."""
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
                    # Map status: A = active, I = inactive, S = suspended
                    status_map = {"A": "active", "I": "inactive", "S": "suspended"}
                    status = status_map.get(user_data.get("status", ""), user_data.get("status", "unknown"))
                    
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
        """Sync doors/entries from OpenPath."""
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
                    
                    # Get location from zone.site.name
                    zone = entry_data.get("zone", {})
                    site = zone.get("site", {})
                    location = site.get("name", "") or zone.get("name", "")
                    
                    # Get status from entryState.name
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
    
    async def sync_access_logs(self, days_back: int = 30, max_records: int = 50000) -> dict:
        """Sync access activity from OpenPath.
        
        Args:
            days_back: Not currently used by API but kept for future use
            max_records: Maximum number of records to fetch (default 50,000 for ~1 year of data)
        """
        async with async_session() as session:
            try:
                await self._update_sync_status(session, "access_logs", "in_progress")
                await session.commit()
                
                # Fetch activity (API returns most recent first)
                # Increased limit to get more historical data
                activity = await self.client.get_all_activity(max_records=max_records)
                synced_count = 0
                
                for event in activity:
                    # Use requestId as unique identifier, or create one from time+user
                    event_id = str(event.get("requestId", "")) or f"{event.get('time', '')}-{event.get('userId', '')}"
                    if not event_id or event_id == "-":
                        continue
                    
                    # Parse timestamp from timeIsoString
                    timestamp_str = event.get("timeIsoString")
                    if timestamp_str:
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                        except:
                            # Try Unix timestamp
                            try:
                                timestamp = datetime.utcfromtimestamp(event.get("time", 0))
                            except:
                                timestamp = datetime.utcnow()
                    else:
                        timestamp = datetime.utcnow()
                    
                    # Get user info directly from activity
                    user_id = str(event.get("userId", "")) if event.get("userId") else None
                    user_name = event.get("userName", "")
                    user_email = event.get("userEmail", "")
                    
                    # Extract door name from sourceDevice.name
                    # Format: "Reader X (ACU) Door X: [Door Name] Reader" or just the door name
                    source_device = event.get("sourceDevice", {})
                    source_name = source_device.get("name", "")
                    door_name = source_name
                    
                    # Try to extract cleaner door name if it follows the pattern
                    if ":" in source_name:
                        # Extract part after the colon
                        door_name = source_name.split(":")[-1].strip()
                        # Remove trailing "Reader" if present
                        if door_name.endswith(" Reader"):
                            door_name = door_name[:-7].strip()
                    
                    # Event type from subCategory (e.g., "Entry Unlock")
                    event_type = event.get("subCategory", event.get("category", "unknown"))
                    
                    # Credential type (e.g., "mobile", "card")
                    credential_type = event.get("credentialTypeModelName", "")
                    
                    # Result (Granted, Denied, etc.)
                    result = event.get("result", "")
                    
                    stmt = sqlite_insert(AccessLog).values(
                        openpath_id=event_id,
                        user_openpath_id=user_id,
                        door_openpath_id=None,  # We don't have direct entry IDs
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
    
    async def sync_all(self, days_back: int = 30, max_records: int = 50000) -> dict:
        """Run full sync of all data.
        
        Args:
            days_back: Not currently used but kept for future use
            max_records: Maximum access log records to fetch (default 50,000)
        """
        results = {
            "started_at": datetime.utcnow().isoformat(),
            "users": None,
            "doors": None,
            "access_logs": None
        }
        
        # Sync in order: users, doors, then access logs
        results["users"] = await self.sync_users()
        results["doors"] = await self.sync_doors()
        results["access_logs"] = await self.sync_access_logs(days_back, max_records)
        
        results["completed_at"] = datetime.utcnow().isoformat()
        
        return results
    
    async def get_sync_status(self) -> list[dict]:
        """Get current sync status for all types."""
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
