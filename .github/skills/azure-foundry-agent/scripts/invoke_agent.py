#!/usr/bin/env python3
"""
Azure Foundry Agent Invoker

This script invokes Azure AI Foundry agents to answer questions.
Supports multiple agents configured in the agents-config.yaml file.

Usage:
    python invoke_agent.py "<agent_name>" "<your_query>"
    python invoke_agent.py --list                          # List available agents
    python invoke_agent.py --help                          # Show help

Prerequisites:
    pip install --pre azure-ai-projects>=2.0.0b1 azure-identity pyyaml
"""

import sys
import os
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Please run: pip install pyyaml")
    sys.exit(1)

try:
    from azure.identity import DefaultAzureCredential
    from azure.ai.projects import AIProjectClient
except ImportError:
    print("ERROR: Required packages not installed.")
    print("Please run: pip install --pre azure-ai-projects>=2.0.0b1 azure-identity")
    sys.exit(1)


def get_config_path() -> Path:
    """Get the path to the agents config file."""
    script_dir = Path(__file__).parent
    config_path = script_dir.parent / "references" / "agents-config.yaml"
    return config_path


def load_config() -> dict:
    """Load the agents configuration from YAML file."""
    config_path = get_config_path()
    
    if not config_path.exists():
        print(f"ERROR: Configuration file not found at: {config_path}")
        print("Please create the config file with your agent definitions.")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def get_available_agents(config: dict) -> list:
    """Get list of available agent names from config."""
    return [agent['name'] for agent in config.get('agents', [])]


def get_agent_info(config: dict, agent_name: str) -> dict | None:
    """Get agent info by name (case-insensitive partial match)."""
    agents = config.get('agents', [])
    
    # First try exact match
    for agent in agents:
        if agent['name'].lower() == agent_name.lower():
            return agent
    
    # Then try partial match
    for agent in agents:
        if agent_name.lower() in agent['name'].lower():
            return agent
    
    return None


def list_agents(config: dict) -> str:
    """Format a list of available agents for display."""
    agents = config.get('agents', [])
    
    if not agents:
        return "No agents configured. Please add agents to the config file."
    
    lines = ["Available Azure Foundry Agents:", "=" * 40]
    
    for agent in agents:
        lines.append(f"\n📌 {agent['name']}")
        lines.append(f"   Description: {agent.get('description', 'No description')}")
        triggers = agent.get('triggers', [])
        if triggers:
            lines.append(f"   Triggers: {', '.join(triggers)}")
    
    lines.append("\n" + "=" * 40)
    lines.append(f"Config file: {get_config_path()}")
    
    return "\n".join(lines)


def invoke_agent(endpoint: str, agent_name: str, query: str) -> str:
    """
    Invoke an Azure Foundry agent with a query.
    
    Args:
        endpoint: Azure Foundry endpoint URL
        agent_name: Name of the agent to invoke
        query: The user's question or query to send to the agent.
        
    Returns:
        The agent's response text.
    """
    try:
        # Create project client with Azure credentials
        project_client = AIProjectClient(
            endpoint=endpoint,
            credential=DefaultAzureCredential(),
        )
        
        # Get the specified agent
        agent = project_client.agents.get(agent_name=agent_name)
        print(f"Connected to agent: {agent.name}", file=sys.stderr)
        
        # Get OpenAI client for generating responses
        openai_client = project_client.get_openai_client()
        
        # Send query to the agent and get response
        response = openai_client.responses.create(
            input=[{"role": "user", "content": query}],
            extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
        )
        
        return response.output_text
        
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        
        if "authentication" in error_msg.lower() or "credential" in error_msg.lower():
            return f"Authentication Error: Please run 'az login' to authenticate with Azure.\nDetails: {error_msg}"
        elif "not found" in error_msg.lower():
            return f"Agent Not Found: The agent '{agent_name}' was not found in Azure Foundry.\nDetails: {error_msg}"
        elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
            return f"Connection Error: Unable to connect to Azure Foundry.\nDetails: {error_msg}"
        else:
            return f"Error ({error_type}): {error_msg}"


def print_usage():
    """Print usage instructions."""
    print("""
Azure Foundry Agent Invoker
===========================

Usage:
    python invoke_agent.py "<agent_name>" "<your_query>"
    python invoke_agent.py --list
    python invoke_agent.py --help

Examples:
    python invoke_agent.py "work-assitant" "What can you help me with?"
    python invoke_agent.py --list

Options:
    --list    List all available agents from config
    --help    Show this help message
""")


def main():
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    # Handle special commands
    if sys.argv[1] in ['--help', '-h']:
        print_usage()
        sys.exit(0)
    
    config = load_config()
    
    if sys.argv[1] in ['--list', '-l']:
        print(list_agents(config))
        sys.exit(0)
    
    # Normal invocation: agent_name and query
    if len(sys.argv) < 3:
        print("ERROR: Missing query. Please provide both agent name and query.")
        print_usage()
        sys.exit(1)
    
    agent_name = sys.argv[1]
    query = sys.argv[2]
    
    if not query.strip():
        print("Error: Query cannot be empty.")
        sys.exit(1)
    
    # Validate agent name against config
    agent_info = get_agent_info(config, agent_name)
    available_agents = get_available_agents(config)
    
    if not agent_info:
        print(f"❌ Agent '{agent_name}' not found in configuration.")
        print("")
        print("Please either:")
        print("  1. Select from the available agents below")
        print(f"  2. Add your agent to the config file: {get_config_path()}")
        print("")
        print(list_agents(config))
        sys.exit(1)
    
    # Use the exact agent name from config
    actual_agent_name = agent_info['name']
    endpoint = config.get('endpoint', '')
    
    if not endpoint:
        print("ERROR: No endpoint configured in agents-config.yaml")
        sys.exit(1)
    
    print(f"Invoking agent: {actual_agent_name}", file=sys.stderr)
    print(f"Query: {query[:50]}{'...' if len(query) > 50 else ''}", file=sys.stderr)
    
    response = invoke_agent(endpoint, actual_agent_name, query)
    
    # Output the response (stdout for capture, stderr for status messages)
    print(response)


if __name__ == "__main__":
    main()
