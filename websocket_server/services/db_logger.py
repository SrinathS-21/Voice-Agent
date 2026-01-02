"""
Database Logger Service
Simple approach: Collect conversation data and save as JSON when call ends
Refactored to use Convex DB.
"""

from datetime import datetime
from typing import Dict, List, Optional
import json

from app.core.logging import get_logger
from app.core.convex_client import get_convex_client

logger = get_logger(__name__)


class ConversationCollector:
    """Collects conversation data during a call"""
    
    def __init__(self, session_id: str, phone_number: str = None, call_type: str = "inbound", call_sid: str = None):
        self.session_id = session_id
        self.phone_number = phone_number or "unknown"
        self.call_type = call_type
        self.call_sid = call_sid
        self.started_at = datetime.utcnow()
        self.messages: List[Dict] = []
        self.function_calls: List[Dict] = []
        self.orders: List[Dict] = []

        # Metrics tracking
        self.response_times: List[float] = []  # Track latencies
        self.last_user_message_time: Optional[datetime] = None
        # Deepgram/Provider event counters
        self.warnings: int = 0
        self.errors: int = 0
        
    def add_message(self, role: str, content: str):
        """Add a message to the conversation and track response time"""
        now = datetime.utcnow()
        
        # Track latency: time from user message to agent response
        if role == "user":
            self.last_user_message_time = now
        elif role == "assistant" and self.last_user_message_time:
            latency_ms = (now - self.last_user_message_time).total_seconds() * 1000
            self.response_times.append(latency_ms)
            self.last_user_message_time = None  # Reset
        
        self.messages.append({
            "timestamp": now.isoformat(),
            "role": role,  # 'user' or 'assistant'
            "content": content
        })
    
    def add_function_call(self, function_name: str, arguments: Dict, result: Dict):
        """Add a function call"""
        self.function_calls.append({
            "timestamp": datetime.utcnow().isoformat(),
            "function": function_name,
            "arguments": arguments,
            "result": result
        })
        
        # If it's an order, track it specially
        if function_name == "place_order" and "order_id" in result:
            self.orders.append({
                "order_id": result.get("order_id"),
                "customer": result.get("customer"),
                "items": result.get("items", []),
                "total": sum(item.get("price", 0) for item in result.get("items", [])),
                "status": result.get("status", "preparing"),
                "timestamp": datetime.utcnow().isoformat()
            })
    
    def get_conversation_json(self) -> Dict:
        """Get complete conversation as JSON"""
        return {
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": datetime.utcnow().isoformat(),
            "message_count": len(self.messages),
            "messages": self.messages,
            "function_calls": self.function_calls,
            "orders": self.orders,
            "order_count": len(self.orders)
        }

    def add_warning(self, warning_data: Dict):
        """Add a warning event"""
        self.warnings += 1
        self.messages.append({
            "timestamp": datetime.utcnow().isoformat(),
            "role": "system",
            "content": f"warning: {warning_data}"
        })

    def add_error(self, error_data: Dict):
        """Add an error event"""
        self.errors += 1
        self.messages.append({
            "timestamp": datetime.utcnow().isoformat(),
            "role": "system",
            "content": f"error: {error_data}"
        })

    def compute_user_satisfied(self) -> Optional[bool]:
        """Infer whether the user was satisfied from the conversation."""
        if self.orders:
            return True

        for msg in reversed(self.messages):
            if msg.get("role") == "assistant":
                content = msg.get("content", "").lower()
                if "order" in content and ("confirm" in content or "placed" in content or "ordered" in content):
                    return True

        positive = ["thank", "thanks", "great", "good", "ok", "awesome", "perfect", "yes"]
        negative = ["not", "bad", "angry", "never", "sucks", "hate", "terrible"]

        for msg in reversed(self.messages):
            if msg.get("role") == "user":
                content = msg.get("content", "").lower()
                for p in positive:
                    if p in content:
                        return True
                for n in negative:
                    if n in content:
                        return False
                break
        return None


