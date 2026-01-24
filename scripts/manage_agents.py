"""
List and manage deployed Foundry agents.

This script helps you view, inspect, and manage agents deployed
to Microsoft Foundry for the Contract Risk Sentinel platform.

Usage:
    # List all agents
    python scripts/manage_agents.py --project-endpoint <ENDPOINT> --action list

    # Get agent details
    python scripts/manage_agents.py --project-endpoint <ENDPOINT> --action details --agent-name ThresholdBreachAnalyst

    # Delete an agent version
    python scripts/manage_agents.py --project-endpoint <ENDPOINT> --action delete --agent-name ThresholdBreachAnalyst --version 1
"""

import argparse
import sys
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient


class AgentManager:
    """Manage Foundry agents for the platform."""
    
    def __init__(self, project_endpoint: str):
        """Initialize the agent manager.
        
        Args:
            project_endpoint: Azure AI Foundry project endpoint
        """
        self.project_endpoint = project_endpoint
        self.project_client = AIProjectClient(
            endpoint=project_endpoint,
            credential=DefaultAzureCredential(),
        )
    
    def list_agents(self):
        """List all deployed agents."""
        print("\n" + "=" * 70)
        print("Deployed Foundry Agents")
        print("=" * 70)
        print(f"Project: {self.project_endpoint}\n")
        
        try:
            # Note: You may need to adjust this based on the actual Azure AI SDK API
            # This is a placeholder for listing agents
            print("Platform Agents:")
            agent_names = [
                "ThresholdBreachAnalyst",
                "MarketShockAnalyst",
                "PortfolioScanAnalyst",
            ]
            
            for agent_name in agent_names:
                try:
                    # Try to get the agent to verify it exists
                    agent = self.project_client.agents.get(agent_name=agent_name)
                    print(f"  ✓ {agent_name}")
                    print(f"    ID: {agent.id}")
                    print(f"    Version: {agent.version}")
                    print(f"    Model: {agent.model}")
                    print()
                except Exception as e:
                    print(f"  ✗ {agent_name} - Not found or error: {str(e)[:50]}")
            
        except Exception as e:
            print(f"Error listing agents: {e}")
            import traceback
            traceback.print_exc()
    
    def get_agent_details(self, agent_name: str, version: str = None):
        """Get detailed information about an agent.
        
        Args:
            agent_name: Name of the agent
            version: Optional version (defaults to latest)
        """
        print("\n" + "=" * 70)
        print(f"Agent Details: {agent_name}")
        print("=" * 70)
        
        try:
            if version:
                agent = self.project_client.agents.get_version(
                    agent_name=agent_name,
                    agent_version=version
                )
            else:
                agent = self.project_client.agents.get(agent_name=agent_name)
            
            print(f"Name: {agent.name}")
            print(f"ID: {agent.id}")
            print(f"Version: {agent.version}")
            print(f"Model: {agent.model}")
            print(f"\nInstructions (first 500 chars):")
            print("-" * 70)
            print(agent.instructions[:500] + "..." if len(agent.instructions) > 500 else agent.instructions)
            print("-" * 70)
            
            if hasattr(agent, 'tools'):
                print(f"\nTools: {len(agent.tools)} configured")
                for i, tool in enumerate(agent.tools, 1):
                    if hasattr(tool, 'server_label'):
                        print(f"  {i}. MCP Tool: {tool.server_label}")
                        if hasattr(tool, 'server_url'):
                            print(f"     URL: {tool.server_url}")
            
            print("\n" + "=" * 70)
            
        except Exception as e:
            print(f"Error getting agent details: {e}")
            import traceback
            traceback.print_exc()
    
    def delete_agent(self, agent_name: str, version: str):
        """Delete an agent version.
        
        Args:
            agent_name: Name of the agent
            version: Version to delete
        """
        print("\n" + "=" * 70)
        print(f"Deleting Agent: {agent_name} (version {version})")
        print("=" * 70)
        
        try:
            confirm = input(f"Are you sure you want to delete {agent_name} v{version}? (yes/no): ")
            if confirm.lower() != 'yes':
                print("Deletion cancelled.")
                return
            
            self.project_client.agents.delete_version(
                agent_name=agent_name,
                agent_version=version
            )
            
            print(f"✓ Successfully deleted {agent_name} version {version}")
            
        except Exception as e:
            print(f"Error deleting agent: {e}")
            import traceback
            traceback.print_exc()
    
    def show_agent_summary(self):
        """Show a summary of all platform agents and their purposes."""
        print("\n" + "=" * 70)
        print("Contract Risk Sentinel - Agent Architecture")
        print("=" * 70)
        
        agents_info = [
            {
                "name": "ThresholdBreachAnalyst",
                "trigger": "Risk metric exceeds threshold",
                "purpose": "Analyze contract breaches and generate recommendations",
                "tools": ["contracts", "risk", "market"],
            },
            {
                "name": "MarketShockAnalyst",
                "trigger": "Significant market movement detected",
                "purpose": "Portfolio-wide risk reassessment after shocks",
                "tools": ["contracts", "risk", "market"],
            },
            {
                "name": "PortfolioScanAnalyst",
                "trigger": "Scheduled (8 AM UTC, every 4 hours)",
                "purpose": "Comprehensive portfolio risk analysis",
                "tools": ["contracts", "risk", "market"],
            },
        ]
        
        for agent in agents_info:
            print(f"\n{agent['name']}")
            print(f"  Trigger: {agent['trigger']}")
            print(f"  Purpose: {agent['purpose']}")
            print(f"  MCP Tools: {', '.join(agent['tools'])}")
        
        print("\n" + "=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Manage Foundry agents for Contract Risk Sentinel"
    )
    parser.add_argument(
        "--project-endpoint",
        required=True,
        help="Azure AI Foundry project endpoint"
    )
    parser.add_argument(
        "--action",
        choices=["list", "details", "delete", "summary"],
        default="list",
        help="Action to perform"
    )
    parser.add_argument(
        "--agent-name",
        help="Agent name (required for details and delete actions)"
    )
    parser.add_argument(
        "--version",
        help="Agent version (optional for details, required for delete)"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.action in ["details", "delete"] and not args.agent_name:
        parser.error(f"--agent-name is required for action '{args.action}'")
    
    if args.action == "delete" and not args.version:
        parser.error("--version is required for delete action")
    
    # Create manager
    manager = AgentManager(args.project_endpoint)
    
    # Execute action
    if args.action == "list":
        manager.list_agents()
    elif args.action == "details":
        manager.get_agent_details(args.agent_name, args.version)
    elif args.action == "delete":
        manager.delete_agent(args.agent_name, args.version)
    elif args.action == "summary":
        manager.show_agent_summary()


if __name__ == "__main__":
    main()
