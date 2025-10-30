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
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    Tool,
)

# EVODEX imports
from evodex.evaluation import assign_evodex_F, match_operators

# Additional imports for SMILES lookup
import requests
import json
import time
import pubchempy as pcp

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
    substrate_name: str
    product_name: str
    substrate_smiles: str
    product_smiles: str
    matches: List[Dict[str, str]]
    conclusion: str

class EVODEXEvaluator:
    """Main class for EVODEX evaluation functionality"""
    
    def __init__(self):
        self.logger = logging.getLogger("evodex_evaluator")
        self.logger.info("EVODEX Evaluator initialized")
    
    def get_smiles_pubchem(self, name: str) -> Optional[str]:
        """
        Get SMILES using PubChemPy library.
        
        Args:
            name: Name of the compound
            
        Returns:
            SMILES string if found, None otherwise
        """
        try:
            smiles = pcp.get_compounds(name, 'name')
            if smiles:
                self.logger.info(f"Found SMILES via PubChem for {name}")
                return smiles[0].isomeric_smiles
            return None
        except Exception as e:
            self.logger.debug(f"PubChem lookup failed for {name}: {e}")
            return None
    
    def get_smiles_cactus(self, structure_identifier: str) -> Optional[str]:
        """
        Get SMILES using CACTUS Chemical Identifier Resolver.
        
        Args:
            structure_identifier: Name of the compound
            
        Returns:
            SMILES string if found, None otherwise
        """
        try:
            url = f"https://cactus.nci.nih.gov/chemical/structure/{structure_identifier}/smiles"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                smiles = response.text.strip()
                if smiles and not smiles.startswith('Error'):
                    self.logger.info(f"Found SMILES via CACTUS for {structure_identifier}")
                    return smiles
            return None
        except Exception as e:
            self.logger.debug(f"CACTUS lookup failed for {structure_identifier}: {e}")
            return None
    
    def get_smiles_chemspider(self, name: str) -> Optional[str]:
        """
        Get SMILES using ChemSpider API.
        
        Args:
            name: Name of the compound
            
        Returns:
            SMILES string if found, None otherwise
        """
        api_key = 'a2J8YBbT3n7JsymaHfisErAyKjDHQP2A'
        search_url = f'https://api.rsc.org/compounds/v1/filter/name/'
        headers = {'apikey': api_key}
        
        try:
            data = {'name': name}
            json_data = json.dumps(data)
            response = requests.post(search_url, headers=headers, data=json_data, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            csid = data['queryId']
            
            # Give the server time to load the query
            time.sleep(1)
            
            details_url = f'https://api.rsc.org/compounds/v1/filter/{csid}/results'
            response = requests.get(details_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            results = data['results'][0]
            details_url = f'https://api.rsc.org/compounds/v1/records/{results}/details?fields=SMILES'
            response = requests.get(details_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            smiles = data.get('smiles')
            if smiles:
                self.logger.info(f"Found SMILES via ChemSpider for {name}")
            return smiles
            
        except Exception as e:
            self.logger.debug(f"ChemSpider lookup failed for {name}: {e}")
            return None
    
    def lookup_smiles(self, compound_name: str) -> Optional[str]:
        """
        Look up SMILES string for a compound name using multiple sources.
        Tries PubChem, then CACTUS, then ChemSpider in sequence.
        
        Args:
            compound_name: Name of the compound
            
        Returns:
            SMILES string if found, None otherwise
        """
        # Try PubChem first
        smiles = self.get_smiles_pubchem(compound_name)
        if smiles:
            return smiles
        
        # Try CACTUS
        smiles = self.get_smiles_cactus(compound_name)
        if smiles:
            return smiles
        
        # Try ChemSpider
        smiles = self.get_smiles_chemspider(compound_name)
        if smiles:
            return smiles
        
        self.logger.warning(f"Could not find SMILES for compound: {compound_name}")
        return None
    
    def evaluate_reaction(self, substrate_name: str, product_name: str) -> ReactionResult:
        """
        Evaluate a reaction based on substrate and product names,
        returning details and matching results from EVODEX.
        
        Args:
            substrate_name: Name of the substrate compound
            product_name: Name of the product compound
            
        Returns:
            ReactionResult object with comprehensive evaluation
        """
        self.logger.info(f"Evaluating reaction: {substrate_name} -> {product_name}")
        
        # Initialize result object
        result = ReactionResult(
            substrate_name=substrate_name,
            product_name=product_name,
            substrate_smiles="",
            product_smiles="",
            matches=[],
            conclusion=""
        )
        
        # Look up SMILES for substrate
        substrate_smiles = self.lookup_smiles(substrate_name)
        if not substrate_smiles:
            result.conclusion = "Could not resolve substrate to SMILES"
            return result
        result.substrate_smiles = substrate_smiles
        
        # Look up SMILES for product
        product_smiles = self.lookup_smiles(product_name)
        if not product_smiles:
            result.conclusion = "Could not resolve product to SMILES"
            return result
        result.product_smiles = product_smiles
        
        # Create reaction SMILES
        reaction_smiles = f"{substrate_smiles}>>{product_smiles}"
        
        # Run EVODEX evaluation at different abstraction levels
        # Check F level (formula difference)
        f_id = assign_evodex_F(reaction_smiles)
        
        if not f_id:
            result.conclusion = "No match found to any known enzymatic reactions"
            return result
        
        # Check C level (chemical)
        c_matches = match_operators(reaction_smiles, 'C')
        if not c_matches:
            result.conclusion = "The reaction has precedent with other reactions with a similar formula difference, but the specific mechanism is unprecedented"
            # Add F match to results
            result.matches.append({"evodex_id": f_id})
            return result
        
        # Check N level (natural)
        n_matches = match_operators(reaction_smiles, 'N')
        if not n_matches:
            result.conclusion = "The reaction has precedent with other reactions sharing similar reactive groups, but the specific mechanism is unprecedented"
            # Add F and C matches to results
            result.matches.append({"evodex_id": f_id})
            for match in c_matches:
                result.matches.append({"evodex_id": match})
            return result
        
        # Check E level (enzymatic)
        e_matches = match_operators(reaction_smiles, 'E')
        if not e_matches:
            result.conclusion = "The reaction matches known reaction mechanisms partially but not the entire electronic manifold is present."
            # Add all previous matches to results
            result.matches.append({"evodex_id": f_id})
            for match in c_matches:
                result.matches.append({"evodex_id": match})
            for match in n_matches:
                result.matches.append({"evodex_id": match})
            return result
        
        # If we got here, we have an E match
        result.conclusion = f"Full enzymatic match found with {len(e_matches)} mechanism(s)"
        
        # Add all matches to results
        result.matches.append({"evodex_id": f_id})
        for match in c_matches:
            result.matches.append({"evodex_id": match})
        for match in n_matches:
            result.matches.append({"evodex_id": match})
        for match in e_matches:
            result.matches.append({"evodex_id": match})
        
        self.logger.info(f"Evaluation complete: {result.conclusion}")
        return result

# Initialize evaluator
evaluator = EVODEXEvaluator()

@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available EVODEX tools"""
    return [
        Tool(
            name="evaluate_reaction",
            description="Evaluate a reaction based on substrate and product names, returning EVODEX matches and conclusions",
            inputSchema={
                "type": "object",
                "properties": {
                    "substrate_name": {
                        "type": "string",
                        "description": "Name of the substrate compound"
                    },
                    "product_name": {
                        "type": "string",
                        "description": "Name of the product compound"
                    }
                },
                "required": ["substrate_name", "product_name"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """Handle tool calls"""
    logger.info(f"Tool call: {name} with arguments: {arguments}")

    if name == "evaluate_reaction":
        substrate_name = arguments.get("substrate_name")
        product_name = arguments.get("product_name")

        if not substrate_name or not product_name:
            raise ValueError("Both substrate_name and product_name parameters are required")

        result = evaluator.evaluate_reaction(substrate_name, product_name)

        # Format result as JSON-like object
        result_text = f"""
{{
  "substrate_name": "{result.substrate_name}",
  "product_name": "{result.product_name}",
  "substrate_smiles": "{result.substrate_smiles}",
  "product_smiles": "{result.product_smiles}",
  "matches": {json.dumps(result.matches, indent=4)},
  "conclusion": "{result.conclusion}"
}}
"""

        return {
            "content": [
                {
                    "type": "text",
                    "text": result_text
                }
            ]
        }

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
