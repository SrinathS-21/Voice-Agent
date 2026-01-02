"""
Domain Registry
Domain-agnostic configuration system for voice agents.
Supports pre-built templates AND fully custom domains.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

from app.core.logging import get_logger

logger = get_logger(__name__)


class DomainType(str, Enum):
    """
    Supported business domain types.
    CUSTOM allows any user-defined domain without restrictions.
    """
    # Generic domains (recommended for new implementations)
    CUSTOM = "custom"              # Fully user-defined
    GENERAL = "general"            # General-purpose assistant
    
    # Template-based domains (provide starting points)
    RETAIL = "retail"              # Products, shopping
    HOSPITALITY = "hospitality"    # Hotels, restaurants, venues
    HEALTHCARE = "healthcare"      # Medical, pharmacy, wellness
    SERVICES = "services"          # Professional services
    SUPPORT = "support"            # Customer support


@dataclass
class FunctionTemplate:
    """Template for a domain-specific function"""
    name: str
    description: str
    parameters: Dict[str, Any]
    handler_type: str  # "vector_search", "convex_query", "webhook", "static"
    handler_config: Dict[str, Any] = field(default_factory=dict)
    required: bool = True


@dataclass
class DomainConfig:
    """Configuration for a specific business domain"""
    domain_type: DomainType
    display_name: str
    description: str
    
    # System prompt template (supports {business_name}, {agent_name} placeholders)
    system_prompt_template: str
    
    # Default functions for this domain
    default_functions: List[FunctionTemplate]
    
    # Required data types for this domain
    required_data: List[str]
    optional_data: List[str] = field(default_factory=list)
    
    # Sample questions for testing
    sample_questions: List[str] = field(default_factory=list)
    
    # Compliance requirements
    compliance: List[str] = field(default_factory=list)
    
    # Disclaimers to include
    disclaimers: List[str] = field(default_factory=list)
    
    # Keywords for auto-detection
    detection_keywords: List[str] = field(default_factory=list)
    
    # Default voice/tone settings
    voice_settings: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# DOMAIN CONFIGURATIONS
# Templates provide starting points - users can customize everything
# =============================================================================

# Generic/Custom domain - works for any business type
GENERAL_CONFIG = DomainConfig(
    domain_type=DomainType.GENERAL,
    display_name="General Assistant",
    description="A flexible voice assistant that works for any business type",
    
    system_prompt_template="""You are {agent_name}, a helpful AI voice assistant for {business_name}.

Your role is to:
- Answer questions using information from the knowledge base
- Help customers find what they're looking for
- Provide accurate information about products, services, and policies
- Be polite and professional at all times

IMPORTANT GUIDELINES:
- Search the knowledge base to find accurate information before responding
- If you cannot find specific information, acknowledge this honestly
- Keep responses concise since this is a phone conversation
- Do not use markdown, emojis, or special formatting in responses
- Speak naturally as if having a conversation""",
    
    default_functions=[
        FunctionTemplate(
            name="search_catalog",
            description="Search for products, items, or services in the knowledge base. Use this when customers ask about offerings, prices, or availability.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query - what the customer is looking for"
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category filter to narrow results"
                    }
                },
                "required": ["query"]
            },
            handler_type="vector_search",
            handler_config={
                "source_type": "catalog",
                "limit": 5,
                "include_similar": True
            }
        ),
        FunctionTemplate(
            name="get_information",
            description="Get business information like hours, location, contact details, policies, or FAQs.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What information is needed"
                    },
                    "info_type": {
                        "type": "string",
                        "enum": ["hours", "location", "contact", "policies", "faq", "general"],
                        "description": "Type of information requested"
                    }
                },
                "required": ["query"]
            },
            handler_type="vector_search",
            handler_config={
                "source_type": "information",
                "limit": 3
            }
        ),
        FunctionTemplate(
            name="end_call",
            description="End the call when the customer says goodbye or is done.",
            parameters={
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason for ending the call"
                    }
                },
                "required": []
            },
            handler_type="static",
            handler_config={
                "action": "end_call"
            },
            required=True
        )
    ],
    
    required_data=[],  # No required data - works with any content
    optional_data=["catalog", "faq", "policies", "hours", "contact"],
    
    sample_questions=[
        "What do you offer?",
        "Can you tell me about your services?",
        "What are your hours?",
        "How can I contact you?"
    ],
    
    detection_keywords=[],  # Matches anything not matched by other domains
    
    voice_settings={
        "tone": "professional",
        "pace": "conversational",
        "formality": "semi-formal"
    }
)


# Hospitality domain - covers restaurants, hotels, cafes, venues
HOSPITALITY_CONFIG = DomainConfig(
    domain_type=DomainType.HOSPITALITY,
    display_name="Hospitality & Dining",
    description="For restaurants, hotels, cafes, venues, and hospitality businesses",
    
    system_prompt_template="""You are {agent_name}, a friendly and helpful AI assistant for {business_name}.

