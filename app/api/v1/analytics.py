"""
Analytics API Endpoints
Provides call analytics and metrics using ConvexDB.
"""
import os
import json
from fastapi import APIRouter, Depends, Query

from datetime import datetime, timedelta
from typing import Optional

from app.core.convex_client import get_convex_client

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/")
async def get_analytics_overview(
    tenant_id: Optional[int] = Query(None)
):
    """
    Get analytics overview
    Shows today's stats and current system status
    """
    client = get_convex_client()
    org_id = str(tenant_id) if tenant_id else "default"
    stats = await client.query("analytics:getTodayStats", {
        "organizationId": org_id
    })
    return {
        "status": "success",
        "data": {
            "today": stats.get("today", {}),
            "timestamp": datetime.utcnow().isoformat()
        }
    }


@router.get("/sessions")
async def get_recent_sessions(
    tenant_id: Optional[int] = Query(None),
    limit: int = Query(default=50, le=200, description="Max sessions to return")
):
    """
    Get recent call sessions
    Returns list of recent calls with details
    """
    client = get_convex_client()
    org_id = str(tenant_id) if tenant_id else "default"
    sessions = await client.query("callSessions:getRecentSessions", {
        "organizationId": org_id,
        "limit": limit
    })
    
    return {
        "status": "success",
        "data": {
            "sessions": [
                {
                    "id": s.get("sessionId"),
                    "call_sid": s.get("callSid"),
                    "call_type": s.get("callType"),
                    "agent_type": s.get("agentType"),
                    "phone_number": s.get("phoneNumber"),
                    "status": s.get("status"),
                    "started_at": datetime.fromtimestamp(s.get("startedAt", 0) / 1000).isoformat() if s.get("startedAt") else None,
                    "ended_at": datetime.fromtimestamp(s.get("endedAt", 0) / 1000).isoformat() if s.get("endedAt") else None,
                    "duration_seconds": s.get("durationSeconds"),
                }
                for s in (sessions or [])
            ],
            "count": len(sessions or [])
        }
    }


@router.get("/sessions/{session_id}")
async def get_session_details(
    session_id: str,
    tenant_id: Optional[int] = Query(None)
):
    """
    Get detailed information about a specific call session
    Includes conversation transcript
    """
    client = get_convex_client()
    result = await client.query("analytics:getSessionDetails", {
        "sessionId": session_id
    })
    
    if not result or not result.get("session"):
        return {
            "status": "error",
            "message": f"Session {session_id} not found"
        }
    
    session = result.get("session", {})
    interactions = result.get("interactions", [])
    
    return {
        "status": "success",
        "data": {
            "session": {
                "id": session.get("sessionId"),
                "call_sid": session.get("callSid"),
                "call_type": session.get("callType"),
                "agent_type": session.get("agentType"),
                "phone_number": session.get("phoneNumber"),
                "status": session.get("status"),
                "started_at": datetime.fromtimestamp(session.get("startedAt", 0) / 1000).isoformat() if session.get("startedAt") else None,
                "ended_at": datetime.fromtimestamp(session.get("endedAt", 0) / 1000).isoformat() if session.get("endedAt") else None,
                "duration_seconds": session.get("durationSeconds"),
                "config": json.loads(session.get("config", "{}")) if isinstance(session.get("config"), str) else session.get("config"),
            },
            "interactions": [
                {
                    "id": i.get("_id"),
                    "type": i.get("interactionType"),
                    "timestamp": datetime.fromtimestamp(i.get("timestamp", 0) / 1000).isoformat() if i.get("timestamp") else None,
                    "user_input": i.get("userInput"),
                    "agent_response": i.get("agentResponse"),
                    "function_name": i.get("functionName"),
                    "function_params": json.loads(i.get("functionParams", "null")) if isinstance(i.get("functionParams"), str) else i.get("functionParams"),
                    "function_result": json.loads(i.get("functionResult", "null")) if isinstance(i.get("functionResult"), str) else i.get("functionResult"),
                }
                for i in interactions
            ]
        }
    }


@router.get("/active")
async def get_active_calls(
    tenant_id: Optional[int] = Query(None)
):
    """
    Get count of currently active calls
    Useful for monitoring concurrent load
    """
    client = get_convex_client()
    result = await client.query("analytics:getActiveCallsCount", {})
    
    return {
        "status": "success",
        "data": {
            "active_calls": int(result.get("activeCallsCount", 0)),
            "max_capacity": int(result.get("maxCapacity", 20)),
            "available": int(result.get("available", 20)),
            "timestamp": datetime.utcnow().isoformat()
        }
    }


@router.get("/breakdown")
async def get_agent_breakdown(
    days: int = Query(default=7, le=30, description="Days to analyze"),
    tenant_id: Optional[int] = Query(None)
):
    """
    Get breakdown of calls by agent type
    Shows which types of agents are used most
    """
    client = get_convex_client()
    org_id = str(tenant_id) if tenant_id else "default"
    breakdown = await client.query("analytics:getAgentBreakdown", {
        "organizationId": org_id
    })
    
    return {
        "status": "success",
        "data": {
            "period_days": days,
            "agent_types": breakdown or {},
            "total": sum((breakdown or {}).values())
        }
    }


@router.get("/date-range")
async def get_sessions_by_date(
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    tenant_id: Optional[int] = Query(None)
):
    """
    Get call sessions within a date range
    """
    # Default to last 7 days
    if not start_date:
        start = datetime.utcnow() - timedelta(days=7)
    else:
        start = datetime.fromisoformat(start_date)
    
    if not end_date:
        end = datetime.utcnow()
    else:
        end = datetime.fromisoformat(end_date)
    
    client = get_convex_client()
    org_id = str(tenant_id) if tenant_id else "default"
    
    # For now, get all recent sessions and filter client-side
    # TODO: Add getByDateRange Convex function for better performance
    sessions = await client.query("callSessions:getRecentSessions", {
        "organizationId": org_id,
        "limit": 500
    })
    
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    
    filtered = [
        s for s in (sessions or [])
        if s.get("startedAt") and start_ms <= s.get("startedAt") <= end_ms
    ]
    
    return {
        "status": "success",
        "data": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "sessions": [
                {
                    "id": s.get("sessionId"),
                    "agent_type": s.get("agentType"),
                    "status": s.get("status"),
                    "started_at": datetime.fromtimestamp(s.get("startedAt", 0) / 1000).isoformat() if s.get("startedAt") else None,
                    "duration_seconds": s.get("durationSeconds"),
                }
                for s in filtered
            ],
            "count": len(filtered)
        }
    }
