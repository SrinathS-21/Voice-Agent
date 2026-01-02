"""
Function Call Handler
Handles function call requests from Deepgram
"""

import json
import asyncio
from typing import Dict

from websocket_server.services.function_service import FunctionExecutionService
from websocket_server.connection_manager import get_connection_manager
from websocket_server.services.db_logger import DatabaseLogger
from app.core.logging import get_logger

logger = get_logger(__name__)
db_logger = DatabaseLogger()


class FunctionCallHandler:
    """Handles function call requests"""
    
    @staticmethod
    async def handle(decoded: Dict, deepgram_ws, session_id: str, stream_id: str = None):
        """
        Handle function call request from Deepgram
        
        Args:
            decoded: Decoded message from Deepgram
            deepgram_ws: Deepgram WebSocket connection
            session_id: API Session ID
            stream_id: Twilio Stream ID (used for conversation collection)
        """
        manager = get_connection_manager()
        functions = manager.get_functions(session_id)
        
        try:
            for function_call in decoded.get("functions", []):
                func_name = function_call["name"]
                func_id = function_call["id"]
                arguments = json.loads(function_call["arguments"])
                
                logger.info(
                    "Function call request",
                    function=func_name,
                    id=func_id,
                    arguments=arguments,
                    session_id=session_id
                )
                
                # Execute function
                try:
                    result = await FunctionExecutionService.execute(
                        func_name,
                        arguments,
                        functions
                    )
                    
                    # Collect function call in conversation (use stream_id for DB)
                    collector = db_logger.get_conversation(stream_id or session_id)
                    if collector:
                        collector.add_function_call(func_name, arguments, result)
                    else:
                        logger.warning(f"⚠️  No collector found for stream_id={stream_id}")
                    
                except Exception as e:
                    result = {"error": str(e)}
                    logger.error(
                        "Function execution failed",
                        function=func_name,
                        error=str(e)
                    )
                
                # Send response to Deepgram
                response = FunctionExecutionService.create_response(
                    func_id,
                    func_name,
                    result
                )
                
                await deepgram_ws.send(json.dumps(response))
                
                logger.info(
                    "Function response sent",
                    function=func_name,
                    session_id=session_id
                )
                
        except Exception as e:
            logger.error(
                "Error handling function call",
                error=str(e),
                session_id=session_id
            )
            
            # Send error response
            error_response = FunctionExecutionService.create_response(
                func_id if "func_id" in locals() else "unknown",
                func_name if "func_name" in locals() else "unknown",
                {"error": f"Function call handling failed: {str(e)}"}
            )
            await deepgram_ws.send(json.dumps(error_response))
