"""
Function Generator Service
Dynamically generates function schemas based on domain and uploaded data.
"""

import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.core.logging import get_logger
from app.core.convex_client import get_convex_client
from app.domains.registry import (
    DomainRegistry,
    DomainConfig,
    FunctionTemplate,
    DomainType
)

logger = get_logger(__name__)


class FunctionGeneratorService:
    """
    Service for generating and managing dynamic function schemas.
    Creates functions based on domain templates and customizes based on data.
    """
    
    def __init__(self):
        self.convex = get_convex_client()
        self.registry = DomainRegistry()
    
    async def generate_functions_for_organization(
        self,
        organization_id: str,
        domain_type: str,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate function schemas for an organization based on domain.
        
        Args:
            organization_id: Organization ID
            domain_type: Business domain type
            custom_config: Optional custom configuration overrides
            
        Returns:
            List of created function schemas
        """
        domain = self.registry.get_domain(domain_type)
        if not domain:
            logger.error("Unknown domain type", domain_type=domain_type)
            raise ValueError(f"Unknown domain type: {domain_type}")
        
        created_functions = []
        
        for template in domain.default_functions:
            try:
                # Apply any custom config overrides
                handler_config = template.handler_config.copy()
                if custom_config and template.name in custom_config:
                    handler_config.update(custom_config[template.name])
                
                # Create function schema
                function_schema = await self.create_function_schema(
                    organization_id=organization_id,
                    domain=domain_type,
                    function_name=template.name,
                    description=template.description,
                    parameters=template.parameters,
                    handler_type=template.handler_type,
                    handler_config=handler_config
                )
                
                created_functions.append(function_schema)
                
            except Exception as e:
                logger.error(
                    "Failed to create function",
                    function_name=template.name,
                    error=str(e)
                )
        
        logger.info(
            "Generated functions for organization",
            organization_id=organization_id,
            domain=domain_type,
            count=len(created_functions)
        )
        
        return created_functions
    
    async def create_function_schema(
        self,
        organization_id: str,
        domain: str,
        function_name: str,
        description: str,
        parameters: Dict[str, Any],
        handler_type: str,
        handler_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a single function schema in the database.
        
        Args:
            organization_id: Organization ID
            domain: Domain type
            function_name: Name of the function
            description: Function description
            parameters: JSON schema for parameters
            handler_type: Type of handler (vector_search, webhook, etc.)
            handler_config: Handler-specific configuration
            
        Returns:
            Created function schema
        """
        now = int(datetime.utcnow().timestamp() * 1000)
        
        schema_data = {
            "organizationId": organization_id,
            "domain": domain,
            "functionName": function_name,
            "description": description,
            "parameters": json.dumps(parameters),
            "handlerType": handler_type,
            "handlerConfig": json.dumps(handler_config),
            "isActive": True,
            "createdAt": now,
            "updatedAt": now
        }
        
        # Check if function already exists
        existing = await self.get_function_schema(organization_id, function_name)
        
        if existing:
            # Update existing
            result = await self.convex.mutation(
                "functionSchemas:update",
                {
                    "id": existing["_id"],
                    "description": description,
                    "parameters": json.dumps(parameters),
                    "handlerType": handler_type,
                    "handlerConfig": json.dumps(handler_config),
                    "updatedAt": now
                }
            )
            logger.debug("Updated existing function schema", function_name=function_name)
        else:
            # Create new
            result = await self.convex.mutation(
                "functionSchemas:create",
                schema_data
            )
            logger.debug("Created new function schema", function_name=function_name)
        
        return schema_data
    
    async def get_function_schema(
        self,
        organization_id: str,
        function_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get a function schema by organization and name"""
        try:
            result = await self.convex.query(
                "functionSchemas:getByName",
                {
                    "organizationId": organization_id,
                    "functionName": function_name
                }
            )
            return result
        except Exception:
            return None
    
    async def get_organization_functions(
        self,
        organization_id: str,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get all function schemas for an organization.
        
        Args:
            organization_id: Organization ID
            active_only: Only return active functions
            
        Returns:
            List of function schemas
        """
        result = await self.convex.query(
            "functionSchemas:getByOrganization",
            {"organizationId": organization_id}
        )
        
        if active_only:
            result = [f for f in result if f.get("isActive", True)]
        
        return result
    
    async def get_functions_as_tools(
        self,
        organization_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get functions formatted for LLM tool/function calling.
        
        Args:
            organization_id: Organization ID
            
        Returns:
            List of function definitions for LLM
        """
        functions = await self.get_organization_functions(organization_id)
        
        tools = []
        for func in functions:
            try:
                parameters = json.loads(func.get("parameters", "{}"))
            except json.JSONDecodeError:
                parameters = {"type": "object", "properties": {}}
            
            tools.append({
                "name": func["functionName"],
                "description": func["description"],
                "parameters": parameters
            })
        
        return tools
    
    async def update_function_schema(
        self,
        organization_id: str,
        function_name: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update a function schema.
        
        Args:
            organization_id: Organization ID
            function_name: Name of the function to update
            updates: Fields to update
            
        Returns:
            Updated function schema or None if not found
        """
        existing = await self.get_function_schema(organization_id, function_name)
        if not existing:
            return None
        
        now = int(datetime.utcnow().timestamp() * 1000)
        
        # Prepare update data
        update_data = {"id": existing["_id"], "updatedAt": now}
        
        if "description" in updates:
            update_data["description"] = updates["description"]
        if "parameters" in updates:
            update_data["parameters"] = json.dumps(updates["parameters"])
        if "handlerConfig" in updates:
            update_data["handlerConfig"] = json.dumps(updates["handlerConfig"])
        if "isActive" in updates:
            update_data["isActive"] = updates["isActive"]
        
        await self.convex.mutation("functionSchemas:update", update_data)
        
        return await self.get_function_schema(organization_id, function_name)
    
    async def delete_function_schema(
        self,
        organization_id: str,
        function_name: str
    ) -> bool:
        """
        Delete a function schema.
        
        Args:
            organization_id: Organization ID
            function_name: Name of the function to delete
            
        Returns:
            True if deleted, False if not found
        """
        existing = await self.get_function_schema(organization_id, function_name)
        if not existing:
            return False
        
        await self.convex.mutation(
            "functionSchemas:remove",
            {"id": existing["_id"]}
        )
        
        logger.info(
            "Deleted function schema",
            organization_id=organization_id,
            function_name=function_name
        )
        
        return True
    
    async def deactivate_organization_functions(
        self,
        organization_id: str
    ) -> int:
        """
        Deactivate all functions for an organization.
        
        Args:
            organization_id: Organization ID
            
        Returns:
            Number of functions deactivated
        """
        functions = await self.get_organization_functions(
            organization_id, 
            active_only=True
        )
        
        count = 0
        for func in functions:
            await self.update_function_schema(
                organization_id,
                func["functionName"],
                {"isActive": False}
            )
            count += 1
        
        logger.info(
            "Deactivated organization functions",
            organization_id=organization_id,
            count=count
        )
        
        return count
    
    def generate_handler_for_function(
        self,
        function_schema: Dict[str, Any]
    ) -> callable:
        """
        Generate a callable handler for a function schema.
        
        Args:
            function_schema: Function schema from database
            
        Returns:
            Callable handler function
        """
        handler_type = function_schema.get("handlerType", "static")
        
        try:
            handler_config = json.loads(
                function_schema.get("handlerConfig", "{}")
            )
        except json.JSONDecodeError:
            handler_config = {}
        
        if handler_type == "vector_search":
            return self._create_vector_search_handler(
                function_schema["organizationId"],
                handler_config
            )
        elif handler_type == "static":
            return self._create_static_handler(handler_config)
        elif handler_type == "webhook":
            return self._create_webhook_handler(handler_config)
        elif handler_type == "convex_query":
            return self._create_convex_query_handler(handler_config)
        else:
            logger.warning(
                "Unknown handler type",
                handler_type=handler_type,
                function_name=function_schema.get("functionName")
            )
            return self._create_fallback_handler()
    
    def _create_vector_search_handler(
        self,
        organization_id: str,
        config: Dict[str, Any]
    ) -> callable:
        """Create a vector search handler"""
        source_type = config.get("source_type", "knowledge")
        limit = config.get("limit", 5)
        
        async def handler(**kwargs):
            from app.services.knowledge_base_service import KnowledgeBaseService
            
            kb_service = KnowledgeBaseService()
            query = kwargs.get("query", "")
            
            results = await kb_service.semantic_search(
                organization_id=organization_id,
                query=query,
                source_type=source_type,
                limit=limit
            )
            
            return {
                "results": results,
                "count": len(results),
                "source": source_type
            }
        
        return handler
    
    def _create_static_handler(self, config: Dict[str, Any]) -> callable:
        """Create a static response handler"""
        action = config.get("action", "unknown")
        
        async def handler(**kwargs):
            if action == "end_call":
                return {
                    "action": "end_call",
                    "message": "Call ended",
                    "reason": kwargs.get("reason", "User request")
                }
            elif action == "transfer_call":
                return {
                    "action": "transfer_call",
                    "target": config.get("target", "operator"),
                    "reason": kwargs.get("reason", "Transfer requested")
                }
            else:
                return {"action": action, "config": config, "params": kwargs}
        
        return handler
    
    def _create_webhook_handler(self, config: Dict[str, Any]) -> callable:
        """Create a webhook handler (placeholder for external integrations)"""
        action = config.get("action", "unknown")
        
        async def handler(**kwargs):
            # In production, this would make HTTP calls to external services
            # For now, return a placeholder response
            logger.info(
                "Webhook handler called",
                action=action,
                params=kwargs
            )
            
            return {
                "action": action,
                "status": "pending",
                "message": f"Action '{action}' queued for processing",
                "params": kwargs
            }
        
        return handler
    
    def _create_convex_query_handler(self, config: Dict[str, Any]) -> callable:
        """Create a Convex query handler"""
        table = config.get("table")
        query_type = config.get("query_type", "get")
        
        async def handler(**kwargs):
            if not table:
                return {"error": "No table configured"}
            
            # Execute Convex query
            result = await self.convex.query(
                f"{table}:{query_type}",
                kwargs
            )
            
            return result
        
        return handler
    
    def _create_fallback_handler(self) -> callable:
        """Create a fallback handler for unknown types"""
        async def handler(**kwargs):
            return {
                "error": "Handler not configured",
                "params": kwargs
            }
        
        return handler


# Singleton instance
_service: Optional[FunctionGeneratorService] = None


def get_function_generator_service() -> FunctionGeneratorService:
    """Get the function generator service singleton"""
    global _service
    if _service is None:
        _service = FunctionGeneratorService()
    return _service
