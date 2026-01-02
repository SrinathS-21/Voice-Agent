from fastapi import APIRouter, Form, Response
# from sqlalchemy import select
# from app.core.database import AsyncSessionLocal
# from app.models.database import PhoneNumberConfig
from app.services.session_service import get_session_service
from app.schemas.config_schemas import VoiceAgentConfigSchema
from app.models.session import CallType
from app.session_cache import set_session_cache
from app.core.config import settings
from twilio.twiml.voice_response import VoiceResponse, Connect
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/webhooks/twilio/voice")
async def twilio_voice_webhook(To: str = Form(...), From: str = Form(...), CallSid: str = Form(None)):
    """Handle incoming Twilio call webhook, create session for configured number, and return TwiML.

    Twilio will POST fields like 'To', 'From', and 'CallSid'. We look up `To` (the called Twilio number)
    in our `phone_number_configs` table, create a session using the stored config, cache it, and then
    return TwiML Connect->Stream to route the call to the WebSocket server with that session_id.
    """

    # Debug: log the incoming To value
    logger.info(f"Twilio webhook received To: '{To}' From: '{From}'")

    # Lookup phone number config, and log all numbers in DB for debug
    async with AsyncSessionLocal() as db:
        all_q = select(PhoneNumberConfig.phone_number)
        all_res = await db.execute(all_q)
        all_numbers = [row[0] for row in all_res.fetchall()]
        logger.info(f"All phone numbers in DB: {all_numbers}")

        q = select(PhoneNumberConfig).where(PhoneNumberConfig.phone_number == To)
        res = await db.execute(q)
        config_row = res.scalar_one_or_none()

    if not config_row:
        logger.warning("Incoming call to unconfigured number", to=To, from_=From)
        resp = VoiceResponse()
        resp.say("This phone number is not configured. Goodbye.")
        return Response(content=str(resp), media_type="application/xml")

    # Parse the stored config JSON into our VoiceAgentConfigSchema
    try:
        config_schema = VoiceAgentConfigSchema.parse_obj(config_row.config_json)
    except Exception as e:
        logger.error("Invalid phone config JSON", error=str(e), phone_number=To)
        resp = VoiceResponse()
        resp.say("This phone number is misconfigured. Goodbye.")
        return Response(content=str(resp), media_type="application/xml")

    # Create a session using the SessionService
    service = get_session_service()
    # Include tenant info (if present) so websocket server and logs know tenant context
    tenant_id = getattr(config_row, 'tenant_id', None)
    business_info = {
        "name": config_schema.business_name if hasattr(config_schema, 'business_name') else config_row.config_json.get('business', {}).get('name') if config_row.config_json else None,
        "tenant_id": tenant_id
    }
    session = await service.create_session(config_schema, call_type=CallType.INBOUND, phone_number=To, tenant_id=tenant_id)
    # attach tenant metadata
    session.metadata['tenant_id'] = tenant_id
    if business_info.get('name'):
        session.business_info = business_info

    # Cache the session data so the websocket server can read it instantly
    set_session_cache(session.session_id, {
        "config": session.config,
        "details": {
            "session_id": session.session_id,
            "status": session.status.value,
            "call_type": session.call_type.value if session.call_type else "inbound",
            "phone_number": session.metadata.get("phone_number", "unknown"),
            "business": session.business_info,
            "metadata": session.metadata,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat()
        }
    })

    # Return TwiML to connect the call to the websocket server with this session ID
    ws_url = f"{settings.WEBSOCKET_URL}/voice/{session.session_id}"
    resp = VoiceResponse()
    connect = Connect()
    connect.stream(url=ws_url)
    resp.append(connect)
    logger.info("Incoming call webhook created session and returned TwiML", session_id=session.session_id, to=To)
    return Response(content=str(resp), media_type="application/xml")