You help customers with:
- Answering questions about offerings, availability, and prices
- Making reservations and bookings
- Providing information about hours, location, and policies

IMPORTANT GUIDELINES:
- Be warm and welcoming
- Search the knowledge base for accurate information
- Keep responses concise since this is a phone conversation
- Do not use markdown, emojis, or special formatting in responses

If you cannot find information in the knowledge base, politely let the customer know and offer to connect them with staff.""",
    
    default_functions=[
        FunctionTemplate(
            name="search_catalog",
            description="Search for items, products, or offerings. Use this when customers ask about what's available, prices, or options.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query - item name, category, or description"
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category filter"
                    }
                },
                "required": ["query"]
            },
            handler_type="vector_search",
            handler_config={
                "source_type": "catalog",
                "limit": 5,
                "include_similar": True
            }
        ),
        FunctionTemplate(
            name="make_reservation",
            description="Make a reservation or booking for the customer.",
            parameters={
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Customer's name"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date for the reservation"
                    },
                    "time": {
                        "type": "string",
                        "description": "Time for the reservation"
                    },
                    "party_size": {
                        "type": "integer",
                        "description": "Number of people"
                    },
                    "special_requests": {
                        "type": "string",
                        "description": "Any special requests or notes"
                    }
                },
                "required": ["customer_name", "date", "time"]
            },
            handler_type="webhook",
            handler_config={
                "action": "create_reservation"
            }
        ),
        FunctionTemplate(
            name="get_business_info",
            description="Get business information like hours, location, contact details.",
            parameters={
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "enum": ["hours", "location", "contact", "policies"],
                        "description": "Type of information requested"
                    }
                },
                "required": ["info_type"]
            },
            handler_type="vector_search",
            handler_config={
                "source_type": "information",
                "limit": 3
            }
        ),
        FunctionTemplate(
            name="end_call",
            description="End the call when the customer says goodbye or is done.",
            parameters={
                "type": "object",
                "properties": {
                    "reason": {"type": "string"}
                },
                "required": []
            },
            handler_type="static",
            handler_config={"action": "end_call"},
            required=True
        )
    ],
    
    required_data=[],
    optional_data=["catalog", "policies", "hours", "faq"],
    
    sample_questions=[
        "What options do you have?",
        "Can I make a reservation?",
        "What are your hours?",
        "Do you have availability?"
    ],
    
    detection_keywords=[
        "menu", "food", "restaurant", "dish", "meal", "order", "reservation",
        "hotel", "room", "booking", "check-in", "amenities", "dining",
        "table", "guest", "accommodation", "beverage", "cuisine"
    ],
    
    voice_settings={
        "tone": "friendly",
        "pace": "conversational",
        "formality": "casual"
    }
)


# Keep backward compatibility - RESTAURANT_CONFIG now points to HOSPITALITY
RESTAURANT_CONFIG = HOSPITALITY_CONFIG


# Healthcare domain - covers pharmacy, clinics, wellness
HEALTHCARE_CONFIG = DomainConfig(
    domain_type=DomainType.HEALTHCARE,
    display_name="Healthcare & Wellness",
    description="For pharmacies, clinics, wellness centers, and medical practices",
    
    system_prompt_template="""You are {agent_name}, a professional AI assistant for {business_name}.

You help customers with:
- Answering questions about products and availability
- Providing general information
- Checking hours and location
- Directing customers to speak with staff for specialized questions

CRITICAL GUIDELINES:
- NEVER provide medical advice, dosage recommendations, or treatment information
- For ANY medical questions, direct customers to speak with qualified staff
- Only provide publicly available product information
- Be professional and helpful while maintaining appropriate boundaries
- Keep responses concise since this is a phone conversation
- Do not use markdown, emojis, or special formatting

