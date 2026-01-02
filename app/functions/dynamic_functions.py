"""
Dynamic Function Implementations
Production-ready, domain-agnostic functions that work with any business knowledge base.
These functions replace hardcoded implementations with knowledge-base-backed operations.
"""

import json
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

from app.core.logging import get_logger
from app.services.voice_knowledge_service import get_voice_knowledge_service

logger = get_logger(__name__)


# ============================================
# IN-MEMORY STORAGE (Orders/Appointments)
# These are temporary - in production, use ConvexDB
# ============================================

@dataclass
class OrderStorage:
    """In-memory order storage with auto-cleanup"""
    orders: Dict[int, Dict] = field(default_factory=dict)
    next_id: int = 1
    
    def create(self, customer_name: str, items: List[Dict], total: float) -> Dict:
        order_id = self.next_id
        self.next_id += 1
        order = {
            "id": order_id,
            "customer": customer_name,
            "items": items,
            "total": total,
            "status": "preparing",
            "created_at": datetime.now().isoformat()
        }
        self.orders[order_id] = order
        return order
    
    def get(self, order_id: int) -> Optional[Dict]:
        return self.orders.get(order_id)


@dataclass
class AppointmentStorage:
    """In-memory appointment storage"""
    appointments: Dict[int, Dict] = field(default_factory=dict)
    next_id: int = 1
    
    def create(self, customer_name: str, date: str, time: str, details: str = "") -> Dict:
        appt_id = self.next_id
        self.next_id += 1
        appointment = {
            "id": appt_id,
            "customer": customer_name,
            "date": date,
            "time": time,
            "details": details,
            "status": "confirmed",
            "created_at": datetime.now().isoformat()
        }
        self.appointments[appt_id] = appointment
        return appointment


# Singleton instances
_order_storage = OrderStorage()
_appointment_storage = AppointmentStorage()


# ============================================
# DYNAMIC FUNCTION IMPLEMENTATIONS
# ============================================

