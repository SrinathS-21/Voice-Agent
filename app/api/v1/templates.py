"""
Template Routes
Pre-built configuration templates for common use cases.
Domain-agnostic - works with any business type.
"""

from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("/general")
async def get_general_template() -> Dict[str, Any]:
    """Get a generic template configuration that works for any business"""
    return {
        "template_name": "general",
        "description": "Domain-agnostic template for any business type",
        "config": {
            "language": "en",
            "system_prompt": """You are a helpful and professional voice assistant for a business.
            You help customers with:
            1) Answering questions about products, services, and offerings
            2) Providing business information (hours, location, contact)
            3) Assisting with orders, bookings, or appointments as applicable
            
            Be friendly, helpful, and professional.
            Search the knowledge base to provide accurate information.
            
            CRITICAL VOICE RULES: This is a PHONE conversation - your responses will be converted to SPEECH.
            NEVER use markdown (**, *, #, -, •), emojis, bullet points, or special formatting.
            Speak in plain conversational English as if talking face-to-face.
            Keep responses concise and natural for voice.""",
            "greeting": "Hello! I'm your virtual assistant. How can I help you today?",
            "suggested_functions": [
                {
                    "name": "search_catalog",
                    "description": "Search for products, items, or services",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "What to search for"
                            },
                            "category": {
                                "type": "string",
                                "description": "Optional category filter"
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "get_information",
                    "description": "Get business information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "What information is needed"
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "end_call",
                    "description": "End the call",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {"type": "string"}
                        }
                    }
                }
            ]
        }
    }


@router.get("/hospitality")
@router.get("/restaurant")
async def get_hospitality_template() -> Dict[str, Any]:
    """Get a template configuration for hospitality businesses (restaurants, hotels, venues)"""
    return {
        "template_name": "hospitality",
        "description": "Pre-configured template for hospitality businesses",
        "config": {
            "language": "en",
            "system_prompt": """You are a friendly and professional assistant for a hospitality business. 
            You help customers with:
            1) Information about offerings and availability
            2) Making reservations or bookings
            3) Answering questions about services and amenities
            
            Be warm, welcoming, and helpful.
            When taking reservations, ALWAYS confirm the customer's name and details.
            
            CRITICAL VOICE RULES: This is a PHONE conversation - your responses will be converted to SPEECH.
            NEVER use markdown (**, *, #, -, •), emojis (🎉, 😊), bullet points, or special formatting.
            Speak in plain conversational English as if talking face-to-face.
            Keep responses concise and natural for voice.""",
            "greeting": "Hello and welcome! I'm your virtual assistant. How can I help you today?",
            "suggested_functions": [
                {
                    "name": "search_catalog",
                    "description": "Search for items, products, or offerings",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "What to search for"
                            },
                            "category": {
                                "type": "string",
                                "description": "Category filter"
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "make_reservation",
                    "description": "Make a reservation or booking",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_name": {"type": "string"},
                            "date": {"type": "string"},
                            "time": {"type": "string"},
                            "party_size": {"type": "integer"}
                        },
                        "required": ["customer_name", "date", "time"]
                    }
                },
                {
                    "name": "get_business_info",
                    "description": "Get business information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "info_type": {
                                "type": "string",
                                "description": "Type of information (hours, location, policies)"
                            }
                        },
                        "required": ["info_type"]
                    }
                }
            ]
        }
    }


@router.get("/healthcare")
@router.get("/pharmacy")
async def get_healthcare_template() -> Dict[str, Any]:
    """Get a template configuration for healthcare businesses"""
    return {
        "template_name": "healthcare",
        "description": "Pre-configured template for healthcare and pharmacy",
        "config": {
            "language": "en",
            "system_prompt": """You are a professional assistant for a pharmacy.
            You help customers with:
            1) Prescription refills
            2) Checking prescription status
            3) Medication information
            
            Be professional, clear, and ensure customer privacy.
            Always verify customer identity before discussing prescriptions.
            
            IMPORTANT: This is a VOICE conversation - use plain conversational language only.""",
            "greeting": "Welcome to our pharmacy. How can I assist you today?",
            "suggested_functions": [
                {
                    "name": "check_prescription",
                    "description": "Check prescription status",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prescription_id": {
                                "type": "string",
                                "description": "Prescription ID number"
                            }
                        },
                        "required": ["prescription_id"]
                    }
                },
                {
                    "name": "refill_prescription",
                    "description": "Request prescription refill",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_name": {"type": "string"},
                            "prescription_id": {"type": "string"}
                        },
                        "required": ["customer_name", "prescription_id"]
                    }
                }
            ]
        }
    }


@router.get("/hotel")
async def get_hotel_template() -> Dict[str, Any]:
    """Get a template configuration for hotel voice agent"""
    return {
        "template_name": "hotel",
        "description": "Pre-configured template for hotel voice agents",
        "config": {
            "language": "en",
            "system_prompt": """You are a courteous assistant for a hotel.
            You help guests with:
            1) Room bookings
            2) Checking availability
            3) Amenities information
            4) Room service orders
            
            Be professional, welcoming, and attentive to guest needs.
            
            IMPORTANT: This is a VOICE conversation - use plain conversational language only.""",
            "greeting": "Welcome to our hotel! How may I assist you today?",
            "suggested_functions": [
                {
                    "name": "check_availability",
                    "description": "Check room availability",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "check_in": {"type": "string"},
                            "check_out": {"type": "string"},
                            "guests": {"type": "integer"}
                        },
                        "required": ["check_in", "check_out", "guests"]
                    }
                },
                {
                    "name": "make_booking",
                    "description": "Book a room",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "guest_name": {"type": "string"},
                            "room_type": {"type": "string"},
                            "check_in": {"type": "string"},
                            "check_out": {"type": "string"}
                        },
                        "required": ["guest_name", "room_type", "check_in", "check_out"]
                    }
                }
            ]
        }
    }