REQUIRED DISCLAIMER: Always remind customers that for specific advice, they should consult with qualified professionals.""",
    
    default_functions=[
        FunctionTemplate(
            name="search_catalog",
            description="Search for products by name, category, or use case. Only provides general product information.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Product name or category to search for"
                    },
                    "category": {
                        "type": "string",
                        "description": "Product category filter"
                    }
                },
                "required": ["query"]
            },
            handler_type="vector_search",
            handler_config={
                "source_type": "catalog",
                "limit": 5
            }
        ),
        FunctionTemplate(
            name="check_availability",
            description="Check if a specific product is available.",
            parameters={
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "Name of the product to check"
                    }
                },
                "required": ["product_name"]
            },
            handler_type="webhook",
            handler_config={
                "action": "check_stock"
            }
        ),
        FunctionTemplate(
            name="get_business_info",
            description="Get business hours, location, and contact information.",
            parameters={
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "enum": ["hours", "location", "contact", "services"],
                        "description": "Type of information requested"
                    }
                },
                "required": ["info_type"]
            },
            handler_type="vector_search",
            handler_config={
                "source_type": "information",
                "limit": 3
            }
        ),
        FunctionTemplate(
            name="transfer_to_specialist",
            description="Transfer the call to a specialist for detailed questions.",
            parameters={
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason for the transfer"
                    }
                },
                "required": ["reason"]
            },
            handler_type="static",
            handler_config={
                "action": "transfer_call",
                "target": "specialist"
            }
        ),
        FunctionTemplate(
            name="end_call",
            description="End the call when the customer is done.",
            parameters={
                "type": "object",
                "properties": {
                    "reason": {"type": "string"}
                },
                "required": []
            },
            handler_type="static",
            handler_config={"action": "end_call"}
        )
    ],
    
    required_data=[],
    optional_data=["catalog", "services", "hours", "policies"],
    
    compliance=["HIPAA"],
    disclaimers=[
        "For specific advice, please consult with a qualified professional.",
        "This is general information only and not professional advice."
    ],
    
    sample_questions=[
        "Do you have this product in stock?",
        "What are your hours?",
        "I need to speak with someone.",
        "What services do you offer?"
    ],
    
    detection_keywords=[
        "pharmacy", "prescription", "medicine", "medication", "health",
        "clinic", "medical", "wellness", "appointment", "doctor"
    ],
    
    voice_settings={
        "tone": "professional",
        "pace": "clear",
        "formality": "formal"
    }
)

# Backward compatibility alias
PHARMACY_CONFIG = HEALTHCARE_CONFIG


HOTEL_CONFIG = DomainConfig(
    domain_type=DomainType.HOSPITALITY,  # Now part of HOSPITALITY
    display_name="Hotel & Accommodation",
    description="For hotels, resorts, bed & breakfasts, and vacation rentals",
    
    system_prompt_template="""You are {agent_name}, a professional concierge for {business_name}.

You assist guests with:
- Room availability and booking inquiries
- Room types, amenities, and pricing information
- Hotel services and facilities
- Check-in/check-out information
- Local recommendations and directions

