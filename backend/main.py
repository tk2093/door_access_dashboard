import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pathlib import Path

from backend.database import init_db
from backend.config import get_settings
from backend.sync_service import SyncService
from backend.routes import dashboard, sync

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Scheduler for background sync
scheduler = AsyncIOScheduler()


async def scheduled_sync():
    """Background sync job."""
    logger.info("Starting scheduled sync...")
    service = SyncService()
    try:
        result = await service.sync_all(days_back=7)  # Only sync last 7 days for scheduled syncs
        logger.info(f"Scheduled sync completed: {result}")
    except Exception as e:
        logger.error(f"Scheduled sync failed: {str(e)}")
    finally:
        await service.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Door Access Dashboard...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Start scheduler
    settings = get_settings()
    scheduler.add_job(
        scheduled_sync,
        'interval',
        minutes=settings.sync_interval_minutes,
        id='sync_job',
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"Scheduler started - syncing every {settings.sync_interval_minutes} minutes")
    
    yield
    
    # Shutdown
    scheduler.shutdown()
    logger.info("Scheduler stopped")


# Create FastAPI app
app = FastAPI(
    title="Door Access Dashboard",
    description="Interactive dashboard for OpenPath door access system",
    version="1.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(dashboard.router)
app.include_router(sync.router)

# Serve static files (frontend)
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


@app.get("/")
async def serve_frontend():
    """Serve the main dashboard page."""
    index_path = frontend_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Dashboard frontend not found. Please check the frontend folder."}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "door-access-dashboard"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
