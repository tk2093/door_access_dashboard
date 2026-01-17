import httpx
from typing import Optional
from datetime import datetime, timedelta
import logging

from backend.config import get_settings

logger = logging.getLogger(__name__)


class OpenPathClient:
    """Client for interacting with OpenPath API."""
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.openpath_base_url
        self.token: Optional[str] = None
        self.token_expires: Optional[datetime] = None
        self.org_id: Optional[str] = self.settings.openpath_org_id or None
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def authenticate(self) -> bool:
        """Authenticate with OpenPath API and get access token."""
        client = await self._get_client()
        
        try:
            # OpenPath uses OAuth2 password grant
            response = await client.post(
                f"{self.base_url}/auth/login",
                json={
                    "email": self.settings.openpath_username,
                    "password": self.settings.openpath_password
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # Token is in data.data.token
            self.token = data.get("data", {}).get("token")
            
            # Token typically expires in 1 hour, refresh at 50 minutes
            self.token_expires = datetime.utcnow() + timedelta(minutes=50)
            
            # Get org ID from tokenScopeList[0].org.id
            if not self.org_id:
                token_scopes = data.get("data", {}).get("tokenScopeList", [])
                for scope in token_scopes:
                    org = scope.get("org", {})
                    org_id = org.get("id")
                    if org_id:
                        self.org_id = str(org_id)
                        logger.info(f"Auto-detected org ID: {self.org_id} ({org.get('name', 'Unknown')})")
                        break
            
            logger.info("Successfully authenticated with OpenPath")
            return True
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Authentication failed: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False
    
    async def _ensure_authenticated(self):
        """Ensure we have a valid token."""
        if not self.token or (self.token_expires and datetime.utcnow() >= self.token_expires):
            success = await self.authenticate()
            if not success:
                raise Exception("Failed to authenticate with OpenPath API")
    
    def _get_headers(self) -> dict:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    async def get_users(self, limit: int = 1000, offset: int = 0) -> list[dict]:
        """Fetch users from OpenPath."""
        await self._ensure_authenticated()
        client = await self._get_client()
        
        try:
            response = await client.get(
                f"{self.base_url}/orgs/{self.org_id}/users",
                headers=self._get_headers(),
                params={"limit": limit, "offset": offset}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", []) if isinstance(data, dict) else data
        except Exception as e:
            logger.error(f"Error fetching users: {str(e)}")
            return []
    
    async def get_all_users(self) -> list[dict]:
        """Fetch all users with pagination."""
        all_users = []
        offset = 0
        limit = 100
        
        while True:
            users = await self.get_users(limit=limit, offset=offset)
            if not users:
                break
            all_users.extend(users)
            if len(users) < limit:
                break
            offset += limit
        
        return all_users
    
    async def get_entries(self, limit: int = 1000, offset: int = 0) -> list[dict]:
        """Fetch entries (doors) from OpenPath."""
        await self._ensure_authenticated()
        client = await self._get_client()
        
        try:
            response = await client.get(
                f"{self.base_url}/orgs/{self.org_id}/entries",
                headers=self._get_headers(),
                params={"limit": limit, "offset": offset}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", []) if isinstance(data, dict) else data
        except Exception as e:
            logger.error(f"Error fetching entries: {str(e)}")
            return []
    
    async def get_all_entries(self) -> list[dict]:
        """Fetch all entries (doors) with pagination."""
        all_entries = []
        offset = 0
        limit = 100
        
        while True:
            entries = await self.get_entries(limit=limit, offset=offset)
            if not entries:
                break
            all_entries.extend(entries)
            if len(entries) < limit:
                break
            offset += limit
        
        return all_entries
    
    async def get_activity(
        self, 
        limit: int = 1000,
        offset: int = 0
    ) -> list[dict]:
        """Fetch access activity/events from OpenPath.
        
        Args:
            limit: Max records per request (OpenPath may cap this)
            offset: Pagination offset
        """
        await self._ensure_authenticated()
        client = await self._get_client()
        
        params = {"limit": limit, "offset": offset}
        
        try:
            # Use the reports/activity endpoint
            response = await client.get(
                f"{self.base_url}/orgs/{self.org_id}/reports/activity",
                headers=self._get_headers(),
                params=params
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", []) if isinstance(data, dict) else data
        except Exception as e:
            logger.error(f"Error fetching activity: {str(e)}")
            return []
    
    async def get_all_activity(self, max_records: int = 50000) -> list[dict]:
        """Fetch activity with pagination up to max_records.
        
        Args:
            max_records: Maximum records to fetch (default 50,000 for ~1 year of data)
        """
        all_activity = []
        offset = 0
        limit = 1000  # Increased batch size for faster fetching
        
        while len(all_activity) < max_records:
            activity = await self.get_activity(
                limit=limit,
                offset=offset
            )
            if not activity:
                break
            all_activity.extend(activity)
            logger.info(f"Fetched {len(all_activity)} activity records so far...")
            if len(activity) < limit:
                break
            offset += limit
        
        return all_activity
    
    async def test_connection(self) -> dict:
        """Test API connection and return status."""
        try:
            success = await self.authenticate()
            if success:
                return {
                    "status": "connected",
                    "org_id": self.org_id,
                    "message": "Successfully connected to OpenPath API"
                }
            else:
                return {
                    "status": "failed",
                    "message": "Authentication failed - check credentials"
                }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
