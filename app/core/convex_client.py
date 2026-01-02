"""
Convex DB Client - Python bridge for Convex serverless database
Provides async HTTP client to interact with Convex queries and mutations
"""

import os
import json
import httpx
from typing import Any, Dict, Optional, TypeVar, Generic
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ConvexResponse(Generic[T]):
    """Response from Convex API"""
    success: bool
    value: Optional[T] = None
    error: Optional[str] = None


class ConvexClient:
    """
    Async HTTP client for Convex DB
    
    Usage:
        client = ConvexClient()
        
        # Query
        result = await client.query("callSessions:getBySessionId", {"sessionId": "abc123"})
        
        # Mutation
        result = await client.mutation("callSessions:create", {
            "sessionId": "abc123",
            "phoneNumber": "+1234567890",
            ...
        })
    """
    
    def __init__(self, deployment_url: Optional[str] = None):
        self.deployment_url = deployment_url or os.getenv("CONVEX_URL")
        if not self.deployment_url:
            raise ValueError(
                "CONVEX_URL not set. Add CONVEX_URL=https://your-deployment.convex.cloud to .env"
            )
        
        # Remove trailing slash
        self.deployment_url = self.deployment_url.rstrip("/")
        
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.deployment_url,
                timeout=30.0,
                headers={"Content-Type": "application/json"},
            )
        return self._client
    
    async def query(self, function_path: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute a Convex query function
        
        Args:
            function_path: Path to function, e.g., "callSessions:getBySessionId"
            args: Arguments to pass to the function
            
        Returns:
            Query result (typed based on Convex function return)
        """
        client = await self._get_client()
        
        payload = {
            "path": function_path,
            "args": args or {},
            "format": "json",
        }
        
        try:
            response = await client.post("/api/query", json=payload)
            response.raise_for_status()
            
            data = response.json()
            if "status" in data and data["status"] == "error":
                logger.error(f"Convex query error: {data.get('errorMessage', 'Unknown error')}")
                raise Exception(data.get("errorMessage", "Convex query failed"))
            
            return data.get("value")
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Convex HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Convex query failed: {e}")
            raise
    
    async def mutation(self, function_path: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute a Convex mutation function
        
        Args:
            function_path: Path to function, e.g., "callSessions:create"
            args: Arguments to pass to the function
            
        Returns:
            Mutation result
        """
        client = await self._get_client()
        
        payload = {
            "path": function_path,
            "args": args or {},
            "format": "json",
        }
        
        try:
            response = await client.post("/api/mutation", json=payload)
            response.raise_for_status()
            
            data = response.json()
            if "status" in data and data["status"] == "error":
                logger.error(f"Convex mutation error: {data.get('errorMessage', 'Unknown error')}")
                raise Exception(data.get("errorMessage", "Convex mutation failed"))
            
            return data.get("value")
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Convex HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Convex mutation failed: {e}")
            raise
    
    async def action(self, function_path: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute a Convex action function
        
        Actions are used for operations that need side effects or external API calls,
        such as vector search operations.
        
        Args:
            function_path: Path to function, e.g., "rag:search"
            args: Arguments to pass to the function
            
        Returns:
            Action result
        """
        client = await self._get_client()
        
        payload = {
            "path": function_path,
            "args": args or {},
            "format": "json",
        }
        
        try:
            response = await client.post("/api/action", json=payload)
            response.raise_for_status()
            
            data = response.json()
            if "status" in data and data["status"] == "error":
                logger.error(f"Convex action error: {data.get('errorMessage', 'Unknown error')}")
                raise Exception(data.get("errorMessage", "Convex action failed"))
            
            return data.get("value")
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Convex HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Convex action failed: {e}")
            raise
    
    async def close(self):
        """Close the HTTP client"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# Singleton instance
_convex_client: Optional[ConvexClient] = None


def get_convex_client() -> ConvexClient:
    """Get singleton Convex client instance"""
    global _convex_client
    if _convex_client is None:
        _convex_client = ConvexClient()
    return _convex_client


async def close_convex_client():
    """Close the global Convex client"""
    global _convex_client
    if _convex_client is not None:
        await _convex_client.close()
        _convex_client = None
