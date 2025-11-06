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
from qwen_agent.tools.base import BaseTool, register_tool

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
        
        # Store context managers (NOT entered yet)
        self._stdio_context = None
        self._session_context = None
        
        print(f"Initializing Qwen Agent with model: {model_config.get('model', 'default')}")
    
    def _create_tool_wrapper(self, tool_name: str, tool_description: str, tool_parameters: Dict) -> type:
        """
        Create a Qwen Agent tool class that wraps an MCP tool call
        
        This creates a proper BaseTool subclass that Qwen Agent can use
        """
        agent_ref = self  # Capture self reference
        
        @register_tool(tool_name)
        class MCPToolWrapper(BaseTool):
            description = tool_description
            parameters = [tool_parameters]
            
            def call(self, params: str, **kwargs) -> str:
                """Call the MCP tool synchronously (wrapper for async call)"""
                # Parse parameters
                if isinstance(params, str):
                    try:
                        params_dict = json.loads(params)
                    except json.JSONDecodeError:
                        params_dict = {'reaction': params}
                else:
                    params_dict = params
                
                # Call MCP tool asynchronously
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(
                    agent_ref._call_mcp_tool_internal(tool_name, params_dict)
                )
                return result
        
        return MCPToolWrapper
    
    async def _call_mcp_tool_internal(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Internal method to call an MCP tool
        
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
    
    async def initialize(self):
        """Initialize MCP connection and discover available tools"""
        print("Connecting to EVODEX MCP Server...")
        
        try:
            # Start MCP server connection
            params = StdioServerParameters(
                command="python",
                args=["evodex-mcp-server.py"]
            )
            
            # Create and enter stdio context
            self._stdio_context = stdio_client(params)
            read_stream, write_stream = await self._stdio_context.__aenter__()
            
            # Create and enter session context
            self._session_context = ClientSession(read_stream, write_stream)
            self.mcp_session = await self._session_context.__aenter__()
            
            # Initialize the session
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
            
            # Register MCP tools as Qwen Agent tools
            print("\nRegistering MCP tools with Qwen Agent...")
            tool_classes = []
            for tool in self.mcp_tools:
                tool_class = self._create_tool_wrapper(
                    tool['name'],
                    tool['description'],
                    tool['parameters']
                )
                tool_classes.append(tool_class)
                print(f"  ✓ Registered: {tool['name']}")
            
            # Load the LLM model
            print("\nLoading Qwen model...")
            llm = get_chat_model(self.model_config)
            print("✓ Model loaded")
            
            # Initialize Qwen Agent with function calling
            # Pass tool names (strings), not classes
            self.agent = Assistant(
                llm=llm,
                system_message=SYSTEM_PROMPT,
                function_list=[t['name'] for t in self.mcp_tools]  # ← Pass names only
            )
            
            print("Qwen Agent initialized and ready!")
            
        except Exception as e:
            print(f"Error during initialization: {e}")
            await self.close()  # Clean up on error
            raise
    
    async def _call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Call an MCP tool and return results (public interface)
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool result as string
        """
        return await self._call_mcp_tool_internal(tool_name, arguments)
    
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
        max_iterations = 5
        
        for iteration in range(max_iterations):
            print(f"[Iteration {iteration + 1}]")
            
            # Get agent's response - it returns a generator!
            response_generator = self.agent.run(messages)
            
            # Consume the generator to get actual responses
            responses = []
            for response in response_generator:  # ← Iterate through generator
                responses.append(response)
            
            if not responses:
                print("No response from agent")
                break
            
            # Get the last response
            response = responses[-1]
            
            # Check if it's a dict (message format)
            if isinstance(response, dict):
                # Check if agent wants to call a function
                if response.get('role') == 'assistant' and 'function_call' in response:
                    func_call = response['function_call']
                    func_name = func_call['name']
                    func_args = json.loads(func_call['arguments'])
                    
                    print(f"Agent wants to call: {func_name}")
                    
                    # Call the MCP tool
                    tool_result = await self._call_mcp_tool(func_name, func_args)
                    
                    # Add function result to messages
                    messages.append({
                        'role': 'assistant',
                        'content': None,
                        'function_call': func_call
                    })
                    messages.append({
                        'role': 'function',
                        'name': func_name,
                        'content': tool_result
                    })
                    
                else:
                    # Agent has final response
                    print(f"Agent final response generated")
                    content = response.get('content', '')
                    return content if content else str(response)
            else:
                # Response is some other format
                print(f"Agent final response generated")
                if hasattr(response, 'content'):
                    return response.content
                else:
                    return str(response)
        
        return "Max iterations reached without response"
    
    async def close(self):
        """Clean up MCP connection"""
        print("Closing MCP connection...")
        
        # Exit session context
        if self._session_context:
            try:
                await self._session_context.__aexit__(None, None, None)
            except Exception as e:
                print(f"Warning: Error closing session: {e}")
        
        # Exit stdio context
        if self._stdio_context:
            try:
                await self._stdio_context.__aexit__(None, None, None)
            except Exception as e:
                print(f"Warning: Error closing stdio: {e}")
        
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