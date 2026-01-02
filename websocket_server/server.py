"""
WebSocket Server
Clean, production-ready WebSocket server with proper structure
"""

import asyncio
import time
import websockets
import json
import httpx
from typing import Optional

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from websocket_server.connection_manager import get_connection_manager
from websocket_server.services.provider_service import ProviderService
from websocket_server.handlers.audio_handler import AudioStreamHandler
from websocket_server.handlers.function_handler import FunctionCallHandler
from app.session_cache import get_session_cache

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def _fetch_complete_session(session_id: str) -> dict:
    """
    Fetch complete session data (config + details) in one API call.
    
    This helper function calls the optimized /complete endpoint to reduce
    latency by eliminating one HTTP roundtrip.
    
    Args:
        session_id: Session ID to fetch
        
    Returns:
        dict: Complete session data with 'config' and 'details' keys
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"http://{getattr(settings, 'API_CLIENT_HOST', 'localhost')}:{settings.API_PORT}/api/v1/sessions/{session_id}/complete"
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Complete endpoint returned {response.status_code}")
                return None
    except Exception as e:
        logger.warning(f"Error fetching complete session data: {e}")
        return None


async def handle_call(twilio_ws, path: str):
    """
    Main WebSocket handler for incoming calls
    
    Args:
        twilio_ws: Twilio WebSocket connection
        path: WebSocket path (contains session ID)
    """
    # Extract session ID from path (/voice/{session_id})
    session_id = path.split("/")[-1] if "/" in path else "default"
    
    logger.info("=" * 60)
    logger.info("New call", session_id=session_id)
    logger.info("=" * 60)
    
    manager = get_connection_manager()
    
    try:
        # 🚀 FIRST: Try cache for session data
        session_data = get_session_cache(session_id)
        if session_data:
            config = session_data["config"]
            session_details = session_data.get("details")
            logger.info("✅ Session data fetched (cache)")
        else:
            # Fetch session data first so we can select the correct provider
            session_data = await _fetch_complete_session(session_id)
            if session_data and "config" in session_data:
                config = session_data["config"]
                session_details = session_data.get("details")
                logger.info("✅ Session data fetched")
            else:
                logger.warning("Complete endpoint failed, using fallback")
                config = await manager.fetch_session_config(session_id)
                session_details = None

            if not config:
                logger.error("No configuration found", session_id=session_id)
                try:
                    with open("config.json", "r") as f:
                        config = json.load(f)
                    logger.warning("Using fallback configuration")
                except Exception as e:
                    logger.error("Failed to load fallback config", error=str(e))
                    await twilio_ws.close()
                    return

                    # Determine provider type from config (default to deepgram)
            try:
                provider_type = config.get("agent", {}).get("listen", {}).get("provider", {}).get("type", "deepgram")
            except Exception:
                provider_type = "deepgram"

            # Prepare agent metadata for provider adapters
            agent_metadata = None
            try:
                if session_details and isinstance(session_details, dict):
                    md = session_details.get("metadata") or {}
                    agent_metadata = {
                        "agent_id": md.get("agent_id"),
                        "agent_name": md.get("agent_name"),
                        "agent_config": md.get("agent_config")
                    }
            except Exception:
                agent_metadata = None

            # Connect to the selected provider and enter its async context
            dg_connect_start = time.time()
            provider_cm = ProviderService.connect(provider_type, agent_metadata=agent_metadata)
            async with provider_cm as deepgram_ws:
                dg_connect_time_ms = (time.time() - dg_connect_start) * 1000
                logger.info(f"Provider connect time: {dg_connect_time_ms:.0f}ms")
                logger.info("✅ Connected to speech provider")

                # Extract organization_id from session details for dynamic function loading
                organization_id = None
                if session_details:
                    organization_id = session_details.get("organization_id") or session_details.get("organizationId")
                    if not organization_id and session_details.get("business"):
                        organization_id = session_details["business"].get("organization_id")
                
                # Load session functions with organization context
                if organization_id:
                    # Use new dynamic functions bound to organization
                    manager.load_session_functions(session_id, organization_id=organization_id)
                    logger.info(f"Using dynamic functions for org: {organization_id}")
                else:
                    # Fallback to legacy functions
                    manager.load_session_functions(session_id)
                    logger.info("Using legacy functions (no organization_id)")
                
                functions = manager.get_functions(session_id)
                logger.info("Functions loaded", count=len(functions), names=list(functions.keys()))

                # Register connection
                manager.register_connection(session_id, twilio_ws)

                # Initialize queues
                # When using Google as the listen provider we need two queues:
                # one for Deepgram (TTS/agent) and one for Google (ASR).
                audio_queue = asyncio.Queue()
                audio_queue_google = None
                streamsid_queue = asyncio.Queue()

                # Send configuration to Deepgram
                # Ensure the agent config has speak provider for TTS
                config.setdefault('agent', {})['speak'] = {"provider": {"type": "deepgram", "model": "aura-2-thalia-en"}}
                # Allow LLM from config.json (Groq for faster responses)
                # config['agent']['think'] = {"provider": {"type": "google", "model": "gemini-2.5-flash"}}
                logger.info("Speak and think providers updated in config")
                config_json = json.dumps(config)
                logger.info(f"Sending config to Deepgram: {config_json[:500]}...")
                await deepgram_ws.send(config_json)
                # Record config send time to measure apply latency
                AudioStreamHandler._config_sent_times[session_id] = time.time()
                logger.info("Configuration sent to Deepgram")

                # Create function call handler
                async def handle_function_call(decoded, dg_ws, sess_id, strm_id=None):
                    await FunctionCallHandler.handle(decoded, dg_ws, sess_id, strm_id)

                # Prepare session metadata for database logging (from session_details)
                session_metadata = {
                    'phone_number': 'unknown',
                    'call_type': 'inbound'
                }
                if session_details:
                    # Extract call_type directly
                    session_metadata['call_type'] = session_details.get('call_type', 'inbound')
                    # Extract phone_number from metadata dict
                    if 'metadata' in session_details and session_details['metadata']:
                        session_metadata['phone_number'] = session_details['metadata'].get('phone_number', 'unknown')
                    # Extract tenant information if present
                    tenant_id = None
                    if 'tenant_id' in session_details:
                        tenant_id = session_details.get('tenant_id')
                    elif 'business' in session_details and session_details['business'] and isinstance(session_details['business'], dict):
                        tenant_id = session_details['business'].get('tenant_id')
                    if tenant_id:
                        session_metadata['tenant_id'] = tenant_id
                    logger.info(f"Session metadata: phone={session_metadata['phone_number']}, type={session_metadata['call_type']}")

                # If the config requests Google as the listen provider, also
                # open a Google adapter in addition to Deepgram. We will send
                # audio to both and forward assistant messages from Google to
                # Deepgram so Deepgram can synthesize TTS audio.
                listen_provider = config.get("agent", {}).get("listen", {}).get("provider", {})
                if listen_provider and listen_provider.get("type") == "google":
                    # Connect Google adapter in parallel with Deepgram
                    google_cm = ProviderService.connect("google", agent_metadata=agent_metadata)
                    async with google_cm as google_ws:
                        # Create a separate audio queue for the Google adapter
                        audio_queue_google = asyncio.Queue()

                        # Send same config to Google adapter so it can extract audio settings
                        await google_ws.send(config_json)

                        # Start all handlers including bridge from Google -> Deepgram
                        await asyncio.gather(
                            AudioStreamHandler.send_to_deepgram(deepgram_ws, audio_queue),
                            AudioStreamHandler.send_to_deepgram(google_ws, audio_queue_google),
                            AudioStreamHandler.deepgram_to_twilio(
                                deepgram_ws,
                                twilio_ws,
                                streamsid_queue,
                                session_id,
                                handle_function_call
                            ),
                            AudioStreamHandler.google_to_deepgram(
                                google_ws,
                                deepgram_ws,
                                streamsid_queue,
                                session_id,
                                handle_function_call
                            ),
                            AudioStreamHandler.twilio_to_deepgram(
                                twilio_ws,
                                [audio_queue, audio_queue_google],
                                streamsid_queue,
                                session_metadata
                            )
                        )
                else:
                    # Default: single provider (Deepgram)
                    await asyncio.gather(
                        AudioStreamHandler.send_to_deepgram(deepgram_ws, audio_queue),
                        AudioStreamHandler.deepgram_to_twilio(
                            deepgram_ws,
                            twilio_ws,
                            streamsid_queue,
                            session_id,
                            handle_function_call
                        ),
                        AudioStreamHandler.twilio_to_deepgram(
                            twilio_ws,
                            audio_queue,
                            streamsid_queue,
                            session_metadata
                        )
                    )
 
        
    except Exception as e:
        logger.error("Error in call handler", session_id=session_id, error=str(e))
        import traceback
        logger.error("Traceback", trace=traceback.format_exc())
    
    finally:
        # Cleanup
        manager.cleanup_session(session_id)
        await twilio_ws.close()
        logger.info("Call ended", session_id=session_id)
        logger.info("=" * 60)


async def websocket_handler(websocket):
    """
    Route WebSocket connections (new websockets library API)
    Note: path is now accessed via websocket.request.path
    """
    path = websocket.request.path
    logger.info("WebSocket connection received", path=path)
    
    try:
        await handle_call(websocket, path)
    except Exception as e:
        logger.error("WebSocket handler error", error=str(e), path=path)


async def process_request(connection, request):
    """
    Process incoming HTTP requests before WebSocket upgrade
    This filters out non-WebSocket requests (like POST from status callbacks)
    
    Args:
        connection: WebSocket connection
        request: Request object with path and headers
    """
    # Check if this is a WebSocket upgrade request
    # request.headers is a Headers object
    upgrade = request.headers.get("Upgrade", "").lower()
    
    if upgrade != "websocket":
        logger.warning(f"Non-WebSocket request rejected", path=request.path, method=request.method)
        # Return 400 Bad Request for non-WebSocket requests
        return connection.respond(400, "WebSocket connection required\n")
    
    # Allow WebSocket upgrade to proceed
    return None


async def main():
    """Start WebSocket server"""
    host = settings.WEBSOCKET_HOST
    port = settings.WEBSOCKET_PORT
    
    logger.info("=" * 60)
    logger.info("DYNAMIC VOICE AGENT - WEBSOCKET SERVER")
    logger.info("=" * 60)
    logger.info("Configuration", host=host, port=port)
    logger.info("Deepgram API", configured="Yes" if settings.DEEPGRAM_API_KEY else "No")
    logger.info("API Server", url=f"http://{settings.API_HOST}:{settings.API_PORT}")
    logger.info("=" * 60)
    logger.info("Server started", url=f"ws://{host}:{port}")
    logger.info("=" * 60)
    logger.info("")
    logger.info("USAGE:")
    logger.info("  1. Create session: POST http://localhost:8000/api/v1/sessions/create")
    logger.info("  2. Connect Twilio: ws://{host}:{port}/voice/{{session_id}}")
    logger.info("  3. Call uses dynamic configuration from API")
    logger.info("=" * 60)
    
    # Start server with process_request to filter non-WebSocket requests
    async with websockets.serve(
        websocket_handler, 
        host, 
        port,
        process_request=process_request  # Filter out POST and other non-WebSocket requests
    ):
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error("Server error", error=str(e))
