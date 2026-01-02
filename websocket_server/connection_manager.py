"""
WebSocket Connection Manager
Manages WebSocket connections and sessions with dynamic function loading.
Optimized for low-latency voice agent operations.
"""

from typing import Dict, Optional, Callable
import websockets
import httpx
import asyncio

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import SessionNotFoundException
from app.utils.function_loader import FunctionLoader
from app.functions.dynamic_functions import get_dynamic_function_map

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and session data with optimized function loading"""
    
    def __init__(self):
        self.session_configs: Dict[str, Dict] = {}
        self.session_functions: Dict[str, Dict[str, Callable]] = {}
        self.session_org_map: Dict[str, str] = {}  # session_id -> organization_id
        self.active_connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self._function_loader = FunctionLoader()
    
    async def fetch_session_config(self, session_id: str) -> Optional[Dict]:
        """
        Fetch configuration for a session from API server
        
        Args:
            session_id: Session ID
            
        Returns:
            Session configuration or None if not found
        """
        # Use API_CLIENT_HOST for connections from WebSocket server to API server
        api_host = getattr(settings, 'API_CLIENT_HOST', 'localhost')
        api_url = f"http://{api_host}:{settings.API_PORT}/api/v1/sessions/{session_id}/config"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(api_url)
                
                if response.status_code == 200:
                    config = response.json()
                    self.session_configs[session_id] = config
                    logger.info("Fetched session config", session_id=session_id)
                    return config
                elif response.status_code == 404:
                    logger.warning("Session not found", session_id=session_id)
                    return None
                else:
                    logger.error(
                        "Failed to fetch session config",
                        session_id=session_id,
                        status=response.status_code
                    )
                    return None
                    
        except Exception as e:
            logger.error("Error fetching session config", session_id=session_id, error=str(e))
            return None
    
    def load_session_functions(
        self, 
        session_id: str, 
        module_path: Optional[str] = None,
        organization_id: Optional[str] = None
    ):
        """
        Load functions for a session (synchronous wrapper).
        For new code, prefer load_session_functions_async.
        
        Args:
            session_id: Session ID
            module_path: Optional path to custom function module (legacy)
            organization_id: Organization ID for dynamic function loading
        """
        if organization_id:
            # Use new dynamic functions bound to organization
            self.session_org_map[session_id] = organization_id
            functions = get_dynamic_function_map(organization_id)
            self.session_functions[session_id] = functions
            logger.info(
                "Loaded dynamic functions",
                session_id=session_id,
                organization_id=organization_id,
                count=len(functions),
                functions=list(functions.keys())
            )
        else:
            # Fallback to legacy module loading
            functions = FunctionLoader.load_from_module(module_path)
            self.session_functions[session_id] = functions
            logger.info(
                "Loaded legacy functions",
                session_id=session_id,
                count=len(functions),
                functions=list(functions.keys())
            )
    
    async def load_session_functions_async(
        self,
        session_id: str,
        organization_id: str,
        use_convex: bool = True
    ):
        """
        Asynchronously load functions for a session from ConvexDB.
        This is the preferred method for production use.
        
        Args:
            session_id: Session ID
            organization_id: Organization ID
            use_convex: Whether to try loading from ConvexDB first
        """
        self.session_org_map[session_id] = organization_id
        
        if use_convex:
            try:
                # Try loading custom functions from ConvexDB
                functions = await self._function_loader.load_from_convex(
                    organization_id=organization_id,
                    use_cache=True
                )
                
                if functions:
                    self.session_functions[session_id] = functions
                    logger.info(
                        "Loaded ConvexDB functions",
                        session_id=session_id,
                        organization_id=organization_id,
                        count=len(functions)
                    )
                    return
            except Exception as e:
                logger.warning(
                    "ConvexDB function loading failed, using dynamic functions",
                    error=str(e)
                )
        
        # Use dynamic functions (knowledge-base-backed)
        functions = get_dynamic_function_map(organization_id)
        self.session_functions[session_id] = functions
        logger.info(
            "Loaded dynamic functions",
            session_id=session_id,
            organization_id=organization_id,
            count=len(functions)
        )
    
    def get_config(self, session_id: str) -> Optional[Dict]:
        """Get cached configuration for a session"""
        return self.session_configs.get(session_id)
    
    def get_functions(self, session_id: str) -> Dict[str, Callable]:
        """Get functions for a session"""
        return self.session_functions.get(session_id, {})
    
    def get_organization_id(self, session_id: str) -> Optional[str]:
        """Get organization ID for a session"""
        return self.session_org_map.get(session_id)
    
    def register_connection(self, session_id: str, websocket: websockets.WebSocketServerProtocol):
        """Register an active WebSocket connection"""
        self.active_connections[session_id] = websocket
        logger.info("WebSocket connection registered", session_id=session_id)
    
    def unregister_connection(self, session_id: str):
        """Unregister a WebSocket connection"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info("WebSocket connection unregistered", session_id=session_id)
    
    def cleanup_session(self, session_id: str):
        """Clean up all session data"""
        self.session_configs.pop(session_id, None)
        self.session_functions.pop(session_id, None)
        self.session_org_map.pop(session_id, None)
        self.unregister_connection(session_id)
        logger.info("Session cleanup completed", session_id=session_id)


# Singleton instance
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get connection manager singleton"""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager
