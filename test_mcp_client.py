"""Test the EVODEX MCP server by calling tools via the MCP client API."""

import asyncio
from typing import List

import mcp.types as types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


# Reactions for testing: 5 valid and 5 invalid
VALID_REACTIONS: List[str] = [
    "CCCO>>CCC=O",  # propanol >> propanal, alcohol oxidation
    "C([C@@H](C(=O)O)N)O>>C([C@@H](C(=O)O)N)=O",  # serine >> oxo-serine, amino acid oxidation
    "CCCO>>CCCOC",  # propanol >> propyl methyl ether, etherification
    "CCO>>CC=O",  # ethanol >> ethanal, alcohol oxidation
    "CCCCO>>CCCC=O",  # butanol >> butanal, alcohol oxidation
]

INVALID_REACTIONS: List[str] = [
    "CCCO>>CC(Br)CO",  # propanol >> brominated propanol, halogenation (not enzymatic)
    "C([C@@H](C(=O)O)N)O>>CCCO",  # serine >> propanol, invalid major structural change
    "CC=CCO>>CCCC",  # butenol >> butane, hydrogenation with carbon chain change (not enzymatic)
    "CCO>>CC(Br)O",  # ethanol >> brominated ethanol, halogenation (not enzymatic)
    "CCO>>CCCC",  # ethanol >> butane, invalid major carbon chain change
]


def summarize_result(result: types.CallToolResult) -> str:
    """Extract and return only the text content from the result."""
    import json
    
    # The MCP framework wraps our dictionary responses in CallToolResult objects
    # where the text field contains the JSON string representation
    parts: List[str] = []
    for content in result.content:
        if hasattr(content, "text") and content.text:
            # Parse the JSON string to extract the actual text content
            json_data = json.loads(content.text)
            for item in json_data["content"]:
                parts.append(item["text"])
    
    return "\n".join(parts) if parts else "<no text content>"


async def run_tests() -> None:
    """Start the EVODEX MCP server and exercise its tools."""
    params = StdioServerParameters(command="python", args=["evodex-mcp-server.py"])

    async with stdio_client(params) as io_streams:
        async with ClientSession(*io_streams) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            available_tools = [tool.name for tool in tools_result.tools]
            print("Available tools:", ", ".join(available_tools))

            print("\nValid reactions:")
            for reaction in VALID_REACTIONS:
                result = await session.call_tool("evaluate_reaction", {"reaction": reaction, "operator_type": "E"})
                print(summarize_result(result))
                print()

            print("Invalid reactions:")
            for reaction in INVALID_REACTIONS:
                result = await session.call_tool("evaluate_reaction", {"reaction": reaction, "operator_type": "E"})
                print(summarize_result(result))
                print()


def main() -> None:
    """Entry point for running the test client."""
    asyncio.run(run_tests())


if __name__ == "__main__":
    main()

