from fastapi import APIRouter, Query
from sqlalchemy import select, func, desc, and_, or_
from datetime import datetime, timedelta
from typing import Optional

from backend.database import async_session, User, Door, AccessLog, SyncStatus

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/stats")
async def get_stats(
    tz_offset: int = Query(default=0, description="Timezone offset from UTC in minutes (e.g., -480 for PST)")
):
    """Get overview statistics for the dashboard."""
    async with async_session() as session:
        # Convert timezone offset to timedelta
        # tz_offset is in minutes, negative = behind UTC (e.g., -480 for PST)
        # We need to ADD the negated offset to UTC to get local time boundaries in UTC
        offset_delta = timedelta(minutes=tz_offset)
        
        # Get current time in user's local timezone, then find local midnight
        now_utc = datetime.utcnow()
        now_local = now_utc - offset_delta  # Convert UTC to local time
        
        # Calculate local midnight, then convert back to UTC for querying
        local_today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_utc = local_today_start + offset_delta  # Convert local midnight back to UTC
        
        # Week start (Monday) in local time, converted to UTC
        days_since_monday = local_today_start.weekday()
        local_week_start = local_today_start - timedelta(days=days_since_monday)
        week_start_utc = local_week_start + offset_delta
        
        # Month start in local time, converted to UTC
        local_month_start = local_today_start.replace(day=1)
        month_start_utc = local_month_start + offset_delta
        
        # Use UTC-converted boundaries for queries
        today_start = today_start_utc
        week_start = week_start_utc
        month_start = month_start_utc
        now = now_utc
        
        # Total counts
        total_users = await session.scalar(select(func.count(User.id)))
        total_doors = await session.scalar(select(func.count(Door.id)))
        total_access_logs = await session.scalar(select(func.count(AccessLog.id)))
        
        # Access counts by time period
        today_accesses = await session.scalar(
            select(func.count(AccessLog.id)).where(AccessLog.timestamp >= today_start)
        )
        week_accesses = await session.scalar(
            select(func.count(AccessLog.id)).where(AccessLog.timestamp >= week_start)
        )
        month_accesses = await session.scalar(
            select(func.count(AccessLog.id)).where(AccessLog.timestamp >= month_start)
        )
        
        # Active users (accessed in last 7 days)
        active_users = await session.scalar(
            select(func.count(func.distinct(AccessLog.user_openpath_id))).where(
                AccessLog.timestamp >= now - timedelta(days=7)
            )
        )
        
        # Most used door - use door_name from access logs
        most_used_door_result = await session.execute(
            select(AccessLog.door_name, func.count(AccessLog.id).label("count"))
            .where(AccessLog.timestamp >= month_start, AccessLog.door_name.isnot(None))
            .group_by(AccessLog.door_name)
            .order_by(desc("count"))
            .limit(1)
        )
        most_used_door = most_used_door_result.first()
        
        return {
            "total_users": total_users or 0,
            "total_doors": total_doors or 0,
            "total_access_logs": total_access_logs or 0,
            "today_accesses": today_accesses or 0,
            "week_accesses": week_accesses or 0,
            "month_accesses": month_accesses or 0,
            "active_users_7d": active_users or 0,
            "most_used_door": {
                "name": most_used_door[0] if most_used_door else None,
                "count": most_used_door[1] if most_used_door else 0
            }
        }