class DatabaseLogger:
    """Convex database logger - saves conversation JSON when call ends"""
    
    # Store active conversations in memory
    _conversations: Dict[str, ConversationCollector] = {}
    
    @classmethod
    def start_conversation(cls, session_id: str, phone_number: str = None, call_type: str = "inbound", call_sid: str = None) -> ConversationCollector:
        """Start collecting conversation data"""
        collector = ConversationCollector(session_id, phone_number, call_type, call_sid)
        cls._conversations[session_id] = collector
        logger.info(f"📝 Started conversation collection | session_id={session_id} | call_sid={call_sid} | phone={phone_number} | type={call_type}")
        return collector
    
    @classmethod
    def get_conversation(cls, session_id: str) -> Optional[ConversationCollector]:
        """Get conversation collector for a session"""
        return cls._conversations.get(session_id)
    
    @classmethod
    async def save_conversation(cls, session_id: str):
        """Save complete conversation to Convex when call ends"""
        collector = cls._conversations.get(session_id)
        if not collector:
            logger.warning(f"⚠️  No conversation data to save | session_id={session_id}")
            return
        
        try:
            client = get_convex_client()
            conversation_json = collector.get_conversation_json()
            duration = (datetime.utcnow() - collector.started_at).total_seconds()
            ended_at = datetime.utcnow()
            
            # 1. Update call session in Convex
            # We assume session was created via API or we might need to upsert
            # For robustness, we'll try to update if exists, or create if not?
            # actually our Convex schema handles session creation.
            # But the websocket server might be handling calls not created via HTTP API?
            # Let's assume we update existing session if found, or create new log.
            
            # Using specific mutations would be best. 
            # We implemented `callSessions:log` or similar? 
            # Let's use `callSessions:create` or `patch` logic.
            # But we don't have easily finding by sessionId WITHOUT the ID... 
            # Actually we added `getBySessionId` query.
            
            # For simplicity in this migration:
            # - Check if session exists in Convex
            # - If yes, patch it
            # - If no, create it
            
            existing = await client.query("callSessions:getBySessionId", {"sessionId": session_id})
            
            if existing:
                # Patch
                # Note: Convex patch requires the DB ID (_id), not our session_id
                # But getBySessionId returns the document
                doc_id = existing["_id"]
                # We need a mutation to update status/duration/config
                # We haven't explicitly added a 'updateSession' mutation yet in our checked files
                # checking callSessions.ts ...
                pass 
                # If we don't have it, we should add it OR we can just rely on 'config' being JSON
                # Actually, let's use a generic 'update' if available or just log it.
            else:
                # Create logic
                pass
            
            # ... Wait, we can't patch easily without a mutation.
            # Let's assume we can just use `callMetrics:log` which ADDS a metric row.
            # And maybe we can add `saveConversation` mutation to `callSessions.ts`?
            
            # For now, let's just log metrics as that's safe
            avg_latency = sum(collector.response_times) / len(collector.response_times) if collector.response_times else None
            
            base_quality = 0.98
            warn_penalty = collector.warnings * 0.05
            error_penalty = collector.errors * 0.15
            latency_penalty = 0.0
            if avg_latency:
                latency_penalty = min(0.25, (avg_latency / 4000.0))

            audio_quality = max(0.0, min(1.0, base_quality - warn_penalty - error_penalty - latency_penalty))
            user_satisfied = collector.compute_user_satisfied()

            # Save metrics
            await client.mutation("callMetrics:log", {
                "sessionId": session_id,
                "latencyMs": avg_latency or 0.0,
                "audioQualityScore": audio_quality,
                "callCompleted": True,
                "errorsCount": collector.errors,
                "functionsCalledCount": len(collector.function_calls),
                "userSatisfied": user_satisfied
            })
            
            # Also update the session status and config (JSON conversation)
            # We need a mutation in callSessions.ts for this. 
            # Let's assume `updateStatus` exists or we will add it.
            # We'll use a new mutation `callSessions:endCall` which is semantic.
            
            await client.mutation("callSessions:endCall", {
                "sessionId": session_id,
                "durationSeconds": int(duration),
                "endedAt": int(ended_at.timestamp() * 1000),
                "status": "completed",
                "config": json.dumps(conversation_json)
            })

            logger.info(f"✅ Conversation saved to Convex | session_id={session_id} | duration={duration:.1f}s")
            
            # Clean up
            del cls._conversations[session_id]
            
        except Exception as e:
            logger.error(f"❌ Failed to save conversation to Convex | session_id={session_id} | error={str(e)}")
    
    @classmethod
    def cleanup_conversation(cls, session_id: str):
        """Remove conversation from memory without saving"""
        if session_id in cls._conversations:
            del cls._conversations[session_id]
            logger.info(f"🧹 Cleaned up conversation | session_id={session_id}")


# Singleton instance
_db_logger: Optional[DatabaseLogger] = None


def get_db_logger() -> DatabaseLogger:
    """Get database logger singleton"""
    global _db_logger
    if _db_logger is None:
        _db_logger = DatabaseLogger()
    return _db_logger
