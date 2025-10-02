# EVODEX MCP Server

A Model Context Protocol (MCP) server that provides access to EVODEX evaluation functionality for assessing the mechanistic plausibility of enzymatic reactions.

## Overview

The EVODEX MCP Server wraps the EVODEX evaluation package and provides tools for:

1. **assign_evodex_f**: Calculate formula differences and assign EVODEX-F IDs
2. **match_operators**: Match reaction operators against EVODEX datasets (E, C, N)
3. **evaluate_reaction**: Comprehensive reaction evaluation combining both methods
4. **batch_evaluate**: Evaluate multiple reactions in batch

## Installation Guide

### Prerequisites

- [Conda](https://docs.conda.io/en/latest/miniconda.html) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html) installed
- Python 3.11.13

### Step 1: Create Conda Environment

Create a new conda environment with Python 3.11.13:

```bash
conda create -n mercury_env python=3.11.13
```

### Step 2: Activate Environment

Activate the conda environment:

```bash
conda activate mercury_env
```

### Step 3: Install Dependencies

Install all required packages from the requirements.txt file:

```bash
pip install -r requirements.txt
```

This will install:
- `evodex` - EVODEX evaluation package
- `mcp` - Model Context Protocol library
- `rdkit-pypi` - Chemical informatics toolkit
- `numpy<2` - Numerical computing (compatible with RDKit)

### Step 4: Verify Installation

Test that everything is working correctly:

```bash
python test_mcp_client.py
```

You should see output showing the evaluation of 10 test reactions (5 valid, 5 invalid).

## Usage

### Running the EVODEX MCP Server

The MCP server provides programmatic access to EVODEX functionality through the Model Context Protocol.

#### Start the Server

```bash
conda activate mercury_env
python evodex-mcp-server.py
```

The server will start and listen for MCP protocol messages via stdio. It provides four main tools for reaction evaluation.

#### Available Tools

##### 1. assign_evodex_f
Calculate formula difference and assign EVODEX-F ID for a reaction.

**Parameters:**
- `reaction` (string): Reaction SMILES string in format 'substrate>>product'

**Example:**
```json
{
  "name": "assign_evodex_f",
  "arguments": {
    "reaction": "CCCO>>CCC=O"
  }
}
```

**Response:**
```
EVODEX-F ID: ['EVODEX.1-F4']

Reaction: CCCO>>CCC=O
```

##### 2. match_operators
Match reaction operators against EVODEX datasets.

**Parameters:**
- `reaction` (string): Reaction SMILES string in format 'substrate>>product'
- `operator_type` (string, optional): Type of operator to match ('E', 'C', or 'N'). Default: 'E'

**Example:**
```json
{
  "name": "match_operators",
  "arguments": {
    "reaction": "CCCO>>CCC=O",
    "operator_type": "E"
  }
}
```

**Response:**
```
Matched Operators (E): ['EVODEX.1-E40']

Reaction: CCCO>>CCC=O
```

##### 3. evaluate_reaction
Comprehensive reaction evaluation combining both EVODEX methods.

**Parameters:**
- `reaction` (string): Reaction SMILES string in format 'substrate>>product'
- `operator_type` (string, optional): Type of operator to match ('E', 'C', or 'N'). Default: 'E'

**Example:**
```json
{
  "name": "evaluate_reaction",
  "arguments": {
    "reaction": "CCCO>>CCC=O",
    "operator_type": "E"
  }
}
```

**Response:**
```
EVODEX Reaction Evaluation Results
================================

Reaction: CCCO>>CCC=O
EVODEX-F ID: ['EVODEX.1-F4']
Matched Operators (E): ['EVODEX.1-E40']
Is Plausible: True
Confidence: High
```

##### 4. batch_evaluate
Evaluate multiple reactions in batch.

**Parameters:**
- `reactions` (array): List of reaction SMILES strings
- `operator_type` (string, optional): Type of operator to match ('E', 'C', or 'N'). Default: 'E'

**Example:**
```json
{
  "name": "batch_evaluate",
  "arguments": {
    "reactions": [
      "CCCO>>CCC=O",
      "C([C@@H](C(=O)O)N)O>>C([C@@H](C(=O)O)N)=O"
    ],
    "operator_type": "E"
  }
}
```

### Using the Test Client

The `test_mcp_client.py` script demonstrates how to interact with the EVODEX MCP server programmatically.

#### Run the Test Client

```bash
conda activate mercury_env
python test_mcp_client.py
```

#### What the Test Client Does

1. **Connects to the MCP server** using stdio communication
2. **Lists available tools** and displays them
3. **Tests 5 valid reactions** (enzymatically plausible):
   - `CCCO>>CCC=O` - propanol >> propanal, alcohol oxidation
   - `C([C@@H](C(=O)O)N)O>>C([C@@H](C(=O)O)N)=O` - serine >> oxo-serine, amino acid oxidation
   - `CCCO>>CCCOC` - propanol >> propyl methyl ether, etherification
   - `CCO>>CC=O` - ethanol >> ethanal, alcohol oxidation
   - `CCCCO>>CCCC=O` - butanol >> butanal, alcohol oxidation

4. **Tests 5 invalid reactions** (not enzymatically plausible):
   - `CCCO>>CC(Br)CO` - propanol >> brominated propanol, halogenation (not enzymatic)
   - `C([C@@H](C(=O)O)N)O>>CCCO` - serine >> propanol, invalid major structural change
   - `CC=CCO>>CCCC` - butenol >> butane, hydrogenation with carbon chain change (not enzymatic)
   - `CCO>>CC(Br)O` - ethanol >> brominated ethanol, halogenation (not enzymatic)
   - `CCO>>CCCC` - ethanol >> butane, invalid major carbon chain change

#### Expected Output

The test client will show:
- Available tools list
- Clean, formatted evaluation results for each reaction
- Plausibility assessment and confidence levels

## Example Results

### Valid Reaction: CCCO>>CCC=O (Propanol to Propanal)

```
EVODEX Reaction Evaluation Results
================================

Reaction: CCCO>>CCC=O
EVODEX-F ID: ['EVODEX.1-F4']
Matched Operators (E): ['EVODEX.1-E40']
Is Plausible: True
Confidence: High
```

This indicates that the oxidation of propanol to propanal is a known enzymatic reaction with high confidence.

### Invalid Reaction: CCCO>>CC(Br)CO (Propanol to Brominated Propanol)

```
EVODEX Reaction Evaluation Results
================================

Reaction: CCCO>>CC(Br)CO
EVODEX-F ID: No match
Matched Operators (E): No matches
Is Plausible: False
Confidence: Low
```

This indicates that the halogenation of propanol is not a known enzymatic reaction.

## File Structure

```
MERCURY/
├── evodex-mcp-server.py      # Main MCP server implementation
├── test_mcp_client.py        # Test client for the MCP server
├── requirements.txt          # Python package dependencies
├── README.md                 # This file
├── .gitignore               # Git ignore rules
└── __pycache__/             # Python bytecode cache (ignored by git)
```

## Logging

The server uses Python's built-in logging module with INFO level logging. Logs include:
- Server initialization
- Tool calls and parameters
- EVODEX evaluation results
- Error messages

## Troubleshooting

### Common Issues

1. **ModuleNotFoundError: No module named 'evodex'**
   - Ensure you're in the correct conda environment: `conda activate mercury_env`
   - Install evodex: `pip install evodex`

2. **NumPy compatibility issues**
   - Downgrade NumPy: `pip install "numpy<2"`

3. **MCP server initialization errors**
   - Check that all dependencies are installed
   - Verify Python version is 3.11.13

4. **Environment not activated**
   - Always run `conda activate mercury_env` before running any Python files

### Getting Help

If you encounter issues:
1. Check that your conda environment is activated
2. Verify all packages are installed correctly
3. Check the server logs for error messages
4. Ensure you're using Python 3.11.13

## License

This project uses the EVODEX evaluation package. Please refer to the EVODEX package license for usage terms.