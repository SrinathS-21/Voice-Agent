from pydantic import BaseModel, Field
from typing import Optional


class OutboundCallRequest(BaseModel):
    from_number: str = Field(..., description="Twilio phone number to place the call from")
    to_number: str = Field(..., description="Destination phone number to call")
    use_twiml_bin: Optional[bool] = Field(False, description="Use TwiML Bin instead of dynamic TwiML")
    twiml_bin_url: Optional[str] = Field(None, description="URL of the TwiML Bin (if use_twiml_bin=True)")


class OutboundCallResponse(BaseModel):
    session_id: str
    websocket_url: str
    status: str
    created_at: str
    expires_at: Optional[str]
    config_summary: dict
    call_sid: Optional[str] = None
    call_placed: bool = False
    message: Optional[str] = None