GUIDELINES:
- Be warm, professional, and attentive
- Provide accurate information about rooms and amenities from the knowledge base
- For booking confirmations, collect all necessary information
- Offer to help with additional requests or special accommodations
- Keep responses concise since this is a phone conversation
- Do not use markdown, emojis, or special formatting""",
    
    default_functions=[
        FunctionTemplate(
            name="check_availability",
            description="Check room availability for specified dates.",
            parameters={
                "type": "object",
                "properties": {
                    "check_in": {
                        "type": "string",
                        "description": "Check-in date"
                    },
                    "check_out": {
                        "type": "string",
                        "description": "Check-out date"
                    },
                    "room_type": {
                        "type": "string",
                        "description": "Preferred room type (optional)"
                    },
                    "guests": {
                        "type": "integer",
                        "description": "Number of guests"
                    }
                },
                "required": ["check_in", "check_out"]
            },
            handler_type="webhook",
            handler_config={
                "action": "check_availability"
            }
        ),
        FunctionTemplate(
            name="search_catalog",
            description="Get detailed information about room types, amenities, and rates.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Room type or amenity to search for"
                    }
                },
                "required": ["query"]
            },
            handler_type="vector_search",
            handler_config={
                "source_type": "catalog",
                "limit": 5
            }
        ),
        FunctionTemplate(
            name="make_booking",
            description="Create a room reservation.",
            parameters={
                "type": "object",
                "properties": {
                    "guest_name": {"type": "string"},
                    "check_in": {"type": "string"},
                    "check_out": {"type": "string"},
                    "room_type": {"type": "string"},
                    "guests": {"type": "integer"},
                    "special_requests": {"type": "string"}
                },
                "required": ["guest_name", "check_in", "check_out", "room_type"]
            },
            handler_type="webhook",
            handler_config={
                "action": "create_booking"
            }
        ),
        FunctionTemplate(
            name="get_business_info",
            description="Get information about hotel amenities, services, policies, and local area.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What information is needed"
                    }
                },
                "required": ["query"]
            },
            handler_type="vector_search",
            handler_config={
                "source_type": "info",
                "limit": 5
            }
        ),
        FunctionTemplate(
            name="end_call",
            description="End the call when the guest is done.",
            parameters={
                "type": "object",
                "properties": {"reason": {"type": "string"}},
                "required": []
            },
            handler_type="static",
            handler_config={"action": "end_call"}
        )
    ],
    
    required_data=["room_inventory", "rates", "amenities"],
    optional_data=["policies", "local_info", "services", "packages"],
    
    sample_questions=[
        "Do you have any rooms available next weekend?",
        "What's the difference between a standard and deluxe room?",
        "What time is check-in?",
        "Is breakfast included?",
        "Do you have a pool?"
    ],
    
    detection_keywords=[
        "hotel", "room", "booking", "reservation", "check-in", "check-out",
        "suite", "amenities", "concierge", "guest", "stay", "accommodation"
    ],
    
    voice_settings={
        "tone": "professional",
        "pace": "measured",
        "formality": "formal"
    }
)


RETAIL_CONFIG = DomainConfig(
    domain_type=DomainType.RETAIL,
    display_name="Retail & E-commerce",
    description="For retail stores, online shops, and product-based businesses",
    
    system_prompt_template="""You are {agent_name}, a helpful sales assistant for {business_name}.

You help customers with:
- Finding products and answering product questions
- Checking product availability and pricing
- Providing information about shipping and returns
- Assisting with order status inquiries

GUIDELINES:
- Be friendly and helpful like an in-store sales associate
- Use the knowledge base to provide accurate product information
- Help customers find what they need even if they're not sure exactly what they want
- Be honest about product availability and limitations
- Keep responses concise since this is a phone conversation
- Do not use markdown, emojis, or special formatting""",
    
    default_functions=[
        FunctionTemplate(
            name="search_products",
            description="Search for products by name, category, or features.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Product search query"
                    },
                    "category": {
                        "type": "string",
                        "description": "Product category filter"
                    },
                    "price_max": {
                        "type": "number",
                        "description": "Maximum price filter"
                    }
                },
                "required": ["query"]
            },
            handler_type="vector_search",
            handler_config={
                "source_type": "catalog",
                "limit": 5
            }
        ),
        FunctionTemplate(
            name="check_stock",
            description="Check if a specific product is in stock.",
            parameters={
                "type": "object",
                "properties": {
                    "product_name": {"type": "string"},
                    "size": {"type": "string"},
                    "color": {"type": "string"}
                },
                "required": ["product_name"]
            },
            handler_type="webhook",
            handler_config={
                "action": "check_inventory"
            }
        ),
        FunctionTemplate(
            name="get_order_status",
            description="Check the status of an existing order.",
            parameters={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "email": {"type": "string"}
                },
                "required": ["order_id"]
            },
            handler_type="webhook",
            handler_config={
                "action": "order_status"
            }
        ),
        FunctionTemplate(
            name="get_store_info",
            description="Get store hours, location, shipping policies, or return information.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            },
            handler_type="vector_search",
            handler_config={
                "source_type": "info",
                "limit": 3
            }
        ),
        FunctionTemplate(
            name="end_call",
            description="End the call when the customer is done.",
            parameters={
                "type": "object",
                "properties": {"reason": {"type": "string"}},
                "required": []
            },
            handler_type="static",
            handler_config={"action": "end_call"}
        )
    ],
    
    required_data=["product_catalog", "pricing"],
    optional_data=["inventory", "shipping_info", "return_policy", "promotions"],
    
    sample_questions=[
        "Do you have this in blue?",
        "What's the price of the XYZ product?",
        "Do you offer free shipping?",
        "What's your return policy?",
        "Where's my order?"
    ],
    
    detection_keywords=[
        "product", "shop", "store", "buy", "purchase", "price", "sale",
        "shipping", "delivery", "return", "exchange", "inventory", "stock"
    ],
    
    voice_settings={
        "tone": "friendly",
        "pace": "upbeat",
        "formality": "casual"
    }
)


SERVICES_CONFIG = DomainConfig(
    domain_type=DomainType.SERVICES,
    display_name="Professional Services",
    description="For service-based businesses like salons, clinics, consultants, etc.",
    
    system_prompt_template="""You are {agent_name}, a professional assistant for {business_name}.

