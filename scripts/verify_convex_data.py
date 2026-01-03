"""
Verify Convex Database Data
Checks if data is being saved correctly to all tables
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.convex_client import get_convex_client
from app.core.logging import get_logger

logger = get_logger(__name__)


async def verify_tables():
    """Verify data in Convex tables"""
    client = get_convex_client()
    
    print("\n" + "="*60)
    print("CONVEX DATABASE VERIFICATION")
    print("="*60 + "\n")
    
    # Check organizations
    try:
        orgs = await client.query("organizations:listAll", {})
        print(f"✅ Organizations: {len(orgs) if orgs else 0} records")
        if orgs and len(orgs) > 0:
            print(f"   First org: {orgs[0].get('name')} ({orgs[0].get('_id')})")
    except Exception as e:
        print(f"❌ Organizations: Error - {e}")
    
    # Check phoneConfigs
    try:
        phones = await client.query("phoneConfigs:listAll", {})
        print(f"✅ Phone Configs: {len(phones) if phones else 0} records")
        if phones and len(phones) > 0:
            print(f"   First phone: {phones[0].get('phoneNumber')} → Agent: {phones[0].get('agentId')}")
    except Exception as e:
        print(f"❌ Phone Configs: Error - {e}")
    
    # Check agents - need orgId, so skip for now or use first org
    try:
        orgs = await client.query("organizations:listAll", {})
        if orgs and len(orgs) > 0:
            org_id = orgs[0].get('_id')
            agents = await client.query("agents:listByOrganization", {"organizationId": org_id})
            print(f"✅ Agents: {len(agents) if agents else 0} records")
            if agents and len(agents) > 0:
                print(f"   First agent: {agents[0].get('name')}")
        else:
            print(f"⚠️  Agents: No organizations to query")
    except Exception as e:
        print(f"❌ Agents: Error - {e}")
    
    # Check callSessions
    try:
        orgs = await client.query("organizations:listAll", {})
        if orgs and len(orgs) > 0:
            org_id = orgs[0].get('_id')
            sessions = await client.query("callSessions:listByOrganization", {"organizationId": org_id})
            print(f"✅ Call Sessions: {len(sessions) if sessions else 0} records")
            if sessions and len(sessions) > 0:
                latest = sessions[0]
                print(f"   Latest: {latest.get('sessionId')} | Status: {latest.get('status')} | Duration: {latest.get('durationSeconds')}s")
                has_config = latest.get('config') is not None
                print(f"   Has conversation JSON: {'✅' if has_config else '❌'}")
        else:
            print(f"⚠️  Call Sessions: No organizations to query")
    except Exception as e:
        print(f"❌ Call Sessions: Error - {e}")
    
    # Check callMetrics - no list query, skip
    print(f"⚠️  Call Metrics: No list query available")
    
    # Check callInteractions - no list query, skip
    print(f"⚠️  Call Interactions: No list query available")
    
    # Check documents (RAG)
    try:
        orgs = await client.query("organizations:listAll", {})
        if orgs and len(orgs) > 0:
            org_id = orgs[0].get('_id')
            docs = await client.query("documents:listByOrganization", {"organizationId": org_id})
            print(f"✅ Documents: {len(docs) if docs else 0} records")
            if docs and len(docs) > 0:
                print(f"   First doc: {docs[0].get('title')} | Chunks: {docs[0].get('chunkCount')}")
        else:
            print(f"⚠️  Documents: No organizations to query")
    except Exception as e:
        print(f"❌ Documents: Error - {e}")
    
    # Check analytics - no query found, skip
    print(f"⚠️  Analytics: No list query available")
    
    print("\n" + "="*60)
    print("VERIFICATION COMPLETE")
    print("="*60 + "\n")


async def check_specific_session(session_id: str):
    """Check data for a specific session"""
    client = get_convex_client()
    
    print(f"\nChecking session: {session_id}")
    print("-" * 60)
    
    # Get session
    try:
        session = await client.query("callSessions:getBySessionId", {"sessionId": session_id})
        if session:
            print(f"✅ Session found:")
            print(f"   Status: {session.get('status')}")
            print(f"   Duration: {session.get('durationSeconds')}s")
            print(f"   Started: {session.get('startedAt')}")
            print(f"   Ended: {session.get('endedAt')}")
            print(f"   Has conversation JSON: {'✅' if session.get('config') else '❌'}")
        else:
            print(f"❌ Session not found")
    except Exception as e:
        print(f"❌ Error fetching session: {e}")
    
    # Get metrics
    try:
        metrics_list = await client.query("callMetrics:getBySessionId", {"sessionId": session_id})
        if metrics_list and len(metrics_list) > 0:
            metrics = metrics_list[0]
            print(f"✅ Metrics found:")
            print(f"   Latency: {metrics.get('latencyMs'):.1f}ms")
            print(f"   Quality: {metrics.get('audioQualityScore'):.2f}")
            print(f"   Errors: {metrics.get('errorsCount')}")
            print(f"   Functions called: {metrics.get('functionsCalledCount')}")
            print(f"   User satisfied: {metrics.get('userSatisfied')}")
        else:
            print(f"⚠️  No metrics found")
    except Exception as e:
        print(f"❌ Error fetching metrics: {e}")
    
    # Get interactions
    try:
        interactions = await client.query("callInteractions:getBySessionId", {"sessionId": session_id})
        if interactions:
            print(f"✅ Interactions found: {len(interactions)} messages")
            for i in interactions[:5]:  # Show first 5
                print(f"   [{i.get('interactionType')}] {i.get('userInput') or i.get('agentResponse') or i.get('functionName')}")
        else:
            print(f"⚠️  No interactions found")
    except Exception as e:
        print(f"❌ Error fetching interactions: {e}")


async def main():
    """Main entry point"""
    import sys
    
    if len(sys.argv) > 1:
        # Check specific session
        session_id = sys.argv[1]
        await check_specific_session(session_id)
    else:
        # Verify all tables
        await verify_tables()


if __name__ == "__main__":
    asyncio.run(main())
