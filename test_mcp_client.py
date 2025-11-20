"""Test the EVODEX MCP server by calling tools via the MCP client API."""

import asyncio
import json
from typing import List, Tuple

import mcp.types as types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


# Test reactions: tuples of (substrate_name, product_name, description)
# Valid enzymatic reactions
VALID_REACTIONS: List[Tuple[str, str, str]] = [
    ("propanol", "propanal", "Alcohol oxidation"),
    ("serine", "oxoserine", "Amino acid oxidation"),
    ("ethanol", "acetaldehyde", "Alcohol oxidation"),
    ("butanol", "butanal", "Alcohol oxidation"),
    ("glucose", "gluconic acid", "Sugar oxidation"),
]

# Invalid or non-enzymatic reactions
INVALID_REACTIONS: List[Tuple[str, str, str]] = [
    ("propanol", "1-bromopropane", "Halogenation (not enzymatic)"),
    ("serine", "propanol", "Invalid major structural change"),
    ("ethanol", "bromoethane", "Halogenation (not enzymatic)"),
    ("ethanol", "butane", "Invalid major carbon chain change"),
    ("benzene", "cyclohexane", "Aromatic reduction (not typical enzymatic)"),
]


def format_result(result: types.CallToolResult) -> str:
    """Extract and format the JSON result from the MCP response."""
    parts: List[str] = []
    for content in result.content:
        if hasattr(content, "text") and content.text:
            try:
                # The server returns a JSON string in the text field
                # First parse the outer structure
                outer_json = json.loads(content.text.strip())
                
                # If it's nested with a "content" field, extract the inner text
                if isinstance(outer_json, dict) and "content" in outer_json:
                    for item in outer_json["content"]:
                        if isinstance(item, dict) and "text" in item:
                            inner_text = item["text"]
                            # Try to parse the inner text as JSON
                            try:
                                inner_json = json.loads(inner_text.strip())
                                formatted = json.dumps(inner_json, indent=2)
                                parts.append(formatted)
                            except json.JSONDecodeError:
                                parts.append(inner_text)
                else:
                    # Direct JSON, format it nicely
                    formatted = json.dumps(outer_json, indent=2)
                    parts.append(formatted)
            except json.JSONDecodeError:
                # If it's not valid JSON, just return the text
                parts.append(content.text)
    
    return "\n".join(parts) if parts else "<no text content>"


async def run_tests() -> None:
    """Start the EVODEX MCP server and exercise its tools."""
    params = StdioServerParameters(command="python", args=["evodex-mcp-server.py"])

    async with stdio_client(params) as io_streams:
        async with ClientSession(*io_streams) as session:
            await session.initialize()

            # List available tools
            tools_result = await session.list_tools()
            available_tools = [tool.name for tool in tools_result.tools]
            print("=" * 80)
            print("Available tools:", ", ".join(available_tools))
            print("=" * 80)

            # Test valid reactions
            print("\n" + "=" * 80)
            print("TESTING VALID ENZYMATIC REACTIONS")
            print("=" * 80)
            for i, (substrate, product, description) in enumerate(VALID_REACTIONS, 1):
                print(f"\n[Test {i}] {description}")
                print(f"Substrate: {substrate} -> Product: {product}")
                print("-" * 80)
                try:
                    result = await session.call_tool(
                        "evaluate_reaction",
                        {
                            "substrate_name": substrate,
                            "product_name": product
                        }
                    )
                    print(format_result(result))
                except Exception as e:
                    print(f"ERROR: {e}")
                print()

            # Test invalid reactions
            print("\n" + "=" * 80)
            print("TESTING INVALID/NON-ENZYMATIC REACTIONS")
            print("=" * 80)
            for i, (substrate, product, description) in enumerate(INVALID_REACTIONS, 1):
                print(f"\n[Test {i}] {description}")
                print(f"Substrate: {substrate} -> Product: {product}")
                print("-" * 80)
                try:
                    result = await session.call_tool(
                        "evaluate_reaction",
                        {
                            "substrate_name": substrate,
                            "product_name": product
                        }
                    )
                    print(format_result(result))
                except Exception as e:
                    print(f"ERROR: {e}")
                print()

            print("=" * 80)
            print("Testing complete!")
            print("=" * 80)


def main() -> None:
    """Entry point for running the test client."""
    asyncio.run(run_tests())


if __name__ == "__main__":
    main()

