"""
Make Outbound Calls Using TwiML Bin
Simple script to trigger calls without exposing webhooks

Usage:
    python make_call.py +1234567890
    
Prerequisites:
    1. Configure .env with Twilio credentials
    2. Create session first OR use auto-create mode
    3. Have your TwiML Bin URL ready
"""

import sys
import asyncio
import httpx
from twilio.rest import Client
from app.core.config import settings
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def create_session(phone_number: str = "+1234567890"):
    """Create a new session for the call

    NOTE: The session must be created for the Twilio 'from' number (the configured
    TWILIO_PHONE_NUMBER). The caller previously passed the destination number here,
    which caused the API to return 404 (phone config not found).
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Use the configured Twilio phone number (the 'from' number) so the
            # backend can look up the PhoneNumberConfig for that Twilio number.
            response = await client.post(
                f"http://{settings.API_CLIENT_HOST}:{settings.API_PORT}/api/v1/sessions/create-from-number",
                json={"phone_number": settings.TWILIO_PHONE_NUMBER, "call_type": "outbound"}
            )
            
            if response.status_code == 201:
                data = response.json()
                session_id = data["session_id"]
                logger.info(f"✅ Session created: {session_id}")
                return session_id
            else:
                logger.error(f"❌ Failed to create session: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                return None
    except Exception as e:
        logger.error(f"❌ Error creating session: {e}")
        return None


def make_outbound_call(to_number: str, session_id: str, use_twiml_bin: bool = False, twiml_bin_url: str = None):
    """
    Make an outbound call using dynamic TwiML or TwiML Bin
    
    Args:
        to_number: Customer phone number (e.g., +1234567890)
        session_id: Session ID for the call
        use_twiml_bin: If True, use TwiML Bin URL instead of dynamic TwiML
        twiml_bin_url: Your TwiML Bin URL (only needed if use_twiml_bin=True)
    """
    from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
    
    logger.info("=" * 60)
    logger.info("📞 Making Outbound Call")
    logger.info("=" * 60)
    
    # Validate Twilio credentials
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.error("❌ Twilio credentials not configured in .env")
        logger.error("   Add: TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN")
        return None
    
    if not settings.TWILIO_PHONE_NUMBER:
        logger.error("❌ TWILIO_PHONE_NUMBER not configured in .env")
        return None
    
    if not settings.WEBSOCKET_URL:
        logger.error("❌ WEBSOCKET_URL not configured in .env")
        logger.error("   Add: WEBSOCKET_URL=wss://your-ngrok-url.ngrok-free.dev")
        return None
    
    try:
        # Initialize Twilio client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        logger.info(f"📱 To: {to_number}")
        logger.info(f"📱 From: {settings.TWILIO_PHONE_NUMBER}")
        logger.info(f"🆔 Session ID: {session_id}")
        
        # Generate TwiML with session ID
        if use_twiml_bin and twiml_bin_url:
            # Use TwiML Bin (static - won't have session_id in WebSocket URL)
            logger.warning("⚠️  Using TwiML Bin - session_id won't be in WebSocket URL")
            twiml_url = twiml_bin_url
        else:
            # Generate dynamic TwiML with session ID embedded
            response = VoiceResponse()
            connect = Connect()
            websocket_url = f"{settings.WEBSOCKET_URL}/voice/{session_id}"
            connect.stream(url=websocket_url)
            response.append(connect)
            twiml = str(response)
            
            logger.info(f"🔗 WebSocket: {websocket_url}")
            logger.info(f"📄 TwiML: {twiml[:100]}...")
            
            # Use TwiML directly
            twiml_url = None
        
        # Make the call
        call_params = {
            "to": to_number,
            "from_": settings.TWILIO_PHONE_NUMBER,
            # Note: status_callback removed - it was causing POST requests to WebSocket server
            # Add it back when you have a proper HTTP endpoint for status callbacks
        }
        
        if twiml_url:
            call_params["url"] = twiml_url
        else:
            call_params["twiml"] = twiml
        
        call = client.calls.create(**call_params)
        
        logger.info("=" * 60)
        logger.info("✅ Call Initiated Successfully!")
        logger.info("=" * 60)
        logger.info(f"📞 Call SID: {call.sid}")
        logger.info(f"📊 Status: {call.status}")
        logger.info(f"🔗 Track at: https://console.twilio.com/us1/monitor/logs/calls/{call.sid}")
        logger.info("=" * 60)
        
        return call.sid
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ Error making call: {e}")
        logger.error("=" * 60)
        return None


async def main():
    """Main function"""
    
    print("\n" + "=" * 60)
    print("📞 OUTBOUND CALL MAKER - Dynamic TwiML")
    print("=" * 60)
    
    # Check if phone number provided
    if len(sys.argv) < 2:
        print("\n❌ Usage: python make_call.py <phone_number>")
        print("\nExample:")
        print("  python make_call.py +919078156839")
        print("\n💡 Tips:")
        print("  - Phone number must include country code (e.g., +91 for India, +1 for US)")
        print("  - Make sure .env has all required credentials:")
        print("    - TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER")
        print("    - WEBSOCKET_URL (your ngrok WebSocket URL)")
        print("=" * 60)
        sys.exit(1)
    
    to_number = sys.argv[1]
    
    # Step 1: Create session
    print(f"\n1️⃣  Creating session...")
    session_id = await create_session(to_number)  # Pass actual phone number
    
    if not session_id:
        print("\n❌ Failed to create session. Make sure API server is running:")
        print("   python server.py")
        return
    
    print(f"✅ Session created: {session_id}")
    
    # Step 2: Make outbound call with dynamic TwiML
    print(f"\n2️⃣  Making outbound call...")
    call_sid = make_outbound_call(to_number, session_id)
    
    if call_sid:
        print(f"\n✅ Call initiated successfully!")
        print(f"\n📞 What happens next:")
        print(f"   1. Twilio calls {to_number}")
        print(f"   2. When answered, connects to WebSocket: {settings.WEBSOCKET_URL}/voice/{session_id}")
        print(f"   3. Voice agent starts conversation")
        print(f"\n📊 Monitor:")
        print(f"   - Twilio Console: https://console.twilio.com/us1/monitor/logs/calls/{call_sid}")
        print(f"   - WebSocket logs: Check your WebSocket server terminal")
        print(f"   - API logs: Check your API server terminal")
    else:
        print("\n❌ Failed to make call")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

