from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/admin/status")
async def admin_status():
    return {"status": "ok", "message": "Admin API placeholder"}


@router.post("/admin/assign-agent")
async def assign_agent(tenant_slug: str, phone_config_id: int):
    # Placeholder: in future, attach an agent/template to tenant's phone number config
    return {"status": "ok", "tenant": tenant_slug, "phone_config_id": phone_config_id}
