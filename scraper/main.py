"""
Main entry point for the OpenPath data scraper.

This script runs a complete sync of all data from the OpenPath API to the
local database.

Usage:
    Manual run:
        python -m scraper.main
    
    With custom max records:
        python -m scraper.main --max-records 100000
    
    Cron job (every 15 minutes):
        */15 * * * * cd /path/to/project && /path/to/venv/bin/python -m scraper.main >> /var/log/door_scraper.log 2>&1

Exit codes:
    0 - Sync completed successfully (all types succeeded)
    1 - Sync completed with failures (one or more types failed)
    2 - Sync failed to start (configuration or initialization error)
"""

import asyncio
import argparse
import logging
import sys
from datetime import datetime

from database import init_db, close_db
from sync import SyncService
from config import get_settings

# Configure logging to stdout for cron visibility
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


async def run_sync(max_records: int) -> bool:
    """
    Execute a complete data sync.
    
    Initializes the database, runs all sync operations, and cleans up
    resources when complete.
    
    Args:
        max_records: Maximum number of access log records to fetch
        
    Returns:
        True if all syncs succeeded, False if any failed
    """
    logger.info("=" * 60)
    logger.info("OpenPath Scraper - Starting sync")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)
    
    # Validate configuration
    settings = get_settings()
    if not settings.openpath_username or not settings.openpath_password:
        logger.error("Missing OpenPath credentials. Check .env file.")
        logger.error("Required: OPENPATH_USERNAME, OPENPATH_PASSWORD")
        return False
    
    # Initialize database tables
    logger.info("Initializing database...")
    await init_db()
    
    # Run sync
    service = SyncService()
    all_success = True
    
    try:
        logger.info(f"Starting sync (max_records={max_records})...")
        results = await service.sync_all(max_records=max_records)
        
        # Log results summary
        logger.info("-" * 60)
        logger.info("Sync Results:")
        logger.info(f"  Started:   {results['started_at']}")
        logger.info(f"  Completed: {results['completed_at']}")
        logger.info("-" * 60)
        
        for sync_type in ["users", "doors", "access_logs"]:
            result = results.get(sync_type, {})
            status = result.get("status", "unknown")
            count = result.get("count", 0)
            error = result.get("error", "")
            
            if status == "success":
                logger.info(f"  {sync_type}: SUCCESS ({count} records)")
            else:
                logger.error(f"  {sync_type}: FAILED - {error}")
                all_success = False
        
        logger.info("-" * 60)
        
    except Exception as e:
        logger.exception(f"Unexpected error during sync: {str(e)}")
        all_success = False
        
    finally:
        # Clean up resources
        await service.close()
        await close_db()
        logger.info("Connections closed")
    
    if all_success:
        logger.info("Sync completed successfully")
    else:
        logger.error("Sync completed with errors")
    
    logger.info("=" * 60)
    return all_success


def main():
    """
    Command-line entry point.
    
    Parses arguments and runs the async sync operation.
    """
    parser = argparse.ArgumentParser(
        description="Sync data from OpenPath API to local database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scraper.main                    # Default sync (50,000 records max)
  python -m scraper.main --max-records 10000   # Smaller sync for testing
  python -m scraper.main --max-records 100000  # Larger historical sync
        """
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=50000,
        help="Maximum number of access log records to fetch (default: 50000)"
    )
    
    args = parser.parse_args()
    
    # Run async sync
    success = asyncio.run(run_sync(args.max_records))
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
