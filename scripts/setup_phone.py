import asyncio
import json
import logging
import sys
import os
from dotenv import load_dotenv

# Load environment variables first
load_dotenv(override=True)

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.convex_client import get_convex_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PHONE_NUMBER = "+12272573009"
ORG_SLUG = "kaanchi-cuisine"
ORG_NAME = "Kaanchi Cuisine"

# Voice Agent Configuration
AGENT_CONFIG = {
    "business": {
        "name": "Spina Soulful Kitchen",
        "type": "restaurant",
        "description": "Authentic South Indian cuisine",
        "specialties": ["Biryani", "Curries", "Tandoori"]
    },
    "language": "en",
    "system_prompt": """You are a friendly voice assistant for Spina Soulful Kitchen, an authentic South Indian restaurant.

IMPORTANT RULES:
1. For ANY factual question about the business (menu, prices, policies, hours, services, delivery, reservations, etc.), you MUST use the appropriate function to look up the information. DO NOT make up or guess answers.
2. Use 'get_menu' for food, dishes, menu items, and pricing questions.
3. Use 'lookup_info' for business hours, policies, services, delivery, reservations, cancellation, payment methods, and any other business information.
4. Keep responses concise since this is a phone conversation.
5. If information is not found, say so honestly instead of making things up.
6. NEVER use markdown formatting, asterisks (*), hash symbols (#), bullet points, or any special characters in your responses. Speak naturally as if having a real phone conversation.
7. When listing items, say them naturally like "First, we have X. Second, we have Y." instead of using numbered lists or bullet points.""",
    "greeting": "Hello! Welcome to Spina Soulful Kitchen. How may I assist you today?",
    "functions": [
        {
            "name": "get_menu",
            "description": "Search for menu items, dishes, food, or drinks. Use this for any menu-related questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term (e.g., 'chicken', 'vegetarian', 'spicy')"},
                    "category": {"type": "string", "description": "Category to filter by (e.g., starters, main_course, desserts)"}
                },
                "required": []
            }
        },
        {
            "name": "lookup_info",
            "description": "Look up business information including: hours, location, policies, services, delivery, reservations, cancellation, payment methods, or any other business details. ALWAYS use this for factual questions about the business.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to look up (e.g., 'delivery policy', 'opening hours', 'cancellation policy', 'services offered', 'payment methods')"}
                },
                "required": ["query"]
            }
        },
        {
             "name": "transfer_call",
             "description": "Transfer the user to a human agent when they explicitly request it",
             "parameters": {
                 "type": "object",
                 "properties": {
                     "reason": {"type": "string", "description": "Reason for transfer"}
                 },
                 "required": ["reason"]
             }
        }
    ]
}

async def setup_phone():
    client = get_convex_client()
    
    # 1. Get/Create Organization
    logger.info(f"Checking organization: {ORG_NAME}...")
    existing_org = await client.query("organizations:getBySlug", {"slug": ORG_SLUG})
    
    if existing_org:
        org_id = existing_org["_id"]
        logger.info(f"✅ Found existing organization: {org_id}")
    else:
        logger.info("Creating new organization...")
        org_id = await client.mutation("organizations:create", {
            "name": ORG_NAME,
            "slug": ORG_SLUG,
            "status": "active"
        })
        logger.info(f"✅ Created organization: {org_id}")

    # 2. Check/Create Phone Config
    logger.info(f"Checking phone config for {PHONE_NUMBER}...")
    existing_config = await client.query("phoneConfigs:getByPhoneNumber", {"phoneNumber": PHONE_NUMBER})
    
    config_json_str = json.dumps(AGENT_CONFIG)
    
    if existing_config:
        logger.info(f"Updating existing phone config: {existing_config['_id']}")
        await client.mutation("phoneConfigs:update", {
            "phoneNumber": PHONE_NUMBER,
            "organizationId": org_id,
            "configJson": config_json_str,
            "isActive": True
        })
        logger.info("✅ Phone config updated")
    else:
        logger.info("Creating new phone config...")
        await client.mutation("phoneConfigs:create", {
            "phoneNumber": PHONE_NUMBER,
            "organizationId": org_id,
            "jobType": "voice_agent",
            "configJson": config_json_str
        })
        logger.info("✅ Phone config created")
        
    print(f"\nSUCCESS! Phone {PHONE_NUMBER} linked to Org {org_id}")

if __name__ == "__main__":
    asyncio.run(setup_phone())
