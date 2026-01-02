from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, Union
from app.api.v1 import phone_configs
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


class CreateAgentSchema(BaseModel):
    tenant_id: Union[int, str]
    name: str
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class AttachToolSchema(BaseModel):
    agent_id: str  # Convex ID is string
    tool_name: str
    tool_config: Dict[str, Any]


class BindNumberSchema(BaseModel):
    phone_number: str
    agent_id: str  # Convex ID is string
    tenant_id: Optional[Union[str, int]] = None


@router.post("/agents/create")
async def create_agent(payload: CreateAgentSchema):
    from app.core.convex_client import get_convex_client
    import json
    client = get_convex_client()
    
    # Resolve tenant slug to ID
    tenant_id = payload.tenant_id
    if isinstance(payload.tenant_id, str):
        # We assume it's a slug, but it could be an ID if passed as string.
        # Try to fetch by slug
        t = await client.query("organizations:getBySlug", {"slug": payload.tenant_id})
        if not t:
            # If not found by slug, maybe it is an ID? 
            # Convex IDs are strings. But user might pass integer? MVP assumption: it's a slug.
            # If it's a legacy int ID, we might fail.
            raise HTTPException(status_code=404, detail=f"Tenant not found: {payload.tenant_id}")
        tenant_id = t["_id"]
    
    # Create agent
    config_str = json.dumps(payload.config) if payload.config else "{}"
    agent_id = await client.mutation("agents:create", {
        "organizationId": str(tenant_id),
        "name": payload.name,
        "role": payload.role,
        "systemPrompt": payload.systemPrompt if hasattr(payload, 'systemPrompt') else payload.system_prompt, # Handling pydantic field alias issues if any
        "config": config_str
    })
    return {"agent": {"id": agent_id, "name": payload.name}}


@router.post("/agents/attach_tool")
async def attach_tool(payload: AttachToolSchema):
    from app.core.convex_client import get_convex_client
    import json
    client = get_convex_client()
    
    # Get agent config
    # We added agents:get
    agent = await client.query("agents:get", {"id": payload.agent_id}) # payload.agent_id should be string ID now
    # If payload.agent_id is int (legacy), this will fail. We rely on new IDs being strings.
    
    if not agent:
         raise HTTPException(status_code=404, detail="Agent not found")
         
    current_config = json.loads(agent.get("config") or "{}")
    tools = current_config.get("tools", {})
    tools[payload.tool_name] = payload.tool_config
    current_config["tools"] = tools
    
    await client.mutation("agents:updateConfig", {
        "id": agent["_id"],
        "config": json.dumps(current_config)
    })
    
    return {"agent_id": agent["_id"], "tools": tools}


@router.post("/agents/bind_number")
async def bind_number(payload: BindNumberSchema):
    from app.core.convex_client import get_convex_client
    client = get_convex_client()
    
    # Update phone config with agentId
    # using phoneConfigs:update which takes phoneNumber
    try:
        await client.mutation("phoneConfigs:update", {
            "phoneNumber": payload.phone_number,
            "agentId": str(payload.agent_id)
        })
        return {"phone_number": payload.phone_number, "agent_id": payload.agent_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/agents/list/{tenant_id}")
async def list_agents(tenant_id: str): # tenant_id is organizationId (slug or ID)
    from app.core.convex_client import get_convex_client
    import json
    client = get_convex_client()
    
    # If tenant_id looks like a slug (no ID format), try resolve?
    # Or just pass to listByOrganization.
    # We should probably resolve slug if passed.
    # naive check: if it has spaces or is short, it's a slug?
    # better: try get by slug, if null, assume ID.
    
    org = await client.query("organizations:getBySlug", {"slug": tenant_id})
    target_id = org["_id"] if org else tenant_id
    
    agents = await client.query("agents:listByOrganization", {"organizationId": str(target_id)})
    
    return {"agents": [ 
        {
            "id": a["_id"], 
            "name": a["name"], 
            "config": json.loads(a["config"] or "{}")
        } for a in (agents or []) 
    ]}