class DynamicFunctions:
    """
    Knowledge-base-backed function implementations.
    All functions work with any organization's knowledge base.
    """
    
    def __init__(self, organization_id: str):
        self.organization_id = organization_id
        self.knowledge_service = get_voice_knowledge_service(organization_id)
    
    async def search_items(
        self,
        query: str
    ) -> Dict[str, Any]:
        """
        Search for items/products in the knowledge base.
        Uses pure semantic search for natural language understanding.
        
        Args:
            query: Search term (e.g., "vegetarian options", "chicken dishes")
            
        Returns:
            Structured response with matching items
        """
        start_time = time.time()
        
        try:
            result = await self.knowledge_service.search_items(
                query=query,
                limit=10
            )
            
            if result.get("found") and result.get("items"):
                items = result["items"]
                
                # Format for voice response
                if len(items) == 1:
                    item = items[0]
                    return {
                        "name": item["name"],
                        "price": f"${item['price']:.2f}",
                        "description": item["description"],
                        "category": item.get("category", ""),
                        "message": f"{item['name']} is ${item['price']:.2f}. {item['description']}"
                    }
                else:
                    # Multiple items
                    summary = []
                    for item in items[:4]:  # Limit for voice
                        summary.append(f"{item['name']} (${item['price']:.2f})")
                    
                    return {
                        "count": len(items),
                        "items": items[:4],
                        "message": f"Found {len(items)} items: {', '.join(summary)}"
                    }
            else:
                return {
                    "error": f"No items found matching '{query}'",
                    "message": "I couldn't find that item. Would you like to hear our categories?"
                }
                
        except Exception as e:
            logger.error(f"search_items failed: {e}")
            return {
                "error": str(e),
                "message": "I'm having trouble searching right now. Can you try again?"
            }
    
    async def get_business_info(
        self,
        info_type: str
    ) -> Dict[str, Any]:
        """
        Get business information like hours, location, policies.
        
        Args:
            info_type: Type of info (hours, location, contact, policies, features)
            
        Returns:
            Requested business information
        """
        try:
            result = await self.knowledge_service.get_business_info(info_type)
            
            if result.get("found"):
                if info_type == "hours":
                    hours = result.get("hours", {})
                    # Format nicely for voice
                    today = datetime.now().strftime("%A").lower()
                    today_hours = hours.get(today, "closed")
                    return {
                        "today": today_hours,
                        "all_hours": hours,
                        "message": f"Today we're open {today_hours}"
                    }
                
                elif info_type == "location":
                    return {
                        "address": result.get("address", ""),
                        "phone": result.get("phone", ""),
                        "message": f"We're located at {result.get('address', 'our location')}"
                    }
                
                elif info_type == "features":
                    features = result.get("features", [])
                    return {
                        "features": features,
                        "message": f"We offer: {', '.join(features)}"
                    }
                
                else:
                    return result
            else:
                return {
                    "message": "I don't have that specific information available."
                }
                
        except Exception as e:
            logger.error(f"get_business_info failed: {e}")
            return {"error": str(e)}
    
    async def place_order(
        self,
        customer_name: str,
        items: str
    ) -> Dict[str, Any]:
        """
        Place an order for items.
        Validates items against knowledge base and calculates total.
        
        Args:
            customer_name: Customer's name
            items: Comma-separated list of item names
            
        Returns:
            Order confirmation with ID and total
        """
        try:
            # Parse items
            item_names = [name.strip() for name in items.split(",")]
            
            order_items = []
            total_price = 0.0
            not_found = []
            
            # Validate each item against knowledge base
            for item_name in item_names:
                result = await self.knowledge_service.search_items(
                    query=item_name,
                    limit=1
                )
                
                if result.get("found") and result.get("items"):
                    item = result["items"][0]
                    order_items.append({
                        "name": item["name"],
                        "price": item["price"]
                    })
                    total_price += item["price"]
                else:
                    not_found.append(item_name)
            
            if not order_items:
                return {
                    "error": "No valid items found",
                    "not_found": not_found,
                    "message": f"I couldn't find: {', '.join(not_found)}. Please try again."
                }
            
            # Create order
            order = _order_storage.create(customer_name, order_items, total_price)
            
            result = {
                "order_id": order["id"],
                "customer": customer_name,
                "items": order_items,
                "total": f"${total_price:.2f}",
                "status": "preparing",
                "message": f"Order #{order['id']} placed! Total: ${total_price:.2f}"
            }
            
            if not_found:
                result["warnings"] = f"Could not find: {', '.join(not_found)}"
            
            logger.info(f"Order placed: #{order['id']} for {customer_name}, total ${total_price:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"place_order failed: {e}")
            return {
                "error": str(e),
                "message": "There was a problem placing your order. Please try again."
            }
    
    async def lookup_order(
        self,
        order_id: int
    ) -> Dict[str, Any]:
        """
        Look up an existing order by ID.
        
        Args:
            order_id: Order ID number
            
        Returns:
            Order details or error if not found
        """
        order = _order_storage.get(order_id)
        
        if order:
            items_text = ", ".join([i["name"] for i in order["items"]])
            return {
                "order_id": order_id,
                "customer": order["customer"],
                "items": order["items"],
                "total": f"${order['total']:.2f}",
                "status": order["status"],
                "message": f"Order #{order_id}: {items_text}. Total ${order['total']:.2f}. Status: {order['status']}"
            }
        else:
            return {
                "error": f"Order #{order_id} not found",
                "message": f"I couldn't find order number {order_id}. Please check the number."
            }
    
    async def make_appointment(
        self,
        customer_name: str,
        date: str,
        time: str,
        details: str = ""
    ) -> Dict[str, Any]:
        """
        Schedule an appointment or reservation.
        
        Args:
            customer_name: Customer's name
            date: Appointment date
            time: Appointment time
            details: Additional details (party size, service type, etc.)
            
        Returns:
            Confirmation with appointment ID
        """
        try:
            appointment = _appointment_storage.create(
                customer_name=customer_name,
                date=date,
                time=time,
                details=details
            )
            
            msg = f"Reservation #{appointment['id']} confirmed for {customer_name} on {date} at {time}"
            if details:
                msg += f" ({details})"
            
            logger.info(f"Appointment created: #{appointment['id']} for {customer_name}")
            
            return {
                "appointment_id": appointment["id"],
                "customer": customer_name,
                "date": date,
                "time": time,
                "details": details,
                "status": "confirmed",
                "message": msg
            }
            
        except Exception as e:
            logger.error(f"make_appointment failed: {e}")
            return {
                "error": str(e),
                "message": "There was a problem making your reservation. Please try again."
            }
    
    async def end_call(
        self,
        reason: str = "User request"
    ) -> Dict[str, Any]:
        """
        End the call.
        
        Args:
            reason: Reason for ending (optional)
            
        Returns:
            End call action
        """
        return {
            "action": "end_call",
            "message": "Call ended",
            "reason": reason
        }
    
    async def lookup_info(
        self,
        query: str
    ) -> Dict[str, Any]:
        """
        Universal lookup for any business information.
        Searches the entire knowledge base for policies, hours, services, etc.
        
        Args:
            query: What to look up (e.g., 'delivery policy', 'opening hours')
            
        Returns:
            Information from knowledge base
        """
        try:
            result = await self.knowledge_service.search_knowledge(
                query=query,
                limit=3
            )
            
            if result.get("found"):
                return {
                    "found": True,
                    "info": result.get("answer", ""),
                    "message": result.get("answer", "")
                }
            else:
                return {
                    "found": False,
                    "message": f"I don't have specific information about {query}. Would you like me to help with something else?"
                }
                
        except Exception as e:
            logger.error(f"lookup_info failed: {e}")
            return {
                "error": str(e),
                "message": "I'm having trouble looking that up. Please try again."
            }

# ============================================
# INTENT-BASED FUNCTION ROUTER
# ============================================

# Intent keywords for classification
INTENT_PATTERNS = {
    "search": ["get", "find", "search", "browse", "show", "list", "what", "menu", "item", "product", "service", "catalog", "available"],
    "book": ["book", "reserve", "appointment", "schedule", "reservation"],
    "order": ["order", "place", "buy", "purchase", "add", "cart"],
    "info": ["info", "hour", "location", "contact", "policy", "about", "address", "phone"],
    "transfer": ["transfer", "agent", "human", "speak", "escalate", "help"],
    "end": ["end", "hangup", "goodbye", "bye", "terminate", "close"]
}


def classify_intent(function_name: str) -> str:
    """
    Classify function intent based on name.
    Returns: 'search', 'book', 'order', 'info', 'transfer', 'end', or 'search' (default)
    """
    name_lower = function_name.lower()
    
    for intent, keywords in INTENT_PATTERNS.items():
        for keyword in keywords:
            if keyword in name_lower:
                return intent
    
    # Default to search (most common use case)
    return "search"


class UniversalFunctionRouter:
    """
    Routes ANY function call to appropriate handler based on intent.
    This is domain-agnostic - works for restaurants, clinics, hotels, etc.
    """
    
    def __init__(self, organization_id: str):
        self.organization_id = organization_id
        self.funcs = DynamicFunctions(organization_id)
    
    async def route(self, function_name: str, **kwargs) -> Dict[str, Any]:
        """
        Route a function call to the appropriate handler.
        
        Args:
            function_name: Name of the function (e.g., get_menu, get_services)
            **kwargs: Function arguments
            
        Returns:
            Function result
        """
        intent = classify_intent(function_name)
        
        logger.info(f"Routing function '{function_name}' → intent: {intent}")
        
        if intent == "search":
            # Extract search query - category is now part of semantic search
            query = kwargs.get("query") or kwargs.get("category") or kwargs.get("search") or kwargs.get("item") or ""
            return await self.funcs.search_items(query=str(query) if query else "menu")
        
        elif intent == "book":
            customer = kwargs.get("customer_name") or kwargs.get("name") or kwargs.get("customer") or "Guest"
            date = kwargs.get("date") or kwargs.get("appointment_date") or "today"
            time = kwargs.get("time") or kwargs.get("appointment_time") or ""
            details = kwargs.get("details") or kwargs.get("notes") or kwargs.get("service") or ""
            return await self.funcs.make_appointment(customer_name=customer, date=date, time=time, details=details)
        
        elif intent == "order":
            customer = kwargs.get("customer_name") or kwargs.get("name") or kwargs.get("customer") or "Guest"
            items = kwargs.get("items") or kwargs.get("item") or kwargs.get("order") or ""
            return await self.funcs.place_order(customer_name=customer, items=items)
        
        elif intent == "info":
            info_type = kwargs.get("info_type") or kwargs.get("type") or "general"
            # Try to infer info type from function name
            if "hour" in function_name.lower():
                info_type = "hours"
            elif "location" in function_name.lower() or "address" in function_name.lower():
                info_type = "location"
            elif "contact" in function_name.lower() or "phone" in function_name.lower():
                info_type = "contact"
            return await self.funcs.get_business_info(info_type=info_type)
        
        elif intent == "transfer":
            reason = kwargs.get("reason") or "User requested transfer"
            return await self.funcs.end_call(reason=f"Transfer: {reason}")
        
        elif intent == "end":
            reason = kwargs.get("reason") or "Call ended"
            return await self.funcs.end_call(reason=reason)
        
        else:
            # Fallback to search
            return await self.funcs.search_items(query=function_name)


def get_dynamic_function_map(organization_id: str) -> Dict[str, callable]:
    """
    Get function map for an organization.
    Returns a UNIVERSAL ROUTER that handles ANY function name.
    
    This is domain-agnostic - the same router works for:
    - Restaurants (get_menu, place_order)
    - Clinics (get_services, book_appointment)
    - Hotels (check_availability, make_reservation)
    - Any other business type
    
    Args:
        organization_id: Organization ID
        
    Returns:
        Dictionary with universal router that handles any function
    """
    router = UniversalFunctionRouter(organization_id)
    funcs = DynamicFunctions(organization_id)
    
    # Create a wrapper that routes any unknown function
    async def universal_handler(function_name: str, **kwargs):
        return await router.route(function_name, **kwargs)
    
    # Return a dict with common function names mapped,
    # but any unknown function will be routed dynamically
    return UniversalFunctionMap(router, funcs)


class UniversalFunctionMap(dict):
    """
    A dict-like object that routes any function call.
    Known functions go to direct handlers; unknown functions use intent routing.
    """
    
    def __init__(self, router: UniversalFunctionRouter, funcs: DynamicFunctions):
        self.router = router
        self.funcs = funcs
        
        # Pre-populate with common function names for efficiency
        super().__init__({
            "search_items": funcs.search_items,
            "get_business_info": funcs.get_business_info,
            "place_order": funcs.place_order,
            "lookup_order": funcs.lookup_order,
            "make_appointment": funcs.make_appointment,
            "end_call": funcs.end_call,
            "lookup_info": funcs.lookup_info,  # Universal knowledge lookup
        })
    
    def __contains__(self, key):
        # ALWAYS return True - we can handle ANY function via routing
        return True
    
    def __getitem__(self, key):
        # Check if it's a known function first
        if super().__contains__(key):
            return super().__getitem__(key)
        
        # Otherwise, create a dynamic handler for this function name
        async def dynamic_handler(**kwargs):
            return await self.router.route(key, **kwargs)
        
        return dynamic_handler
    
    def get(self, key, default=None):
        return self[key]
    
    def keys(self):
        # Return base keys plus indicator that we handle more
        return list(super().keys()) + ["<any_function>"]


# ============================================
# LEGACY COMPATIBILITY
# ============================================

FUNCTION_MAP = None

def get_legacy_function_map() -> Dict[str, callable]:
    """Get legacy function map (for backward compatibility)."""
    global FUNCTION_MAP
    if FUNCTION_MAP is None:
        FUNCTION_MAP = get_dynamic_function_map("default")
    return FUNCTION_MAP
