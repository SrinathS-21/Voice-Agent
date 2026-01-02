"""
Twilio provisioning service (platform-managed Twilio)
Creates tenants, TwiML Apps, purchases numbers and persists PhoneNumberConfig
"""
import asyncio
from typing import Optional
from twilio.rest import Client as TwilioClient
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TwilioProvisioner:
    def __init__(self, account_sid: Optional[str] = None, auth_token: Optional[str] = None):
        self.account_sid = account_sid or settings.TWILIO_ACCOUNT_SID
        self.auth_token = auth_token or settings.TWILIO_AUTH_TOKEN
        if not self.account_sid or not self.auth_token:
            raise ValueError("Twilio credentials not configured in settings")
        # Twilio client is synchronous; run calls in thread executor when used in async context
        self.client = TwilioClient(self.account_sid, self.auth_token)

    async def create_twiml_app(self, friendly_name: str, voice_url: str) -> str:
        def _create():
            return self.client.applications.create(
                friendly_name=friendly_name,
                voice_url=voice_url
            )
        app = await asyncio.to_thread(_create)
        logger.info("Created TwiML App", sid=app.sid, voice_url=voice_url)
        return app.sid

    async def buy_number(self, country: str = "US") -> (str, str):
        def _buy():
            nums = self.client.available_phone_numbers(country).local.list(limit=1)
            if not nums:
                return None
            purchased = self.client.incoming_phone_numbers.create(
                phone_number=nums[0].phone_number
            )
            return purchased
        purchased = await asyncio.to_thread(_buy)
        if not purchased:
            raise RuntimeError("No available numbers to purchase")
        logger.info("Purchased number", phone_number=purchased.phone_number, sid=purchased.sid)
        return purchased.phone_number, purchased.sid

    async def attach_number_to_app(self, number_sid: str, app_sid: str):
        def _attach():
            return self.client.incoming_phone_numbers(number_sid).update(
                voice_application_sid=app_sid
            )
        updated = await asyncio.to_thread(_attach)
        logger.info("Attached number to TwiML App", number_sid=number_sid, app_sid=app_sid)
        return updated

    async def provision_for_tenant(self, slug: str, client_name: str, job_type: str = "general", voice_url: Optional[str] = None, country: str = "US") -> dict:
        """
        High-level provisioning: create tenant record, create TwiML app, buy number, attach, persist phone config
        Returns dict with tenant and phone info
        """
        # ensure voice_url is provided (public HTTPS endpoint)
        if not voice_url:
            voice_url = getattr(settings, "NGROK_URL", None)
            if voice_url:
                voice_url = f"{voice_url}/api/v1/webhooks/twilio/voice"
        if not voice_url:
            raise ValueError("voice_url is required for provisioning (use NGROK_URL or pass voice_url)")

        from app.core.convex_client import get_convex_client
        import json
        client = get_convex_client()

        # 1. create tenant in DB (Convex)
        # Check if exists first to get ID
        existing_org = await client.query("organizations:getBySlug", {"slug": slug})
        if existing_org:
             tenant_id = existing_org["_id"]
             tenant_name = existing_org["name"]
        else:
             tenant_id = await client.mutation("organizations:create", {
                 "slug": slug, 
                 "name": client_name, 
                 "status": "active"
             })
             tenant_name = client_name

        # 2. create twiml app
        app_sid = await self.create_twiml_app(friendly_name=f"{slug}-twiml-app", voice_url=voice_url)

        # 3. buy number
        phone_number, number_sid = await self.buy_number(country=country)

        # 4. attach number to app
        await self.attach_number_to_app(number_sid=number_sid, app_sid=app_sid)

        # 5. persist phone number config
        phone_config_args = {
            "phoneNumber": phone_number,
            "organizationId": str(tenant_id), # Ensure string ID
            "jobType": job_type,
            "configJson": json.dumps({"twiml_app_sid": app_sid, "twilio_sid": number_sid, "provisioned": True})
        }
        await client.mutation("phoneConfigs:create", phone_config_args)

        return {
            "tenant": {
                "id": tenant_id,
                "slug": slug,
                "name": tenant_name
            },
            "phone": {
                "phone_number": phone_number,
                "number_sid": number_sid,
                "twiml_app_sid": app_sid,
                "phone_config_id": "convex_managed" 
            }
        }
