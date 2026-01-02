"""
Helper utilities for WebSocket operations
"""

import json
import base64
from typing import Dict, Any

import websockets

from app.core.logging import get_logger

logger = get_logger(__name__)


class WebSocketHelper:
    """Helper class for WebSocket operations.

    send_json/send_media/send_clear are now resilient: they catch
    common websocket errors, try to close the socket gracefully, and
    return a boolean indicating success. Callers should check the
    return value when appropriate but existing code will continue to
    work because exceptions are no longer propagated.
    """

    @staticmethod
    async def send_json(websocket, data: Dict[str, Any]) -> bool:
        """Send JSON data over WebSocket; return True on success."""
        try:
            payload = json.dumps(data)
        except Exception as e:
            logger.error("Failed to serialize JSON", error=str(e), data_preview=str(data)[:200])
            return False

        try:
            await websocket.send(payload)
            return True
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning("WebSocket closed while sending JSON", error=str(e))
            try:
                await websocket.close()
            except Exception:
                pass
            return False
        except Exception as e:
            logger.error("Failed to send JSON", error=str(e))
            try:
                await websocket.close()
            except Exception:
                pass
            return False

    @staticmethod
    async def send_media(websocket, audio_data: bytes, stream_sid: str) -> bool:
        """Send media message to Twilio; returns True on success."""
        try:
            message = {
                "event": "media",
                "streamSid": stream_sid,
                "media": {
                    "payload": base64.b64encode(audio_data).decode("ascii")
                }
            }
            return await WebSocketHelper.send_json(websocket, message)
        except Exception as e:
            logger.error("Failed to prepare/send media message", error=str(e))
            return False

    @staticmethod
    async def send_clear(websocket, stream_sid: str) -> bool:
        """Send clear message (barge-in); returns True on success."""
        try:
            message = {"event": "clear", "streamSid": stream_sid}
            return await WebSocketHelper.send_json(websocket, message)
        except Exception as e:
            logger.error("Failed to prepare/send clear message", error=str(e))
            return False

    @staticmethod
    def parse_twilio_message(message: str) -> Dict[str, Any]:
        """Parse Twilio WebSocket message"""
        try:
            return json.loads(message)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Twilio message", error=str(e))
            return {}

    @staticmethod
    def extract_stream_id(start_message: Dict[str, Any]) -> str:
        """Extract stream ID from Twilio start message"""
        return start_message.get("start", {}).get("streamSid", "")

    @staticmethod
    def extract_call_info(start_message: Dict[str, Any]) -> Dict[str, str]:
        """Extract call information from Twilio start message"""
        start_data = start_message.get("start", {})
        # Determine call direction
        call_direction = start_data.get("direction", "inbound")

        # For outbound calls, customer is 'to'; for inbound, customer is 'from'
        if call_direction == "outbound":
            phone_number = start_data.get("to", "")
            call_type = "outbound"
        else:
            phone_number = start_data.get("from", "")
            call_type = "inbound"

        return {
            "stream_sid": start_data.get("streamSid", ""),
            "call_sid": start_data.get("callSid", ""),
            "phone_number": phone_number,
            "call_type": call_type
        }

    @staticmethod
    def decode_audio(payload: str) -> bytes:
        """Decode base64 audio payload"""
        try:
            return base64.b64decode(payload)
        except Exception as e:
            logger.error("Failed to decode audio", error=str(e))
            return b""
