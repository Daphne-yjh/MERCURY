import asyncio
from qwen_agent_mcp import QwenMCPAgent

async def test_queries():
    agent = QwenMCPAgent()
    
    try:
        await agent.initialize()
        
        # These should work with the full agent
        queries = [
            "Is CCCO>>CCC=O a valid enzymatic reaction?",
            "Can you validate ethanol to acetaldehyde?",
            "Is the conversion of propanol to propanal enzymatically plausible?"
        ]
        
        for query in queries:
            response = await agent.run(query)
            print(f"\nQuery: {query}")
            print(f"Response: {response}\n")
            print("="*60)
            
    finally:
        await agent.close()

if __name__ == "__main__":
    asyncio.run(test_queries())