from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class PhoneConfigCreate(BaseModel):
    phone_number: str = Field(..., description="Twilio phone number in E.164 format")
    job_type: str = Field(..., description="Job type like 'restaurant' or 'pharmacy'")
    tenant_id: Optional[int] = Field(None, description="Optional tenant id to associate the number with")
    config_json: Optional[Dict[str, Any]] = Field(None, description="Configuration payload for the number")


class PhoneConfigUpdate(BaseModel):
    job_type: Optional[str]
    config_json: Optional[Dict[str, Any]]


class PhoneConfigJSONUpdate(BaseModel):
    """Update only the config JSON for a phone number"""
    config_json: Dict[str, Any]


class PhoneConfigResponse(BaseModel):
    id: int
    phone_number: str
    job_type: str
    tenant_id: Optional[int]
    config_json: Optional[Dict[str, Any]]


class PhoneConfigList(BaseModel):
    total: int
    items: List[PhoneConfigResponse]