@router.get("/access-logs")
async def get_access_logs(
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    user_id: Optional[str] = None,
    door_name: Optional[list[str]] = Query(default=None),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    event_type: Optional[str] = None,
    credential_type: Optional[str] = None,
    sort_by: Optional[str] = "timestamp",
    sort_order: Optional[str] = "desc"
):
    """Get paginated access logs with optional filters."""
    async with async_session() as session:
        query = select(AccessLog)
        
        # Apply filters
        conditions = []
        if user_id:
            conditions.append(AccessLog.user_openpath_id == user_id)
        if door_name:
            # Support multiple door names (OR condition)
            door_conditions = [AccessLog.door_name.ilike(f"%{dn}%") for dn in door_name]
            conditions.append(or_(*door_conditions))
        if start_date:
            try:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                conditions.append(AccessLog.timestamp >= start)
            except:
                pass
        if end_date:
            try:
                end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                conditions.append(AccessLog.timestamp <= end)
            except:
                pass
        if event_type:
            conditions.append(AccessLog.event_type.ilike(f"%{event_type}%"))
        if credential_type:
            conditions.append(AccessLog.credential_type.ilike(f"%{credential_type}%"))
        if search:
            search_term = f"%{search}%"
            conditions.append(
                or_(
                    AccessLog.user_name.ilike(search_term),
                    AccessLog.user_email.ilike(search_term),
                    AccessLog.door_name.ilike(search_term)
                )
            )
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await session.scalar(count_query)
        
        # Apply sorting
        sort_column = getattr(AccessLog, sort_by, AccessLog.timestamp)
        if sort_order == "asc":
            query = query.order_by(sort_column)
        else:
            query = query.order_by(desc(sort_column))
        
        # Get paginated results
        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        logs = result.scalars().all()
        
        return {
            "total": total or 0,
            "limit": limit,
            "offset": offset,
            "data": [
                {
                    "id": log.id,
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                    "event_type": log.event_type,
                    "credential_type": log.credential_type,
                    "result": log.result,
                    "user": {
                        "id": log.user_openpath_id,
                        "name": log.user_name or "Unknown",
                        "email": log.user_email
                    },
                    "door": {
                        "name": log.door_name or "Unknown"
                    }
                }
                for log in logs
            ]
        }


@router.get("/access-logs/filters")
async def get_access_log_filters():
    """Get available filter options for access logs."""
    async with async_session() as session:
        # Get unique event types
        event_types_result = await session.execute(
            select(func.distinct(AccessLog.event_type))
            .where(AccessLog.event_type.isnot(None))
        )
        event_types = [r[0] for r in event_types_result.all() if r[0]]
        
        # Get unique credential types
        credential_types_result = await session.execute(
            select(func.distinct(AccessLog.credential_type))
            .where(AccessLog.credential_type.isnot(None))
        )
        credential_types = [r[0] for r in credential_types_result.all() if r[0]]
        
        # Get unique door names
        door_names_result = await session.execute(
            select(func.distinct(AccessLog.door_name))
            .where(AccessLog.door_name.isnot(None))
            .order_by(AccessLog.door_name)
        )
        door_names = [r[0] for r in door_names_result.all() if r[0]]
        
        return {
            "event_types": event_types,
            "credential_types": credential_types,
            "door_names": door_names
        }


@router.get("/users")
async def get_users(
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: Optional[str] = "last_name",
    sort_order: Optional[str] = "asc"
):
    """Get paginated users list."""
    async with async_session() as session:
        query = select(User)
        
        conditions = []
        if search:
            search_term = f"%{search}%"
            conditions.append(
                or_(
                    User.first_name.ilike(search_term),
                    User.last_name.ilike(search_term),
                    User.email.ilike(search_term)
                )
            )
        if status:
            conditions.append(User.status == status)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await session.scalar(count_query)
        
        # Apply sorting
        sort_column = getattr(User, sort_by, User.last_name)
        if sort_order == "asc":
            query = query.order_by(sort_column)
        else:
            query = query.order_by(desc(sort_column))
        
        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        users = result.scalars().all()
        
        # Get access count for each user
        user_access_counts = {}
        if users:
            user_ids = [u.openpath_id for u in users]
            counts_result = await session.execute(
                select(AccessLog.user_openpath_id, func.count(AccessLog.id))
                .where(AccessLog.user_openpath_id.in_(user_ids))
                .group_by(AccessLog.user_openpath_id)
            )
            user_access_counts = {r[0]: r[1] for r in counts_result.all()}
        
        return {
            "total": total or 0,
            "limit": limit,
            "offset": offset,
            "data": [
                {
                    "id": u.openpath_id,
                    "name": u.full_name,
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "email": u.email,
                    "status": u.status,
                    "access_count": user_access_counts.get(u.openpath_id, 0)
                }
                for u in users
            ]
        }


