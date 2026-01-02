"""
Function Loader Utility
Dynamically loads function implementations from modules or ConvexDB.
Supports both legacy Python module loading and new dynamic function schemas.
"""

import importlib.util
import json
from typing import Dict, Callable, List, Any, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class FunctionLoader:
    """
    Utility class for loading function modules dynamically.
    Supports loading from:
    1. ConvexDB function schemas (new dynamic approach)
    2. Python modules (legacy/fallback approach)
    """
    
    def __init__(self):
        self._function_cache: Dict[str, Dict[str, Callable]] = {}
        self._schema_cache: Dict[str, List[Dict[str, Any]]] = {}
    
    async def load_from_convex(
        self, 
        organization_id: str,
        use_cache: bool = True
    ) -> Dict[str, Callable]:
        """
        Load function handlers from ConvexDB for an organization.
        
        Args:
            organization_id: Organization ID to load functions for
            use_cache: Whether to use cached functions
            
        Returns:
            Dictionary mapping function names to callable handlers
        """
        # Check cache
        if use_cache and organization_id in self._function_cache:
            logger.debug(
                "Using cached functions",
                organization_id=organization_id,
                count=len(self._function_cache[organization_id])
            )
            return self._function_cache[organization_id]
        
        try:
            from app.services.function_generator_service import (
                get_function_generator_service
            )
            
            generator = get_function_generator_service()
            
            # Get function schemas from database
            schemas = await generator.get_organization_functions(
                organization_id,
                active_only=True
            )
            
            if not schemas:
                logger.info(
                    "No dynamic functions found in ConvexDB",
                    organization_id=organization_id
                )
                # Return empty - dynamic_functions.py will handle knowledge-base queries
                return {}
            
            # Generate handlers for each schema
            functions = {}
            for schema in schemas:
                handler = generator.generate_handler_for_function(schema)
                functions[schema["functionName"]] = handler
            
            # Cache results
            self._function_cache[organization_id] = functions
            self._schema_cache[organization_id] = schemas
            
            logger.info(
                "Loaded dynamic functions from ConvexDB",
                organization_id=organization_id,
                count=len(functions),
                function_names=list(functions.keys())
            )
            
            return functions
            
        except Exception as e:
            logger.error(
                "Failed to load from ConvexDB",
                organization_id=organization_id,
                error=str(e)
            )
            # Return empty - dynamic_functions.py will handle knowledge-base queries
            return {}
    
    def get_function_schemas(
        self,
        organization_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get cached function schemas for an organization.
        Returns empty list if not cached.
        """
        return self._schema_cache.get(organization_id, [])
    
    def get_tools_for_llm(
        self,
        organization_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get function definitions formatted for LLM tool/function calling.
        
        Args:
            organization_id: Organization ID
            
        Returns:
            List of function definitions for LLM
        """
        schemas = self.get_function_schemas(organization_id)
        
        if not schemas:
            # Return legacy function definitions
            return self._get_legacy_tool_definitions()
        
        tools = []
        for schema in schemas:
            try:
                parameters = json.loads(schema.get("parameters", "{}"))
            except json.JSONDecodeError:
                parameters = {"type": "object", "properties": {}}
            
            tools.append({
                "name": schema["functionName"],
                "description": schema["description"],
                "parameters": parameters
            })
        
        return tools
    
    def _get_legacy_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get generic function definitions (used when no custom schemas exist)"""
        return [
            {
                "name": "search_items",
                "description": "Search for items, products, or services by query. Returns matching results from the knowledge base.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query to find items"
                        },
                        "category": {
                            "type": "string",
                            "description": "Optional category to filter results"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_business_info",
                "description": "Get business information like hours, location, contact details, policies",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "info_type": {
                            "type": "string",
                            "description": "Type of info: hours, location, contact, policies, features"
                        }
                    },
                    "required": ["info_type"]
                }
            },
            {
                "name": "place_order",
                "description": "Place an order for the customer",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_name": {
                            "type": "string",
                            "description": "Customer's name for the order"
                        },
                        "items": {
                            "type": "string",
                            "description": "Comma-separated list of items to order"
                        }
                    },
                    "required": ["customer_name", "items"]
                }
            },
            {
                "name": "lookup_order",
                "description": "Look up the status of an existing order",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "The order ID to look up"
                        }
                    },
                    "required": ["order_id"]
                }
            },
            {
                "name": "make_appointment",
                "description": "Schedule an appointment or reservation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_name": {"type": "string"},
                        "date": {"type": "string"},
                        "time": {"type": "string"},
                        "party_size": {"type": "integer"}
                    },
                    "required": ["customer_name", "date", "time"]
                }
            },
            {
                "name": "end_call",
                "description": "End the call when user says goodbye",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string"}
                    }
                }
            }
        ]
    
    def clear_cache(self, organization_id: Optional[str] = None) -> None:
        """
        Clear function cache.
        
        Args:
            organization_id: Specific organization to clear, or None for all
        """
        if organization_id:
            self._function_cache.pop(organization_id, None)
            self._schema_cache.pop(organization_id, None)
            logger.debug("Cleared cache for organization", organization_id=organization_id)
        else:
            self._function_cache.clear()
            self._schema_cache.clear()
            logger.debug("Cleared all function caches")
    
    @staticmethod
    def load_from_module(module_path: str = None) -> Dict[str, Callable]:
        """
        Load functions from a Python module (DEPRECATED - legacy approach).
        
        NOTE: This method is deprecated. Use dynamic functions from 
        app.functions.dynamic_functions.get_dynamic_function_map() instead.
        
        Args:
            module_path: Path to Python module file
            
        Returns:
            Dictionary mapping function names to callable functions
        """
        if not module_path:
            # DEPRECATED: No longer falls back to restaurant_functions.py
            # Use dynamic functions backed by knowledge base instead
            logger.warning(
                "load_from_module called without path - this is deprecated. "
                "Use get_dynamic_function_map() for knowledge-base-backed functions."
            )
            return {}
        
        try:
            # Load custom module dynamically
            spec = importlib.util.spec_from_file_location("custom_functions", module_path)
            if not spec or not spec.loader:
                logger.error("Invalid module path", path=module_path)
                return {}
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            functions = getattr(module, 'FUNCTION_MAP', {})
            logger.info("Loaded custom functions", path=module_path, count=len(functions))
            return functions
            
        except Exception as e:
            logger.error("Error loading functions", path=module_path, error=str(e))
            return {}
    
    @staticmethod
    def validate_functions(functions: Dict[str, Callable]) -> bool:
        """
        Validate that all functions are callable
        
        Args:
            functions: Dictionary of functions to validate
            
        Returns:
            True if all functions are valid
        """
        for name, func in functions.items():
            if not callable(func):
                logger.error("Invalid function", name=name)
                return False
        return True
