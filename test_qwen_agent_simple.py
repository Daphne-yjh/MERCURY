#!/usr/bin/env python3
"""
Simple test of Qwen Agent with direct tool calls (no full LLM yet)
"""

import asyncio
from qwen_agent_mcp import QwenMCPAgent


async def test_direct_validation():
    """Test direct MCP tool calls through the agent"""
    agent = QwenMCPAgent()
    
    try:
        # Just initialize MCP connection (skip LLM for now)
        await agent.initialize()
        
        # Directly test MCP tool call
        test_reaction = "CCCO>>CCC=O"
        
        result = await agent._call_mcp_tool(
            "evaluate_reaction",
            {"reaction": test_reaction, "operator_type": "E"}
        )
        
        print(f"\nDirect tool result:\n{result}")
        
    finally:
        await agent.close()


if __name__ == "__main__":
    print("Testing Qwen Agent - MCP Connection Only")
    asyncio.run(test_direct_validation())