#!/usr/bin/env python3
"""
EVODEX MCP Server

A Model Context Protocol (MCP) server that provides access to EVODEX evaluation
functionality for assessing the mechanistic plausibility of enzymatic reactions.

This server wraps the EVODEX evaluation package and provides tools for:
1. assign_evodex_F: Calculate formula differences and assign EVODEX-F IDs
2. match_operators: Match reaction operators against EVODEX datasets (E, C, N)
3. evaluate_reaction: Comprehensive reaction evaluation combining both methods
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)

# EVODEX imports
from evodex.evaluation import assign_evodex_F, match_operators

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("evodex_mcp_server")

# Initialize MCP server
server = Server("evodex-mcp-server")

@dataclass
class ReactionResult:
    """Data class for reaction evaluation results"""
    reaction: str
    evodex_f_id: Optional[str]
    matched_operators: List[str]
    is_plausible: bool
    confidence: str

class EVODEXEvaluator:
    """Main class for EVODEX evaluation functionality"""
    
    def __init__(self):
        self.logger = logging.getLogger("evodex_evaluator")
        self.logger.info("EVODEX Evaluator initialized")
    
    def assign_evodex_f(self, reaction: str) -> Optional[str]:
        """
        Calculate formula difference and assign EVODEX-F ID if it exists.
        
        Args:
            reaction: Reaction SMILES string in format "substrate>>product"
            
        Returns:
            EVODEX-F ID if found, None otherwise
        """
        self.logger.info(f"Evaluating reaction with assign_evodex_F: {reaction}")
        result = assign_evodex_F(reaction)
        self.logger.info(f"assign_evodex_F result: {result}")
        return result
    
    def match_operators(self, reaction: str, operator_type: str = 'E') -> List[str]:
        """
        Match reaction operators against EVODEX datasets.
        
        Args:
            reaction: Reaction SMILES string in format "substrate>>product"
            operator_type: Type of operator to match ('E', 'C', or 'N')
            
        Returns:
            List of matched operator IDs
        """
        self.logger.info(f"Evaluating reaction with match_operators: {reaction}, type: {operator_type}")
        result = match_operators(reaction, operator_type)
        self.logger.info(f"match_operators result: {result}")
        return result
    
    def evaluate_reaction(self, reaction: str, operator_type: str = 'E') -> ReactionResult:
        """
        Comprehensive reaction evaluation combining both EVODEX methods.
        
        Args:
            reaction: Reaction SMILES string in format "substrate>>product"
            operator_type: Type of operator to match ('E', 'C', or 'N')
            
        Returns:
            ReactionResult object with comprehensive evaluation
        """
        self.logger.info(f"Comprehensive evaluation of reaction: {reaction}")

        # Get EVODEX-F assignment
        f_id = self.assign_evodex_f(reaction)

        # Get matched operators
        matched_ops = self.match_operators(reaction, operator_type)

        # Determine plausibility
        is_plausible = f_id is not None or len(matched_ops) > 0

        # Determine confidence level
        if f_id and len(matched_ops) > 0:
            confidence = "High"
        elif f_id or len(matched_ops) > 0:
            confidence = "Medium"
        else:
            confidence = "Low"

        result = ReactionResult(
            reaction=reaction,
            evodex_f_id=f_id,
            matched_operators=matched_ops,
            is_plausible=is_plausible,
            confidence=confidence
        )

        self.logger.info(f"Evaluation complete: {result}")
        return result

# Initialize evaluator
evaluator = EVODEXEvaluator()

@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available EVODEX tools"""
    return [
        Tool(
            name="assign_evodex_f",
            description="Calculate formula difference and assign EVODEX-F ID for a reaction",
            inputSchema={
                "type": "object",
                "properties": {
                    "reaction": {
                        "type": "string",
                        "description": "Reaction SMILES string in format 'substrate>>product'"
                    }
                },
                "required": ["reaction"]
            }
        ),
        Tool(
            name="match_operators",
            description="Match reaction operators against EVODEX datasets (E, C, or N)",
            inputSchema={
                "type": "object",
                "properties": {
                    "reaction": {
                        "type": "string",
                        "description": "Reaction SMILES string in format 'substrate>>product'"
                    },
                    "operator_type": {
                        "type": "string",
                        "description": "Type of operator to match: 'E' (enzymatic), 'C' (chemical), or 'N' (natural)",
                        "default": "E",
                        "enum": ["E", "C", "N"]
                    }
                },
                "required": ["reaction"]
            }
        ),
        Tool(
            name="evaluate_reaction",
            description="Comprehensive reaction evaluation combining both EVODEX methods",
            inputSchema={
                "type": "object",
                "properties": {
                    "reaction": {
                        "type": "string",
                        "description": "Reaction SMILES string in format 'substrate>>product'"
                    },
                    "operator_type": {
                        "type": "string",
                        "description": "Type of operator to match: 'E' (enzymatic), 'C' (chemical), or 'N' (natural)",
                        "default": "E",
                        "enum": ["E", "C", "N"]
                    }
                },
                "required": ["reaction"]
            }
        ),
        Tool(
            name="batch_evaluate",
            description="Evaluate multiple reactions in batch",
            inputSchema={
                "type": "object",
                "properties": {
                    "reactions": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "List of reaction SMILES strings"
                    },
                    "operator_type": {
                        "type": "string",
                        "description": "Type of operator to match: 'E' (enzymatic), 'C' (chemical), or 'N' (natural)",
                        "default": "E",
                        "enum": ["E", "C", "N"]
                    }
                },
                "required": ["reactions"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """Handle tool calls"""
    logger.info(f"Tool call: {name} with arguments: {arguments}")

    if name == "assign_evodex_f":
        reaction = arguments.get("reaction")
        if not reaction:
            raise ValueError("Reaction parameter is required")

        result = evaluator.assign_evodex_f(reaction)

        return CallToolResult.model_validate({
            "content": [
                {
                    "type": "text",
                    "text": f"EVODEX-F ID: {result if result else 'No match found'}\n\nReaction: {reaction}"
                }
            ]
        })

    if name == "match_operators":
        reaction = arguments.get("reaction")
        operator_type = arguments.get("operator_type", "E")

        if not reaction:
            raise ValueError("Reaction parameter is required")

        result = evaluator.match_operators(reaction, operator_type)

        return CallToolResult.model_validate({
            "content": [
                {
                    "type": "text",
                    "text": f"Matched Operators ({operator_type}): {result if result else 'No matches found'}\n\nReaction: {reaction}"
                }
            ]
        })

    if name == "evaluate_reaction":
        reaction = arguments.get("reaction")
        operator_type = arguments.get("operator_type", "E")

        if not reaction:
            raise ValueError("Reaction parameter is required")

        result = evaluator.evaluate_reaction(reaction, operator_type)

        # Format comprehensive result
        result_text = f"""
EVODEX Reaction Evaluation Results
================================

Reaction: {result.reaction}
EVODEX-F ID: {result.evodex_f_id if result.evodex_f_id else 'No match'}
Matched Operators ({operator_type}): {result.matched_operators if result.matched_operators else 'No matches'}
Is Plausible: {result.is_plausible}
Confidence: {result.confidence}

Interpretation:
-- EVODEX-F ID indicates known formula change patterns
-- Matched operators indicate specific mechanistic patterns
-- Higher confidence when both methods find matches
"""

        return CallToolResult.model_validate({
            "content": [
                {
                    "type": "text",
                    "text": result_text.strip()
                }
            ]
        })

    if name == "batch_evaluate":
        reactions = arguments.get("reactions", [])
        operator_type = arguments.get("operator_type", "E")

        if not reactions:
            raise ValueError("Reactions parameter is required")

        results = []
        for reaction in reactions:
            result = evaluator.evaluate_reaction(reaction, operator_type)
            results.append({
                "reaction": result.reaction,
                "evodex_f_id": result.evodex_f_id,
                "matched_operators": result.matched_operators,
                "is_plausible": result.is_plausible,
                "confidence": result.confidence
            })

        # Format batch results
        result_text = f"Batch Evaluation Results ({len(reactions)} reactions)\n"
        result_text += "=" * 50 + "\n\n"

        for i, result in enumerate(results, 1):
            result_text += f"{i}. {result['reaction']}\n"
            result_text += f"   EVODEX-F: {result['evodex_f_id'] or 'No match'}\n"
            result_text += f"   Operators: {result['matched_operators'] or 'No matches'}\n"
            result_text += f"   Plausible: {result['is_plausible']} (Confidence: {result['confidence']})\n"
            result_text += "\n"

        return CallToolResult.model_validate({
            "content": [
                {
                    "type": "text",
                    "text": result_text.strip()
                }
            ]
        })

    raise ValueError(f"Unknown tool: {name}")

async def main():
    """Main function to run the MCP server"""
    logger.info("Starting EVODEX MCP Server...")
    
    # Run the server using stdio
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="evodex-mcp-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=server.notification_options,
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
