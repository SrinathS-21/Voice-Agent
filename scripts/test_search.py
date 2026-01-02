"""Test semantic search on the RAG knowledge base."""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from app.core.convex_client import ConvexClient

async def test_search():
    client = ConvexClient()
    org_id = 'js710fpdzbnhrb8ttvyc4crghn7y9qng'
    
    # Test queries that a customer might ask
    queries = [
        'What vegetarian starters do you have?',
        'Tell me about butter chicken',
        'What is the price of biryani?',
        'Do you deliver? What is the delivery fee?',
        'What are your hours on Sunday?',
        'Any desserts available?',
        'Spicy dishes',
        'paneer dishes'
    ]
    
    print("=" * 60)
    print("TESTING SEMANTIC SEARCH ON KAANCHI CUISINE KNOWLEDGE BASE")
    print("=" * 60)
    
    for query in queries:
        print(f'\n🔍 Query: "{query}"')
        print("-" * 50)
        
        try:
            result = await client.action('rag:search', {
                'namespace': org_id,
                'query': query,
                'limit': 3
            })
            
            if result and result.get('results'):
                for i, r in enumerate(result['results'], 1):
                    text = r.get('text', '')[:200].replace('\n', ' ')
                    score = r.get('score', 0)
                    print(f'  {i}. [Score: {score:.3f}]')
                    print(f'     {text}...')
            else:
                print('  ❌ No results found')
        except Exception as e:
            print(f'  ❌ Error: {e}')
    
    print("\n" + "=" * 60)
    print("SEARCH TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_search())
