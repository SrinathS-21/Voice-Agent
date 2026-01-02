from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Optional
import json
from app.services.twilio_service import TwilioProvisioner
from app.core.logging import get_logger
from app.core.convex_client import get_convex_client

logger = get_logger(__name__)
router = APIRouter(prefix="/tenants", tags=["tenants"])


class TenantCreateSchema(BaseModel):
    slug: str
    name: str
    job_type: str = "general"
    voice_url: str | None = None


@router.post("/provision")
async def provision_tenant(payload: TenantCreateSchema):
    try:
        prov = TwilioProvisioner()
        res = await prov.provision_for_tenant(
            slug=payload.slug,
            client_name=payload.name,
            job_type=payload.job_type,
            voice_url=payload.voice_url
        )
        return res
    except Exception as e:
        logger.error("Provisioning failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[dict])
async def list_tenants():
    client = get_convex_client()
    try:
        # Check if we can list organizations. 
        # Using a known query or just getting default if list capability isn't there yet.
        # Ideally we added organizations:list to Convex. 
        # Since we didn't add a general list query, we will return the default one.
        items = await client.query("organizations:getBySlug", {"slug": "default"})
        if items:
            return [{"id": 1, "slug": items.get("slug"), "name": items.get("name"), "status": "active"}]
        return []
    except Exception as e:
        logger.error(f"Error listing tenants: {e}")
        return []


@router.get("/{slug}/numbers")
async def tenant_numbers(slug: str):
    client = get_convex_client()
    
    # 1. Get org by slug
    org = await client.query("organizations:getBySlug", {"slug": slug})
    if not org:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    org_id = org.get("_id")
    if not org_id:
         raise HTTPException(status_code=404, detail="Tenant ID not found")

    # 2. List phone configs for this org
    target_org_id = slug if slug == "default" else str(org_id)
    
    configs = await client.query("phoneConfigs:listByOrganization", {"organizationId": target_org_id})
    
    return [
        {
            "id": c.get("_id"), 
            "phone_number": c.get("phoneNumber"), 
            "job_type": c.get("jobType"), 
            "config": json.loads(c.get("configJson", "{}")) if isinstance(c.get("configJson"), str) else c.get("configJson"),
            "created_at": None 
        }
        for c in (configs or [])
    ]
