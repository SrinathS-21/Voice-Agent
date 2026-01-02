"""Test dish searches to verify knowledge base coverage."""
import asyncio
import os
os.environ['CONVEX_URL'] = 'https://strong-warbler-592.convex.cloud'

from app.services.voice_knowledge_service import get_voice_knowledge_service

async def main():
    org_id = 'js710fpdzbnhrb8ttvyc4crghn7y9qng'
    service = get_voice_knowledge_service(org_id)
    
    print("=" * 60)
    print("KNOWLEDGE BASE DISH SEARCH TEST")
    print("=" * 60)
    
    searches = [
        ("vegetarian dishes", 10),
        ("chicken", 10),
        ("starters appetizers", 10),
        ("biryani", 10),
        ("paneer", 10),
        ("fish curry", 10),
        ("beverages drinks", 10),
        ("desserts sweets", 10),
        ("main course", 10),
        ("rolls", 5),
    ]
    
    for query, limit in searches:
        print(f"\n🔍 Searching: '{query}' (limit={limit})")
        result = await service.search_items(query, limit=limit)
        items = result.get('items', [])
        print(f"   Found: {len(items)} items")
        for item in items[:5]:
            name = item.get('name', 'Unknown')
            price = item.get('price', 0)
            print(f"   - {name}: ${price:.2f}")
    
    # Also test knowledge search
    print("\n" + "=" * 60)
    print("KNOWLEDGE BASE GENERAL SEARCH")
    print("=" * 60)
    
    knowledge_queries = [
        "opening hours",
        "delivery policy",
        "reservation",
        "catering",
    ]
    
    for query in knowledge_queries:
        print(f"\n🔍 Knowledge: '{query}'")
        result = await service.search_knowledge(query, limit=3)
        if result.get('found'):
            answer = result.get('answer', '')[:100]
            print(f"   Answer: {answer}...")
        else:
            print("   No result found")

if __name__ == "__main__":
    asyncio.run(main())
