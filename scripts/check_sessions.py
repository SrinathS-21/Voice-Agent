import asyncio
import sys
import os
from pathlib import Path

# Set Convex URL
os.environ['CONVEX_URL'] = 'https://strong-warbler-592.convex.cloud'

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.convex_client import get_convex_client

async def check_sessions():
    client = get_convex_client()
    sessions = await client.query('callSessions:listByOrganization', {'organizationId': 'js710fpdzbnhrb8ttvyc4crghn7y9qng'})
    
    print(f"\nTotal sessions: {len(sessions)}")
    
    # Count by status
    completed = [s for s in sessions if s.get('status') == 'completed']
    active = [s for s in sessions if s.get('status') == 'active']
    
    print(f"Completed: {len(completed)}")
    print(f"Active: {len(active)}")
    
    print("\nLast 5 sessions:")
    print("-" * 80)
    
    for s in sessions[-5:]:
        status = s.get('status')
        duration = s.get('durationSeconds')
        has_config = '✅' if s.get('config') else '❌'
        print(f"{s.get('sessionId')[:20]}... | Status: {status} | Duration: {duration}s | Config: {has_config}")
    
    if completed:
        print("\nCompleted sessions:")
        print("-" * 80)
        for s in completed:
            print(f"{s.get('sessionId')} | Duration: {s.get('durationSeconds')}s | Has config: {'✅' if s.get('config') else '❌'}")

if __name__ == "__main__":
    asyncio.run(check_sessions())