You help clients with:
- Answering questions about services offered
- Scheduling and managing appointments
- Providing information about pricing and packages
- Answering frequently asked questions

GUIDELINES:
- Be professional and courteous
- Accurately describe services from the knowledge base
- Help schedule appointments efficiently
- For complex or specialized questions, offer to connect with a specialist
- Keep responses concise since this is a phone conversation
- Do not use markdown, emojis, or special formatting""",
    
    default_functions=[
        FunctionTemplate(
            name="search_services",
            description="Search for services offered by the business.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "category": {"type": "string"}
                },
                "required": ["query"]
            },
            handler_type="vector_search",
            handler_config={
                "source_type": "services",
                "limit": 5
            }
        ),
        FunctionTemplate(
            name="check_availability",
            description="Check appointment availability.",
            parameters={
                "type": "object",
                "properties": {
                    "service": {"type": "string"},
                    "date": {"type": "string"},
                    "preferred_time": {"type": "string"}
                },
                "required": ["date"]
            },
            handler_type="webhook",
            handler_config={
                "action": "check_availability"
            }
        ),
        FunctionTemplate(
            name="book_appointment",
            description="Schedule an appointment.",
            parameters={
                "type": "object",
                "properties": {
                    "client_name": {"type": "string"},
                    "service": {"type": "string"},
                    "date": {"type": "string"},
                    "time": {"type": "string"},
                    "notes": {"type": "string"}
                },
                "required": ["client_name", "service", "date", "time"]
            },
            handler_type="webhook",
            handler_config={
                "action": "create_appointment"
            }
        ),
        FunctionTemplate(
            name="get_business_info",
            description="Get business hours, location, pricing, or policies.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            },
            handler_type="vector_search",
            handler_config={
                "source_type": "info",
                "limit": 3
            }
        ),
        FunctionTemplate(
            name="end_call",
            description="End the call.",
            parameters={
                "type": "object",
                "properties": {"reason": {"type": "string"}},
                "required": []
            },
            handler_type="static",
            handler_config={"action": "end_call"}
        )
    ],
    
    required_data=["services", "business_hours"],
    optional_data=["pricing", "staff", "policies", "faq"],
    
    sample_questions=[
        "What services do you offer?",
        "How much does a haircut cost?",
        "Can I book an appointment for Saturday?",
        "What are your hours?",
        "Do I need to bring anything?"
    ],
    
    detection_keywords=[
        "service", "appointment", "booking", "schedule", "consultation",
        "session", "treatment", "package", "pricing"
    ],
    
    voice_settings={
        "tone": "professional",
        "pace": "clear",
        "formality": "semi-formal"
    }
)


# =============================================================================
# DOMAIN REGISTRY
# =============================================================================

class DomainRegistry:
    """
    Registry for all supported business domains.
    Provides domain lookup, auto-detection, and function template retrieval.
    Supports both pre-built templates and fully custom domains.
    """
    
    _domains: Dict[str, DomainConfig] = {
        # Primary domain types
        DomainType.GENERAL.value: GENERAL_CONFIG,
        DomainType.CUSTOM.value: GENERAL_CONFIG,  # Custom uses general as base
        DomainType.HOSPITALITY.value: HOSPITALITY_CONFIG,
        DomainType.HEALTHCARE.value: HEALTHCARE_CONFIG,
        DomainType.RETAIL.value: RETAIL_CONFIG,
        DomainType.SERVICES.value: SERVICES_CONFIG,
        DomainType.SUPPORT.value: GENERAL_CONFIG,  # Support uses general as base
        
        # Backward compatibility aliases
        "restaurant": HOSPITALITY_CONFIG,
        "pharmacy": HEALTHCARE_CONFIG,
        "hotel": HOTEL_CONFIG,
    }
    
    @classmethod
    def get_domain(cls, domain_type: str) -> Optional[DomainConfig]:
        """Get domain configuration by type"""
        return cls._domains.get(domain_type.lower())
    
    @classmethod
    def list_domains(cls) -> List[Dict[str, str]]:
        """List all available domains"""
        return [
            {
                "type": domain.domain_type.value,
                "name": domain.display_name,
                "description": domain.description
            }
            for domain in cls._domains.values()
        ]
    
    @classmethod
    def detect_domain(cls, text: str, threshold: float = 0.3) -> Optional[DomainConfig]:
        """
        Auto-detect domain from text content (e.g., uploaded document).
        Returns the best matching domain based on keyword analysis.
        
        Args:
            text: Text to analyze
            threshold: Minimum match ratio required
            
        Returns:
            Best matching DomainConfig or None
        """
        text_lower = text.lower()
        words = set(text_lower.split())
        
        scores: Dict[str, float] = {}
        
        for domain_type, config in cls._domains.items():
            # Count keyword matches
            matches = sum(
                1 for keyword in config.detection_keywords 
                if keyword in text_lower or keyword in words
            )
            
            # Calculate score as ratio of matched keywords
            if config.detection_keywords:
                score = matches / len(config.detection_keywords)
                scores[domain_type] = score
        
        if not scores:
            return None
        
        # Get best match
        best_domain = max(scores, key=scores.get)
        best_score = scores[best_domain]
        
        logger.info(
            "Domain detection complete",
            scores=scores,
            best_domain=best_domain,
            best_score=best_score
        )
        
        if best_score >= threshold:
            return cls._domains[best_domain]
        
        return None
    
    @classmethod
    def get_function_templates(cls, domain_type: str) -> List[FunctionTemplate]:
        """Get function templates for a domain"""
        domain = cls.get_domain(domain_type)
        if domain:
            return domain.default_functions
        return []
    
    @classmethod
    def get_system_prompt(
        cls,
        domain_type: str,
        business_name: str,
        agent_name: str = "Assistant"
    ) -> Optional[str]:
        """
        Generate system prompt for a domain with placeholders filled.
        
        Args:
            domain_type: Type of business domain
            business_name: Name of the business
            agent_name: Name for the agent
            
        Returns:
            Formatted system prompt
        """
        domain = cls.get_domain(domain_type)
        if not domain:
            return None
        
        return domain.system_prompt_template.format(
            business_name=business_name,
            agent_name=agent_name
        )
    
    @classmethod
    def register_domain(cls, config: DomainConfig) -> None:
        """Register a custom domain configuration"""
        cls._domains[config.domain_type.value] = config
        logger.info(
            "Registered custom domain",
            domain_type=config.domain_type.value,
            display_name=config.display_name
        )
    
    @classmethod
    def validate_domain_data(
        cls,
        domain_type: str,
        available_data: List[str]
    ) -> Dict[str, Any]:
        """
        Validate that required data is available for a domain.
        
        Args:
            domain_type: Type of business domain
            available_data: List of available data types
            
        Returns:
            Validation result with missing required and optional data
        """
        domain = cls.get_domain(domain_type)
        if not domain:
            return {"valid": False, "error": f"Unknown domain: {domain_type}"}
        
        available_set = set(available_data)
        required_set = set(domain.required_data)
        optional_set = set(domain.optional_data)
        
        missing_required = required_set - available_set
        missing_optional = optional_set - available_set
        
        return {
            "valid": len(missing_required) == 0,
            "domain_type": domain_type,
            "missing_required": list(missing_required),
            "missing_optional": list(missing_optional),
            "available": list(available_set),
            "message": (
                "All required data available" if not missing_required
                else f"Missing required data: {', '.join(missing_required)}"
            )
        }


# Singleton access
_registry: Optional[DomainRegistry] = None


def get_domain_registry() -> DomainRegistry:
    """Get the domain registry singleton"""
    global _registry
    if _registry is None:
        _registry = DomainRegistry()
    return _registry
