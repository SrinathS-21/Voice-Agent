"""
Phone Config API Endpoints
Manages phone number configurations using ConvexDB.
"""
import os
import json
from fastapi import APIRouter, HTTPException, Depends, status, Body
from typing import Optional

from app.schemas.phone_config_schemas import (
    PhoneConfigCreate,
    PhoneConfigUpdate,
    PhoneConfigResponse,
    PhoneConfigList
)
from app.core.convex_client import get_convex_client

router = APIRouter(prefix="/phone-configs", tags=["phone-configs"])

# Feature flag (can remove if fully committed)
# USE_CONVEX = True 


# ============================================
# CONVEX HELPER FUNCTIONS
# ============================================

def _convex_to_response(data: dict) -> PhoneConfigResponse:
    """Convert Convex document to PhoneConfigResponse"""
    config_json = data.get("configJson")
    if isinstance(config_json, str):
        try:
            config_json = json.loads(config_json)
        except json.JSONDecodeError:
            config_json = {}
    
    return PhoneConfigResponse(
        id=hash(data.get("_id", data.get("phoneNumber"))) % 1000000,  # Generate pseudo-ID
        phone_number=data.get("phoneNumber"),
        job_type=data.get("jobType"),
        tenant_id=None,  # Convex uses organizationId string, not tenant_id int
        config_json=config_json
    )


# ============================================
# API ENDPOINTS
# ============================================

@router.post("/", response_model=PhoneConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_phone_config(payload: PhoneConfigCreate):
    """Create a new phone configuration"""
    client = get_convex_client()
    try:
        # Convert config_json to string for Convex
        config_str = json.dumps(payload.config_json) if payload.config_json else "{}"
        
        result = await client.mutation("phoneConfigs:create", {
            "phoneNumber": payload.phone_number,
            "organizationId": str(getattr(payload, 'tenant_id', None) or "default"),
            "jobType": payload.job_type,
            "configJson": config_str,
        })
        
        return PhoneConfigResponse(
            id=hash(result.get("_id", payload.phone_number)) % 1000000,
            phone_number=payload.phone_number,
            job_type=payload.job_type,
            tenant_id=getattr(payload, 'tenant_id', None),
            config_json=payload.config_json
        )
    except Exception as e:
        if "already configured" in str(e).lower():
            raise HTTPException(status_code=400, detail="Phone number already configured")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{phone_number}", response_model=PhoneConfigResponse)
async def get_phone_config(phone_number: str):
    """Get phone configuration by phone number"""
    client = get_convex_client()
    result = await client.query("phoneConfigs:getByPhoneNumber", {
        "phoneNumber": phone_number
    })
    if not result:
        raise HTTPException(status_code=404, detail="Phone config not found")
    return _convex_to_response(result)


@router.put("/{phone_number}", response_model=PhoneConfigResponse)
async def update_phone_config(phone_number: str, payload: PhoneConfigUpdate):
    """Update phone configuration"""
    client = get_convex_client()
    
    # Build update args
    args = {"phoneNumber": phone_number}
    if payload.job_type is not None:
        args["jobType"] = payload.job_type
    if payload.config_json is not None:
        args["configJson"] = json.dumps(payload.config_json)
    
    try:
        await client.mutation("phoneConfigs:update", args)
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Phone config not found")
        raise HTTPException(status_code=500, detail=str(e))
    
    # Fetch updated config
    result = await client.query("phoneConfigs:getByPhoneNumber", {
        "phoneNumber": phone_number
    })
    return _convex_to_response(result)


@router.put("/{phone_number}/config", response_model=PhoneConfigResponse)
async def update_phone_config_json(phone_number: str, config_json: dict = Body(...)):
    """Update only the config JSON for a phone number."""
    if not isinstance(config_json, dict):
        raise HTTPException(status_code=400, detail="Config JSON must be an object")
    
    client = get_convex_client()
    try:
        await client.mutation("phoneConfigs:update", {
            "phoneNumber": phone_number,
            "configJson": json.dumps(config_json)
        })
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Phone config not found")
        raise HTTPException(status_code=500, detail=str(e))
    
    result = await client.query("phoneConfigs:getByPhoneNumber", {
        "phoneNumber": phone_number
    })
    return _convex_to_response(result)


@router.delete("/{phone_number}")
async def delete_phone_config(phone_number: str):
    """Delete (deactivate) a phone configuration"""
    client = get_convex_client()
    try:
        await client.mutation("phoneConfigs:deactivate", {
            "phoneNumber": phone_number
        })
        return {"message": "deleted", "phone_number": phone_number}
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Phone config not found")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=PhoneConfigList)
async def list_phone_configs(
    tenant_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0
):
    """List all phone configurations"""
    client = get_convex_client()
    
    if tenant_id:
        result = await client.query("phoneConfigs:listByOrganization", {
            "organizationId": str(tenant_id)
        })
    else:
        result = await client.query("phoneConfigs:listAll", {})
    
    items = [_convex_to_response(item) for item in (result or [])]
    # Apply pagination
    paginated = items[offset:offset + limit]
    return PhoneConfigList(total=len(items), items=paginated)
