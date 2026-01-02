"""
Dynamic Functions Module
Provides knowledge-base-backed function implementations for voice agents.
"""

from app.functions.dynamic_functions import (
    DynamicFunctions,
    get_dynamic_function_map,
    get_legacy_function_map,
)

__all__ = [
    "DynamicFunctions",
    "get_dynamic_function_map",
    "get_legacy_function_map",
]
