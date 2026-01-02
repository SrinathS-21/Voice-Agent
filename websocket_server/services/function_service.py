"""
Function Execution Service
Handles function call execution
"""

import json
from typing import Dict, Callable
import asyncio
import inspect

from app.core.logging import get_logger
from app.core.exceptions import FunctionExecutionException

logger = get_logger(__name__)


class FunctionExecutionService:
    """Service for executing voice agent functions"""
    
    @staticmethod
    async def execute(
        func_name: str,
        arguments: Dict,
        functions: Dict[str, Callable]
    ) -> Dict:
        """
        Execute a function call
        
        Args:
            func_name: Function name
            arguments: Function arguments
            functions: Available functions dictionary
            
        Returns:
            Function execution result
            
        Raises:
            FunctionExecutionException: If execution fails
        """
        if func_name not in functions:
            error_msg = f"Unknown function: {func_name}"
            logger.error(error_msg, available_functions=list(functions.keys()))
            return {"error": error_msg}
        
        try:
            logger.info(
                "Executing function",
                function=func_name,
                arguments=arguments
            )

            func = functions[func_name]
            # Support async or sync callables
            if inspect.iscoroutinefunction(func):
                result = await func(**arguments)
            else:
                # run sync function in a thread to avoid blocking
                result = await asyncio.to_thread(func, **arguments)
            
            logger.info(
                "Function executed successfully",
                function=func_name,
                result=result
            )
            
            return result
            
        except Exception as e:
            error_msg = f"Function execution failed: {str(e)}"
            logger.error(
                "Function execution error",
                function=func_name,
                error=str(e)
            )
            raise FunctionExecutionException(func_name, str(e))
    
    @staticmethod
    def create_response(func_id: str, func_name: str, result: Dict) -> Dict:
        """
        Create function call response for Deepgram
        
        Args:
            func_id: Function call ID
            func_name: Function name
            result: Execution result
            
        Returns:
            Formatted response dictionary
        """
        return {
            "type": "FunctionCallResponse",
            "id": func_id,
            "name": func_name,
            "content": json.dumps(result)
        }