@router.get("/users/{user_id}")
async def get_user_detail(user_id: str):
    """Get detailed info for a single user including recent activity."""
    async with async_session() as session:
        # Get user
        result = await session.execute(
            select(User).where(User.openpath_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return {"error": "User not found"}
        
        # Get recent access logs - use stored door_name
        logs_result = await session.execute(
            select(AccessLog)
            .where(AccessLog.user_openpath_id == user_id)
            .order_by(desc(AccessLog.timestamp))
            .limit(50)
        )
        logs = logs_result.scalars().all()
        
        # Get access count stats
        total_accesses = await session.scalar(
            select(func.count(AccessLog.id)).where(AccessLog.user_openpath_id == user_id)
        )
        
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_accesses = await session.scalar(
            select(func.count(AccessLog.id)).where(
                AccessLog.user_openpath_id == user_id,
                AccessLog.timestamp >= month_start
            )
        )
        
        # Most used doors for this user - use door_name from access logs
        doors_result = await session.execute(
            select(AccessLog.door_name, func.count(AccessLog.id).label("count"))
            .where(AccessLog.user_openpath_id == user_id, AccessLog.door_name.isnot(None))
            .group_by(AccessLog.door_name)
            .order_by(desc("count"))
            .limit(5)
        )
        top_doors = doors_result.all()
        
        return {
            "user": {
                "id": user.openpath_id,
                "name": user.full_name,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "status": user.status
            },
            "stats": {
                "total_accesses": total_accesses or 0,
                "month_accesses": month_accesses or 0,
                "top_doors": [{"name": d[0], "count": d[1]} for d in top_doors]
            },
            "recent_activity": [
                {
                    "id": log.id,
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                    "event_type": log.event_type,
                    "credential_type": log.credential_type,
                    "door_name": log.door_name or "Unknown"
                }
                for log in logs
            ]
        }


@router.get("/doors")
async def get_doors(
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = None
):
    """Get unique doors from access logs with usage stats."""
    async with async_session() as session:
        # Get unique doors from access logs with counts
        query = (
            select(
                AccessLog.door_name,
                func.count(AccessLog.id).label("total_accesses"),
                func.max(AccessLog.timestamp).label("last_access")
            )
            .where(AccessLog.door_name.isnot(None), AccessLog.door_name != "")
        )
        
        if search:
            query = query.where(AccessLog.door_name.ilike(f"%{search}%"))
        
        query = (
            query
            .group_by(AccessLog.door_name)
            .order_by(desc("total_accesses"))
        )
        
        # Get total count of unique doors
        count_query = (
            select(func.count(func.distinct(AccessLog.door_name)))
            .where(AccessLog.door_name.isnot(None), AccessLog.door_name != "")
        )
        if search:
            count_query = count_query.where(AccessLog.door_name.ilike(f"%{search}%"))
        total = await session.scalar(count_query)
        
        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        rows = result.all()
        
        return {
            "total": total or 0,
            "limit": limit,
            "offset": offset,
            "data": [
                {
                    "name": row[0],
                    "total_accesses": row[1] or 0,
                    "last_access": row[2].isoformat() if row[2] else None
                }
                for row in rows
            ]
        }


def get_date_range_filter(days: Optional[int], start_date: Optional[str], end_date: Optional[str]):
    """Helper to get date range for chart queries."""
    if start_date:
        try:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except:
            start = datetime.utcnow() - timedelta(days=days or 30)
    else:
        start = datetime.utcnow() - timedelta(days=days or 30)
    
    if end_date:
        try:
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except:
            end = datetime.utcnow()
    else:
        end = datetime.utcnow()
    
    return start, end


@router.get("/charts/hourly")
async def get_hourly_distribution(
    days: int = Query(default=7, le=365),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tz_offset: int = Query(default=0, description="Timezone offset from UTC in minutes (e.g., -480 for PST)")
):
    """Get access distribution by hour of day, adjusted for local timezone."""
    async with async_session() as session:
        start, end = get_date_range_filter(days, start_date, end_date)
        
        # Calculate offset in hours and minutes for SQLite
        # tz_offset is in minutes, negative = behind UTC (e.g., -480 for PST/PDT)
        # We need to ADD the offset to UTC to get local time (offset is already signed correctly)
        offset_hours = -tz_offset // 60  # Negate because JS gives opposite sign
        
        # SQLite datetime adjustment: add offset to convert UTC to local
        offset_str = f"{offset_hours:+d} hours"
        
        result = await session.execute(
            select(
                func.strftime('%H', func.datetime(AccessLog.timestamp, offset_str)).label("hour"),
                func.count(AccessLog.id).label("count")
            )
            .where(AccessLog.timestamp >= start, AccessLog.timestamp <= end)
            .group_by("hour")
            .order_by("hour")
        )
        rows = result.all()
        
        # Create full 24-hour distribution
        hourly = {str(i).zfill(2): 0 for i in range(24)}
        for hour, count in rows:
            if hour:
                hourly[hour] = count
        
        return {
            "labels": list(hourly.keys()),
            "data": list(hourly.values())
        }


@router.get("/charts/daily")
async def get_daily_distribution(
    days: int = Query(default=30, le=365),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tz_offset: int = Query(default=0, description="Timezone offset from UTC in minutes (e.g., -480 for PST)")
):
    """Get access counts by day, adjusted for local timezone."""
    async with async_session() as session:
        start, end = get_date_range_filter(days, start_date, end_date)
        
        # Calculate offset in hours for SQLite
        # tz_offset is in minutes, negative = behind UTC (e.g., -480 for PST)
        # We need to ADD the offset to UTC to get local time (offset is already signed correctly)
        offset_hours = -tz_offset // 60  # Negate because JS gives opposite sign
        
        # SQLite datetime adjustment: add offset to convert UTC to local
        offset_str = f"{offset_hours:+d} hours"
        
        result = await session.execute(
            select(
                func.date(func.datetime(AccessLog.timestamp, offset_str)).label("date"),
                func.count(AccessLog.id).label("count")
            )
            .where(AccessLog.timestamp >= start, AccessLog.timestamp <= end)
            .group_by("date")
            .order_by("date")
        )
        rows = result.all()
        
        return {
            "labels": [str(row[0]) for row in rows],
            "data": [row[1] for row in rows]
        }


@router.get("/charts/by-door")
async def get_access_by_door(
    days: int = Query(default=30, le=365),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 10
):
    """Get access counts by door."""
    async with async_session() as session:
        start, end = get_date_range_filter(days, start_date, end_date)
        
        result = await session.execute(
            select(AccessLog.door_name, func.count(AccessLog.id).label("count"))
            .where(AccessLog.timestamp >= start, AccessLog.timestamp <= end, AccessLog.door_name.isnot(None))
            .group_by(AccessLog.door_name)
            .order_by(desc("count"))
            .limit(limit)
        )
        rows = result.all()
        
        return {
            "labels": [row[0] for row in rows],
            "data": [row[1] for row in rows]
        }


@router.get("/charts/by-user")
async def get_access_by_user(
    days: int = Query(default=30, le=365),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 10
):
    """Get access counts by user (top users)."""
    async with async_session() as session:
        start, end = get_date_range_filter(days, start_date, end_date)
        
        result = await session.execute(
            select(AccessLog.user_name, func.count(AccessLog.id).label("count"))
            .where(AccessLog.timestamp >= start, AccessLog.timestamp <= end, AccessLog.user_name.isnot(None))
            .group_by(AccessLog.user_name)
            .order_by(desc("count"))
            .limit(limit)
        )
        rows = result.all()
        
        return {
            "labels": [row[0] or "Unknown" for row in rows],
            "data": [row[1] for row in rows]
        }


@router.get("/charts/weekday")
async def get_weekday_distribution(
    days: int = Query(default=30, le=365),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tz_offset: int = Query(default=0, description="Timezone offset from UTC in minutes (e.g., -480 for PST)")
):
    """Get access distribution by day of week, adjusted for local timezone."""
    async with async_session() as session:
        start, end = get_date_range_filter(days, start_date, end_date)
        
        # Calculate offset in hours for SQLite
        offset_hours = -tz_offset // 60  # Negate because JS gives opposite sign
        offset_str = f"{offset_hours:+d} hours"
        
        result = await session.execute(
            select(
                func.strftime('%w', func.datetime(AccessLog.timestamp, offset_str)).label("weekday"),
                func.count(AccessLog.id).label("count")
            )
            .where(AccessLog.timestamp >= start, AccessLog.timestamp <= end)
            .group_by("weekday")
            .order_by("weekday")
        )
        rows = result.all()
        
        # Map to day names
        day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        weekday_data = {str(i): 0 for i in range(7)}
        for weekday, count in rows:
            if weekday:
                weekday_data[weekday] = count
        
        return {
            "labels": day_names,
            "data": [weekday_data[str(i)] for i in range(7)]
        }
