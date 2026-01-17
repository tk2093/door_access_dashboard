from fastapi import APIRouter, BackgroundTasks
from backend.sync_service import SyncService
from backend.openpath_client import OpenPathClient

router = APIRouter(prefix="/api/sync", tags=["sync"])

# Global sync state
_sync_in_progress = False


@router.get("/status")
async def get_sync_status():
    """Get current sync status."""
    service = SyncService()
    try:
        status = await service.get_sync_status()
        return {
            "sync_in_progress": _sync_in_progress,
            "statuses": status
        }
    finally:
        await service.close()


@router.post("/trigger")
async def trigger_sync(
    background_tasks: BackgroundTasks, 
    days_back: int = 30,
    max_records: int = 50000
):
    """Trigger a manual sync of all data.
    
    Args:
        days_back: Not currently used but kept for future use
        max_records: Maximum access log records to fetch (default 50,000 for ~1 year of data)
    """
    global _sync_in_progress
    
    if _sync_in_progress:
        return {"status": "already_running", "message": "A sync is already in progress"}
    
    async def run_sync():
        global _sync_in_progress
        _sync_in_progress = True
        service = SyncService()
        try:
            await service.sync_all(days_back=days_back, max_records=max_records)
        finally:
            _sync_in_progress = False
            await service.close()
    
    background_tasks.add_task(run_sync)
    
    return {"status": "started", "message": f"Sync started in background (fetching up to {max_records:,} records)"}


@router.post("/users")
async def sync_users():
    """Sync only users."""
    service = SyncService()
    try:
        result = await service.sync_users()
        return result
    finally:
        await service.close()


@router.post("/doors")
async def sync_doors():
    """Sync only doors."""
    service = SyncService()
    try:
        result = await service.sync_doors()
        return result
    finally:
        await service.close()


@router.post("/access-logs")
async def sync_access_logs(days_back: int = 30, max_records: int = 50000):
    """Sync only access logs.
    
    Args:
        days_back: Not currently used but kept for future use
        max_records: Maximum records to fetch (default 50,000)
    """
    service = SyncService()
    try:
        result = await service.sync_access_logs(days_back=days_back, max_records=max_records)
        return result
    finally:
        await service.close()


@router.get("/test-connection")
async def test_openpath_connection():
    """Test connection to OpenPath API."""
    client = OpenPathClient()
    try:
        result = await client.test_connection()
        return result
    finally:
        await client.close()
