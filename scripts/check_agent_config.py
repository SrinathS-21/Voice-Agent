"""
Check why agents table is empty and verify phone/agent configuration
"""
import asyncio
import sys
import os
from pathlib import Path

# Set Convex URL
os.environ['CONVEX_URL'] = 'https://strong-warbler-592.convex.cloud'

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.convex_client import get_convex_client

async def check_configuration():
    """Check the full configuration chain"""
    client = get_convex_client()
    
    print("\n" + "="*60)
    print("CHECKING AGENT CONFIGURATION")
    print("="*60 + "\n")
    
    # Get organization
    orgs = await client.query("organizations:listAll", {})
    if not orgs:
        print("❌ No organizations found!")
        return
    
    org = orgs[0]
    org_id = org.get('_id')
    print(f"✅ Organization: {org.get('name')}")
    print(f"   ID: {org_id}")
    
    # Check agents
    print(f"\n📋 Checking agents for organization...")
    agents = await client.query("agents:listByOrganization", {"organizationId": org_id})
    
    if not agents or len(agents) == 0:
        print(f"⚠️  No agents found for this organization")
        print(f"   This is why calls might not work properly!")
        print(f"\n💡 You need to create an agent via the API:")
        print(f"   POST /api/v1/agents/")
        print(f"   with body containing agent configuration")
    else:
        print(f"✅ Found {len(agents)} agents:")
        for agent in agents:
            print(f"   - {agent.get('name')} (ID: {agent.get('_id')})")
            print(f"     Type: {agent.get('agentType')}")
    
    # Check phone configs
    print(f"\n📞 Checking phone configurations...")
    phones = await client.query("phoneConfigs:listAll", {})
    
    if not phones:
        print(f"❌ No phone configurations found!")
    else:
        print(f"✅ Found {len(phones)} phone configs:")
        for phone in phones:
            phone_num = phone.get('phoneNumber')
            agent_id = phone.get('agentId')
            org_id_from_phone = phone.get('organizationId')
            
            print(f"\n   Phone: {phone_num}")
            print(f"   Agent ID: {agent_id or '⚠️ NOT SET'}")
            print(f"   Organization ID: {org_id_from_phone or '⚠️ NOT SET'}")
            
            if agent_id:
                # Try to get agent details
                # We don't have a direct get by ID, but we can check if it exists in our agents list
                agent_found = any(a.get('_id') == agent_id for a in agents) if agents else False
                if agent_found:
                    print(f"   Agent exists: ✅")
                else:
                    print(f"   Agent exists: ❌ (Agent {agent_id} not found)")
            else:
                print(f"   ⚠️  WARNING: Phone has no agent assigned!")
    
    # Check call sessions
    print(f"\n📊 Checking call sessions...")
    sessions = await client.query('callSessions:listByOrganization', {'organizationId': org_id})
    
    if sessions:
        print(f"✅ Found {len(sessions)} call sessions")
        
        # Count by status
        active = sum(1 for s in sessions if s.get('status') == 'active')
        completed = sum(1 for s in sessions if s.get('status') == 'completed')
        
        print(f"   Active: {active}")
        print(f"   Completed: {completed}")
        
        # Show latest session
        if sessions:
            latest = sessions[-1]
            print(f"\n   Latest session:")
            print(f"   - Session ID: {latest.get('sessionId')}")
            print(f"   - Status: {latest.get('status')}")
            print(f"   - Phone: {latest.get('phoneNumber')}")
            print(f"   - Agent ID: {latest.get('agentId') or 'Not set'}")
            print(f"   - Started: {latest.get('startedAt')}")
    else:
        print(f"⚠️  No call sessions found")
    
    print("\n" + "="*60)
    print("CONFIGURATION CHECK COMPLETE")
    print("="*60 + "\n")
    
    # Provide recommendations
    print("\n💡 RECOMMENDATIONS:")
    if not agents or len(agents) == 0:
        print("   1. Create an agent using the API:")
        print("      POST /api/v1/agents/ with agent configuration")
    if phones:
        for phone in phones:
            if not phone.get('agentId'):
                print(f"   2. Assign agent to phone {phone.get('phoneNumber')}:")
                print(f"      PATCH /api/v1/phone-configs/{phone.get('phoneNumber')}")

if __name__ == "__main__":
    asyncio.run(check_configuration())
