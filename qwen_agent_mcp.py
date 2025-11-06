#!/usr/bin/env python3
"""
Qwen Agent integrated with EVODEX MCP Server
This is the orchestration layer that interprets user queries and calls MCP tools
"""

import asyncio
import json
from typing import Dict, Any, Optional, List

# Qwen Agent imports
from qwen_agent.agents import Assistant
from qwen_agent.llm import get_chat_model

# MCP imports
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from agents_prompts import SYSTEM_PROMPT


class QwenMCPAgent:
    """
    Qwen Agent that uses MCP to validate enzymatic reactions
    
    This agent:
    1. Receives natural language queries about reactions
    2. Extracts chemical names from queries
    3. Calls EVODEX MCP server tools for validation
    4. Interprets and explains results to the user
    """
    
    def __init__(self, model_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Qwen Agent with MCP client
        
        Args:
            model_config: Configuration for Qwen model (default uses Qwen2.5-3B locally)
        """
        # Default to local 3B model for M2 Mac
        if model_config is None:
            model_config = {
                'model': 'Qwen/Qwen2.5-3B-Instruct',
                'model_server': 'local',
                'device': 'mps',  # Metal Performance Shaders for M2
                'generate_cfg': {
                    'temperature': 0.1,  # Low temp for deterministic chemistry
                    'top_p': 0.9,
                    'max_tokens': 2048
                }
            }
        
        self.model_config = model_config
        self.mcp_session: Optional[ClientSession] = None
        self.mcp_tools: List[Dict] = []
        
        print(f"Initializing Qwen Agent with model: {model_config.get('model', 'default')}")
        
    async def initialize(self):
        """Initialize MCP connection and discover available tools"""
        print("Connecting to EVODEX MCP Server...")
        
        # Start MCP server connection
        params = StdioServerParameters(
            command="python",
            args=["evodex-mcp-server.py"]
        )
        
        # Create MCP client session
        self.io_streams = await stdio_client(params).__aenter__()
        self.mcp_session = await ClientSession(*self.io_streams).__aenter__()
        await self.mcp_session.initialize()
        
        # Discover available tools from MCP server
        tools_result = await self.mcp_session.list_tools()
        self.mcp_tools = [
            {
                'name': tool.name,
                'description': tool.description,
                'parameters': tool.inputSchema
            }
            for tool in tools_result.tools
        ]
        
        print(f"Connected! Available tools: {[t['name'] for t in self.mcp_tools]}")
        
        # Initialize Qwen Agent with function calling
        self.agent = Assistant(
            llm=self.model_config,
            system_message=SYSTEM_PROMPT,
            function_list=self._convert_tools_for_qwen()
        )
        
        print("Qwen Agent initialized and ready!")
        
    def _convert_tools_for_qwen(self) -> List[Dict]:
        """
        Convert MCP tool definitions to Qwen Agent function format
        
        Qwen Agent expects OpenAI-style function definitions
        """
        qwen_functions = []
        
        for tool in self.mcp_tools:
            qwen_functions.append({
                'name': tool['name'],
                'description': tool['description'],
                'parameters': tool['parameters']
            })
        
        return qwen_functions
    
    async def _call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Call an MCP tool and return results
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool result as string
        """
        print(f"  → Calling MCP tool: {tool_name}")
        print(f"    Arguments: {arguments}")
        
        result = await self.mcp_session.call_tool(tool_name, arguments)
        
        # Extract text from result
        result_text = ""
        for content in result.content:
            if hasattr(content, 'text'):
                result_text += content.text
        
        print(f"  ← Received result ({len(result_text)} chars)")
        return result_text
    
    async def run(self, user_query: str) -> str:
        """
        Process a user query through the agent
        
        Args:
            user_query: Natural language question about reaction validation
            
        Returns:
            Agent's response with validation results
        """
        print(f"\n{'='*60}")
        print(f"User Query: {user_query}")
        print(f"{'='*60}\n")
        
        if not self.mcp_session:
            await self.initialize()
        
        # Create messages for the agent
        messages = [{'role': 'user', 'content': user_query}]
        
        # Agent reasoning loop
        response_messages = []
        max_iterations = 5  # Prevent infinite loops
        
        for iteration in range(max_iterations):
            print(f"[Iteration {iteration + 1}]")
            
            # Get agent's response
            response = self.agent.run(messages)
            
            # Check if agent wants to call a function
            if hasattr(response, 'function_call') and response.function_call:
                func_name = response.function_call.name
                func_args = json.loads(response.function_call.arguments)
                
                print(f"Agent wants to call: {func_name}")
                
                # Call the MCP tool
                tool_result = await self._call_mcp_tool(func_name, func_args)
                
                # Add function result to messages
                messages.append({
                    'role': 'assistant',
                    'content': None,
                    'function_call': response.function_call
                })
                messages.append({
                    'role': 'function',
                    'name': func_name,
                    'content': tool_result
                })
                
            else:
                # Agent has final response
                print(f"Agent final response generated")
                response_messages.append(response)
                break
        
        # Extract final text response
        final_response = response_messages[-1] if response_messages else response
        
        if hasattr(final_response, 'content'):
            return final_response.content
        else:
            return str(final_response)
    
    async def close(self):
        """Clean up MCP connection"""
        if self.mcp_session:
            await self.mcp_session.__aexit__(None, None, None)
            await self.io_streams.__aexit__(None, None, None)
            print("MCP connection closed")


async def main():
    """Example usage of Qwen MCP Agent"""
    agent = QwenMCPAgent()
    
    try:
        # Initialize agent and connect to MCP server
        await agent.initialize()
        
        # Test queries
        test_queries = [
            "Is the conversion of ethanol to acetaldehyde a valid enzymatic reaction?",
            "Can glucose be enzymatically converted to pyruvate?",
            "Validate the reaction: propanol to propanal"
        ]
        
        for query in test_queries:
            response = await agent.run(query)
            print(f"\n{'='*60}")
            print(f"RESPONSE:")
            print(response)
            print(f"{'='*60}\n")
            
    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())