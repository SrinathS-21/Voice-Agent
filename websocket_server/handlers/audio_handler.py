"""
Audio Stream Handler
Handles audio streaming between Twilio and Deepgram
"""

import asyncio
import base64
import json
import time
from typing import Optional

from app.core.logging import get_logger
from app.utils.websocket_helper import WebSocketHelper
from websocket_server.services.db_logger import DatabaseLogger

logger = get_logger(__name__)
db_logger = DatabaseLogger()


class AudioStreamHandler:
    """Handles bidirectional audio streaming"""
    
    BUFFER_SIZE = 160  # 20ms of mulaw audio at 8kHz (160 samples @ 8kHz, 1 byte/sample)
    
    # Track greeting latency (call answer -> first agent audio)
    _call_start_times = {}
    # Track think latency (user utterance end -> assistant generation)
    _last_user_utterance_end_times = {}
    # Track when config was sent to Deepgram to measure apply latency
    _config_sent_times = {}
    
    # 🆕 Detailed latency tracking for STT, LLM, TTS
    _stt_start_times = {}  # When user started speaking
    _llm_start_times = {}  # When transcript sent to LLM
    _tts_start_times = {}  # When TTS generation started
    
    # Auto-hangup after farewell (two-phase detection)
    _farewell_pending = {}  # Track if farewell phrase detected (text)
    _farewell_complete = {}  # Track if farewell audio transmission completed
    _farewell_start_time = {}  # Track when farewell was first detected (for fallback timeout)
    _last_activity_time = {}  # Track last user activity
    
    @staticmethod
    async def twilio_to_deepgram(twilio_ws, audio_queues, streamsid_queue, session_metadata=None, call_sid_queue=None):
        """
        Receive audio from Twilio and queue for Deepgram
        
        Args:
            twilio_ws: Twilio WebSocket connection
            audio_queue: Queue for audio chunks
            streamsid_queue: Queue for stream ID
            session_metadata: Dict with phone_number and call_type
            call_sid_queue: Queue for call_sid (for Twilio hangup)
        """
        logger.info("Twilio receiver started")
        inbuffer = bytearray(b"")
        current_stream_id = None  # Store stream_id here
        session_metadata = session_metadata or {}
        
        async for message in twilio_ws:
            try:
                data = WebSocketHelper.parse_twilio_message(message)
                event = data.get("event")
                
                if event == "start":
                    # 📊 LATENCY TRACKING: Record call start time
                    start_time = time.time()
                    
                    # Extract all call information from Twilio
                    call_info = WebSocketHelper.extract_call_info(data)
                    stream_id = call_info["stream_sid"]
                    current_stream_id = stream_id  # Save it
                    streamsid_queue.put_nowait(stream_id)
                    
                    # Store start time for latency measurement
                    AudioStreamHandler._call_start_times[stream_id] = start_time
                    
                    # Prioritize session metadata for call_type (we set it correctly when creating session)
                    # Use Twilio data for phone_number (actual number being called/calling)
                    phone_number = call_info.get("phone_number") or session_metadata.get('phone_number')
                    call_type = session_metadata.get('call_type', 'inbound')  # Trust session metadata for call type
                    call_sid_value = call_info.get("call_sid")
                    
                    logger.info(f"📞 Call started | stream_id={stream_id} | call_sid={call_sid_value} | phone={phone_number} | type={call_type}")
                    
                    # Get organization_id from session_metadata if available
                    organization_id = session_metadata.get('organization_id') or session_metadata.get('organizationId')
                    
                    # Start collecting conversation data with metadata
                    db_logger.start_conversation(
                        stream_id,
                        phone_number=phone_number,
                        call_type=call_type,
                        call_sid=call_sid_value,
                        organization_id=organization_id
                    )
                    
                    # Send call_sid to deepgram_to_twilio for hangup capability
                    if call_sid_queue:
                        call_sid_queue.put_nowait(call_sid_value)
                    
                elif event == "connected":
                    logger.info("Twilio connected")
                    
                elif event == "media":
                    media = data.get("media", {})
                    if media.get("track") == "inbound":
                        chunk = WebSocketHelper.decode_audio(media["payload"])
                        inbuffer.extend(chunk)
                        
                elif event == "stop":
                    logger.info("Call ended by Twilio")
                    # Save complete conversation to database (await to ensure it completes)
                    if current_stream_id:
                        await db_logger.save_conversation(current_stream_id)
                    break
                
                # Send buffered audio to one or more provider queues
                while len(inbuffer) >= AudioStreamHandler.BUFFER_SIZE:
                    chunk = inbuffer[:AudioStreamHandler.BUFFER_SIZE]
                    # audio_queues may be a single Queue or a list of Queues
                    queues = audio_queues if isinstance(audio_queues, (list, tuple)) else [audio_queues]
                    for q in queues:
                        try:
                            q.put_nowait(chunk)
                        except Exception:
                            # If a queue fails, log and continue
                            logger.warning("Failed to enqueue audio chunk to a provider queue")
                    inbuffer = inbuffer[AudioStreamHandler.BUFFER_SIZE:]
                    
            except Exception as e:
                logger.error("Error in Twilio receiver", error=str(e))
                break
    
    @staticmethod
    async def _terminate_twilio_call(call_sid: str, stream_id: str):
        """
        Terminate Twilio call via REST API
        
        Args:
            call_sid: Twilio call SID
            stream_id: Stream ID for logging
        """
        try:
            from twilio.rest import Client
            from app.core.config import settings
            
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            # Use asyncio.to_thread to avoid blocking the event loop
            await asyncio.to_thread(
                lambda: client.calls(call_sid).update(status='completed')
            )
            logger.info(f"✅ Twilio call terminated successfully", call_sid=call_sid, stream_id=stream_id)
        except Exception as e:
            logger.error(f"❌ Failed to terminate Twilio call", call_sid=call_sid, stream_id=stream_id, error=str(e))
    
    @staticmethod
    async def deepgram_to_twilio(deepgram_ws, twilio_ws, streamsid_queue, session_id: str, on_function_call, call_sid_queue=None):
        """
        Receive from Deepgram and send to Twilio
        
        Args:
            deepgram_ws: Deepgram WebSocket connection
            twilio_ws: Twilio WebSocket connection
            streamsid_queue: Queue for stream ID
            session_id: Session ID
            on_function_call: Callback for function calls
            call_sid_queue: Queue for call_sid (for Twilio hangup)
        """
        logger.info("Deepgram receiver started", session_id=session_id)
        stream_id = await streamsid_queue.get()
        
        # Track if we've sent first audio (for greeting latency measurement)
        first_audio_sent = False
        
        # Track call_sid for Twilio hangup (wait for it with timeout)
        call_sid = None
        if call_sid_queue:
            try:
                call_sid = await asyncio.wait_for(call_sid_queue.get(), timeout=5.0)
                logger.info(f"Received call_sid for hangup capability: {call_sid}")
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for call_sid - Twilio hangup will not be available")
        
        async for message in deepgram_ws:
            try:
                if isinstance(message, str):
                    # Text message (events, function calls)
                    import json
                    decoded = json.loads(message)
                    msg_type = decoded.get("type", "unknown")
                    
                    # Log important Deepgram events only
                    if msg_type == "UserStartedSpeaking":
                        await WebSocketHelper.send_clear(twilio_ws, stream_id)
                        # 📊 STT TIMING: Record when user started speaking
                        AudioStreamHandler._stt_start_times[stream_id] = time.time()
                        logger.info("🎤 User started speaking (barge-in + STT timing started)")
                    
                    elif msg_type == "UtteranceEnd":
                        role = decoded.get('role')
                        logger.info(f"UtteranceEnd: {role} finished speaking")
                        # If the user finished speaking, record timestamp to measure think latency
                        if role == 'user':
                            AudioStreamHandler._last_user_utterance_end_times[stream_id] = time.time()
                        # If assistant finished speaking and farewell is pending, mark as complete
                        elif role == 'assistant' and stream_id in AudioStreamHandler._farewell_pending:
                            AudioStreamHandler._farewell_complete[stream_id] = True
                            logger.info(f"👋 Farewell audio transmission complete (UtteranceEnd). Call can be terminated.")
                    
                    elif msg_type == "AgentAudioDone":
                        logger.info("Deepgram event: AgentAudioDone")
                        # If farewell is pending, mark as complete (Deepgram sends this instead of UtteranceEnd for assistant)
                        if stream_id in AudioStreamHandler._farewell_pending:
                            AudioStreamHandler._farewell_complete[stream_id] = True
                            logger.info(f"👋 Farewell audio transmission complete (AgentAudioDone). Call can be terminated.")
                    
                    elif msg_type == "FunctionCallRequest":
                        function_name = decoded.get("function_name", "unknown")
                        logger.info(f"Function call: {function_name}")
                        
                        # Handle end_call explicitly for graceful hangup
                        if function_name == "end_call":
                            logger.info("📞 Tool requested hangup (end_call). Initiating graceful shutdown.")
                            AudioStreamHandler._farewell_pending[stream_id] = True
                            AudioStreamHandler._farewell_start_time[stream_id] = time.time()
                        
                        await on_function_call(decoded, deepgram_ws, session_id, stream_id)
                    
                    elif msg_type == "ConversationText":
                        role = decoded.get("role", "unknown")
                        content = decoded.get("content", "")
                        logger.info(f"\n{'='*20}\n💬 {role.upper()}: {content}\n{'='*20}\n")

                        # 📊 LATENCY MEASUREMENTS
                        if role == 'user':
                            # STT LATENCY: User started speaking -> transcript ready
                            stt_start = AudioStreamHandler._stt_start_times.pop(stream_id, None)
                            if stt_start:
                                stt_latency_ms = (time.time() - stt_start) * 1000
                                logger.info(f"⏱️  STT LATENCY: {stt_latency_ms:.0f}ms (speech start → transcript)")
                            
                            # Mark LLM processing start
                            AudioStreamHandler._llm_start_times[stream_id] = time.time()
                            
                            # Track user activity for auto-hangup
                            AudioStreamHandler._last_activity_time[stream_id] = time.time()
                            
                            # Detect farewell phrases from user
                            farewell_phrases = ["goodbye", "bye", "see you", "thank you", "thanks", "cut the call", "hang up", "end call"]
                            if any(phrase in content.lower() for phrase in farewell_phrases):
                                logger.info(f"👋 Farewell detected from user (text) - awaiting agent response completion")
                                AudioStreamHandler._farewell_pending[stream_id] = True
                                AudioStreamHandler._farewell_start_time[stream_id] = time.time()
                        
                        elif role == 'assistant':
                            # LLM LATENCY: Transcript ready -> LLM response
                            llm_start = AudioStreamHandler._llm_start_times.pop(stream_id, None)
                            if llm_start:
                                llm_latency_ms = (time.time() - llm_start) * 1000
                                logger.info(f"⏱️  LLM LATENCY: {llm_latency_ms:.0f}ms (transcript → LLM response)")
                            
                            # THINK LATENCY: User utterance end -> assistant text (total pipeline)
                            last_end = AudioStreamHandler._last_user_utterance_end_times.pop(stream_id, None)
                            if last_end:
                                think_latency_ms = (time.time() - last_end) * 1000
                                logger.info(f"⏱️  TOTAL PIPELINE: {think_latency_ms:.0f}ms (user end → assistant text) 🚀")
                            
                            # Mark TTS processing start
                            AudioStreamHandler._tts_start_times[stream_id] = time.time()
                            
                            # Detect farewell from assistant
                            farewell_responses = ["goodbye", "bye", "take care", "have a great day", "enjoy your day", "alright"]
                            if any(phrase in content.lower() for phrase in farewell_responses):
                                logger.info(f"👋 Assistant farewell detected")
                        # Collect message in conversation (use stream_id, not session_id)
                        collector = db_logger.get_conversation(stream_id)
                        if collector:
                            collector.add_message(role, content)

                        # NOTE: Deepgram Voice Agent API already handles TTS internally.
                        # When Deepgram sends ConversationText for assistant, it also sends
                        # the corresponding binary audio. We do NOT need to call _speak_and_forward
                        # separately as that would cause the response to be spoken twice.
                        # The binary audio from Deepgram (handled in the else branch below) is
                        # already being forwarded to Twilio.
                        if role == 'assistant':
                            logger.info("Deepgram ConversationText (assistant) received — audio handled by Deepgram agent", session_id=session_id, stream_id=stream_id)
                            # No additional TTS needed - Deepgram sends audio via binary messages
                        # Note: Collector may not exist if message arrives after call ended - this is normal
                    
                    elif msg_type == "Warning":
                        # Log full warning message - this is critical for debugging
                        logger.warning(f"⚠️  Deepgram Warning: {json.dumps(decoded)}")
                        # Add warning to conversation collector
                        collector = db_logger.get_conversation(stream_id)
                        if collector:
                            collector.add_warning(decoded)

                    elif msg_type == "SettingsApplied":
                        logger.info("Deepgram event: SettingsApplied")
                        # If we recorded when config was sent, measure apply latency
                        sent_time = AudioStreamHandler._config_sent_times.pop(session_id, None)
                        if sent_time:
                            apply_latency_ms = (time.time() - sent_time) * 1000
                            logger.info(f"⏱️  CONFIG APPLY LATENCY: {apply_latency_ms:.0f}ms (config sent → settings applied)")
                    
                    elif msg_type == "Error":
                        # Log full error message
                        logger.error(f"❌ Deepgram Error: {json.dumps(decoded)}")
                        collector = db_logger.get_conversation(stream_id)
                        if collector:
                            collector.add_error(decoded)
                    
                    else:
                        # Log other event types to debug
                        logger.info(f"Deepgram event: {msg_type}")
                    
                else:
                    # Binary message (audio) - send to Twilio
                    try:
                        size = len(message) if hasattr(message, '__len__') else None
                    except Exception:
                        size = None
                    # Binary audio - send to Twilio (log suppressed for clarity)
                    await WebSocketHelper.send_media(twilio_ws, message, stream_id)
                    
                    # 📊 TTS LATENCY: First audio byte received
                    if stream_id in AudioStreamHandler._tts_start_times:
                        tts_start = AudioStreamHandler._tts_start_times.pop(stream_id)
                        tts_latency_ms = (time.time() - tts_start) * 1000
                        logger.info(f"⏱️  TTS LATENCY: {tts_latency_ms:.0f}ms (LLM text → first audio)")
                    
                    # 📊 LATENCY TRACKING: Measure greeting latency on first audio
                    if not first_audio_sent and stream_id in AudioStreamHandler._call_start_times:
                        first_audio_sent = True
                        start_time = AudioStreamHandler._call_start_times[stream_id]
                        greeting_latency = (time.time() - start_time) * 1000  # Convert to ms
                        logger.info(f"⏱️  GREETING LATENCY: {greeting_latency:.0f}ms (call answer → first audio)")
                        # Clean up timing data
                        AudioStreamHandler._call_start_times.pop(stream_id, None)
                    
            except Exception as e:
                logger.error("Error in Deepgram receiver", error=str(e), session_id=session_id)
            
            # 🔚 AUTO-HANGUP: Check if call should end after farewell (check AFTER message processing)
            if stream_id in AudioStreamHandler._farewell_complete:
                last_activity = AudioStreamHandler._last_activity_time.get(stream_id)
                if last_activity:
                    idle_time = time.time() - last_activity
                    if idle_time > 3.0:  # 3 seconds after farewell audio completes
                        logger.info(f"📞 AUTO-HANGUP: {idle_time:.1f}s of silence after farewell completion. Ending call gracefully.")
                        # Save conversation before hangup
                        await db_logger.save_conversation(stream_id)
                        # Terminate call via Twilio if call_sid is available
                        if call_sid:
                            await AudioStreamHandler._terminate_twilio_call(call_sid, stream_id)
                        break
            
            # 🔚 FALLBACK TIMEOUT: Force hangup if farewell pending for too long (AgentAudioDone may not arrive)
            if stream_id in AudioStreamHandler._farewell_pending and stream_id not in AudioStreamHandler._farewell_complete:
                farewell_start = AudioStreamHandler._farewell_start_time.get(stream_id)
                if farewell_start and (time.time() - farewell_start) > 8.0:
                    logger.warning(f"⚠️  FALLBACK TIMEOUT: 8s elapsed since farewell detection. Forcing hangup.")
                    # Save conversation before hangup
                    await db_logger.save_conversation(stream_id)
                    # Terminate call via Twilio if call_sid is available
                    if call_sid:
                        await AudioStreamHandler._terminate_twilio_call(call_sid, stream_id)
                    break
        
        # Cleanup tracking dictionaries for this stream
        AudioStreamHandler._farewell_pending.pop(stream_id, None)
        AudioStreamHandler._farewell_complete.pop(stream_id, None)
        AudioStreamHandler._farewell_start_time.pop(stream_id, None)
        AudioStreamHandler._last_activity_time.pop(stream_id, None)
        logger.info("Farewell tracking cleaned up", stream_id=stream_id)
    
    @staticmethod
    async def send_to_deepgram(deepgram_ws, audio_queue):
        """
        Send audio from queue to Deepgram
        
        Args:
            deepgram_ws: Deepgram WebSocket connection
            audio_queue: Queue with audio chunks
        """
        logger.info("Audio sender started")
        
        while True:
            try:
                chunk = await audio_queue.get()
                try:
                    size = len(chunk) if hasattr(chunk, '__len__') else None
                except Exception:
                    size = None
                logger.debug("Sending audio chunk to Deepgram", bytes=size, ts=time.time())
                await deepgram_ws.send(chunk)
            except Exception as e:
                logger.error("Error sending audio to Deepgram", error=str(e))
                break
