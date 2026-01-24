"""
HTTP client for the OpenPath API.

Handles authentication, token management, and paginated data fetching
for users, doors (entries), and access activity logs.

The client uses OAuth2 password grant for authentication and automatically
refreshes tokens before they expire.
"""

import httpx
import logging
from typing import Optional
from datetime import datetime, timedelta

from config import get_settings

logger = logging.getLogger(__name__)


class OpenPathClient:
    """
    Async HTTP client for OpenPath API interactions.
    
    Manages authentication tokens and provides methods to fetch
    all relevant data types with automatic pagination handling.
    
    Usage:
        client = OpenPathClient()
        try:
            users = await client.get_all_users()
            entries = await client.get_all_entries()
            activity = await client.get_all_activity()
        finally:
            await client.close()
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.openpath_base_url
        self.token: Optional[str] = None
        self.token_expires: Optional[datetime] = None
        self.org_id: Optional[str] = self.settings.openpath_org_id or None
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client instance."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def close(self):
        """
        Close the HTTP client and release resources.
        
        Must be called when finished using the client to prevent
        connection leaks.
        """
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def authenticate(self) -> bool:
        """
        Authenticate with the OpenPath API.
        
        Uses email/password credentials to obtain an OAuth2 bearer token.
        The organization ID is auto-detected from the token response if
        not explicitly configured.
        
        Returns:
            True if authentication succeeded, False otherwise
        """
        client = await self._get_client()
        
        try:
            response = await client.post(
                f"{self.base_url}/auth/login",
                json={
                    "email": self.settings.openpath_username,
                    "password": self.settings.openpath_password
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract token from nested response structure
            self.token = data.get("data", {}).get("token")
            
            # Set token expiry with buffer (tokens last 1 hour, refresh at 50 min)
            self.token_expires = datetime.utcnow() + timedelta(minutes=50)
            
            # Auto-detect organization ID if not configured
            if not self.org_id:
                token_scopes = data.get("data", {}).get("tokenScopeList", [])
                for scope in token_scopes:
                    org = scope.get("org", {})
                    org_id = org.get("id")
                    if org_id:
                        self.org_id = str(org_id)
                        logger.info(f"Auto-detected org ID: {self.org_id} ({org.get('name', 'Unknown')})")
                        break
            
            logger.info("Successfully authenticated with OpenPath API")
            return True
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Authentication failed: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False
    
    async def _ensure_authenticated(self):
        """
        Ensure a valid authentication token exists.
        
        Automatically re-authenticates if the token is missing or expired.
        
        Raises:
            Exception: If authentication fails
        """
        if not self.token or (self.token_expires and datetime.utcnow() >= self.token_expires):
            success = await self.authenticate()
            if not success:
                raise Exception("Failed to authenticate with OpenPath API")
    
    def _get_headers(self) -> dict:
        """Get HTTP headers with current authentication token."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    async def get_users(self, limit: int = 1000, offset: int = 0) -> list[dict]:
        """
        Fetch a page of users from OpenPath.
        
        Args:
            limit: Maximum number of users to return (API may cap this)
            offset: Number of records to skip for pagination
            
        Returns:
            List of user dictionaries from the API response
        """
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
        """
        Fetch all users with automatic pagination.
        
        Iterates through all pages of users until no more results
        are returned.
        
        Returns:
            Complete list of all user dictionaries
        """
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
        
        logger.info(f"Fetched {len(all_users)} users from OpenPath")
        return all_users
    
    async def get_entries(self, limit: int = 1000, offset: int = 0) -> list[dict]:
        """
        Fetch a page of entries (doors) from OpenPath.
        
        Args:
            limit: Maximum number of entries to return
            offset: Number of records to skip for pagination
            
        Returns:
            List of entry dictionaries from the API response
        """
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
        """
        Fetch all entries (doors) with automatic pagination.
        
        Returns:
            Complete list of all entry/door dictionaries
        """
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
        
        logger.info(f"Fetched {len(all_entries)} entries (doors) from OpenPath")
        return all_entries
    
    async def get_activity(self, limit: int = 1000, offset: int = 0) -> list[dict]:
        """
        Fetch a page of access activity from OpenPath.
        
        Activity records include door unlocks, access denials, and other
        access-related events. Results are returned in reverse chronological
        order (most recent first).
        
        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip for pagination
            
        Returns:
            List of activity dictionaries from the API response
        """
        await self._ensure_authenticated()
        client = await self._get_client()
        
        params = {"limit": limit, "offset": offset}
        
        try:
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
        """
        Fetch activity records with pagination up to a maximum count.
        
        Logs progress periodically as records are fetched.
        
        Args:
            max_records: Maximum total records to fetch. Use this to limit
                        sync duration and database size.
                        
        Returns:
            List of activity dictionaries, up to max_records in length
        """
        all_activity = []
        offset = 0
        limit = 1000  # Larger batch size for efficiency
        
        while len(all_activity) < max_records:
            activity = await self.get_activity(limit=limit, offset=offset)
            if not activity:
                break
            all_activity.extend(activity)
            logger.info(f"Fetched {len(all_activity)} activity records so far...")
            if len(activity) < limit:
                break
            offset += limit
        
        logger.info(f"Fetched {len(all_activity)} total activity records from OpenPath")
        return all_activity
    
    async def test_connection(self) -> dict:
        """
        Test the API connection and return status information.
        
        Useful for verifying credentials and connectivity before
        running a full sync.
        
        Returns:
            Dictionary with connection status and details
        """
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
