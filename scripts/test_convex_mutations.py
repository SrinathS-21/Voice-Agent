"""
Test Convex endCall mutation and verify it's working
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
import json

async def test_end_call_mutation():
    """Test the endCall mutation with one of the existing active sessions"""
    client = get_convex_client()
    
    print("\n" + "="*60)
    print("TESTING CONVEX endCall MUTATION")
    print("="*60 + "\n")
    
    # Get an active session to test with
    sessions = await client.query('callSessions:listByOrganization', {
        'organizationId': 'js710fpdzbnhrb8ttvyc4crghn7y9qng'
    })
    
    if not sessions:
        print("❌ No sessions found to test with")
        return
    
    # Find an active session
    test_session = None
    for s in sessions:
        if s.get('status') == 'active':
            test_session = s
            break
    
    if not test_session:
        print("❌ No active sessions found to test with")
        return
    
    session_id = test_session.get('sessionId')
    print(f"📝 Testing with session: {session_id}")
    print(f"   Current status: {test_session.get('status')}")
    print(f"   Current duration: {test_session.get('durationSeconds')}")
    
    # Test conversation JSON
    test_conversation = {
        "session_id": session_id,
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ],
        "test": True
    }
    
    # Try to call endCall mutation
    print("\n🔧 Calling endCall mutation...")
    try:
        result = await client.mutation("callSessions:endCall", {
            "sessionId": session_id,
            "durationSeconds": 45,
            "endedAt": 1735920000000,  # Test timestamp
            "status": "completed",
            "config": json.dumps(test_conversation)
        })
        
        print(f"✅ endCall mutation succeeded!")
        print(f"   Result: {result}")
        
        # Verify the update
        print("\n🔍 Verifying update...")
        updated_session = await client.query("callSessions:getBySessionId", {
            "sessionId": session_id
        })
        
        if updated_session:
            print(f"✅ Session updated successfully:")
            print(f"   Status: {updated_session.get('status')}")
            print(f"   Duration: {updated_session.get('durationSeconds')}s")
            print(f"   EndedAt: {updated_session.get('endedAt')}")
            print(f"   Has config: {'✅' if updated_session.get('config') else '❌'}")
            
            if updated_session.get('config'):
                config_data = json.loads(updated_session.get('config'))
                print(f"   Config preview: {list(config_data.keys())}")
        else:
            print(f"⚠️  Could not retrieve updated session")
            
    except Exception as e:
        print(f"❌ endCall mutation failed: {e}")
        import traceback
        traceback.print_exc()

async def test_interaction_logging():
    """Test callInteractions logging"""
    client = get_convex_client()
    
    print("\n" + "="*60)
    print("TESTING CALL INTERACTIONS LOGGING")
    print("="*60 + "\n")
    
    test_session_id = "test-session-" + str(int(asyncio.get_event_loop().time()))
    
    # Test user message
    print(f"📝 Logging user message for session: {test_session_id}")
    try:
        result = await client.mutation("callInteractions:logUserMessage", {
            "sessionId": test_session_id,
            "userInput": "Hello, this is a test message"
        })
        print(f"✅ User message logged: {result}")
    except Exception as e:
        print(f"❌ User message logging failed: {e}")
    
    # Test agent response
    print(f"\n📝 Logging agent response...")
    try:
        result = await client.mutation("callInteractions:logAgentResponse", {
            "sessionId": test_session_id,
            "agentResponse": "Hello! This is a test response."
        })
        print(f"✅ Agent response logged: {result}")
    except Exception as e:
        print(f"❌ Agent response logging failed: {e}")
    
    # Test function call
    print(f"\n📝 Logging function call...")
    try:
        result = await client.mutation("callInteractions:logFunctionCall", {
            "sessionId": test_session_id,
            "functionName": "test_function",
            "functionParams": json.dumps({"param1": "value1"}),
            "functionResult": json.dumps({"result": "success"})
        })
        print(f"✅ Function call logged: {result}")
    except Exception as e:
        print(f"❌ Function call logging failed: {e}")
    
    # Retrieve interactions
    print(f"\n🔍 Retrieving logged interactions...")
    try:
        interactions = await client.query("callInteractions:getBySessionId", {
            "sessionId": test_session_id
        })
        print(f"✅ Retrieved {len(interactions)} interactions:")
        for i in interactions:
            print(f"   - [{i.get('interactionType')}] {i.get('userInput') or i.get('agentResponse') or i.get('functionName')}")
    except Exception as e:
        print(f"❌ Failed to retrieve interactions: {e}")

async def main():
    """Run all tests"""
    await test_end_call_mutation()
    await test_interaction_logging()
    
    print("\n" + "="*60)
    print("TESTS COMPLETE")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
