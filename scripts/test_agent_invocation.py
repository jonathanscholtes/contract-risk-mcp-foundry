"""
Test Foundry Agent Invocation.

This script tests that deployed agents can be successfully invoked
and can communicate with MCP services.

Usage:
    python scripts/test_agent_invocation.py \
        --project-endpoint <PROJECT_ENDPOINT> \
        --agent-name <AGENT_NAME>
"""

import os
import sys
import argparse
import asyncio
from typing import Dict
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient


async def test_agent_invocation(
    project_endpoint: str,
    agent_name: str,
    test_task: str,
    test_context: Dict,
):
    """Test agent invocation with a sample task.
    
    Args:
        project_endpoint: Azure AI Foundry project endpoint
        agent_name: Name of the agent to test
        test_task: Test task description
        test_context: Test context data
    """
    print("\n" + "=" * 70)
    print("Testing Foundry Agent Invocation")
    print("=" * 70)
    print(f"Project Endpoint: {project_endpoint}")
    print(f"Agent Name: {agent_name}")
    print(f"Test Task: {test_task}")
    print("=" * 70 + "\n")
    
    try:
        # Initialize project client
        project_client = AIProjectClient(
            endpoint=project_endpoint,
            credential=DefaultAzureCredential(),
        )
        
        openai_client = project_client.get_openai_client()
        
        # Create a conversation
        print("Creating conversation...")
        conversation = openai_client.conversations.create()
        print(f"✓ Conversation created (id: {conversation.id})")
        
        # Send test request
        print(f"\nSending test request to agent '{agent_name}'...")
        response = openai_client.responses.create(
            conversation=conversation.id,
            input=f"Task: {test_task}\nContext: {test_context}",
            extra_body={"agent": {"name": agent_name, "type": "agent_reference"}},
        )
        
        print("\n" + "=" * 70)
        print("Agent Response:")
        print("=" * 70)
        print(response.output_text)
        print("=" * 70 + "\n")
        
        # Check if MCP tool calls were made
        mcp_calls = []
        for item in response.output:
            if hasattr(item, 'type') and 'mcp' in item.type.lower():
                mcp_calls.append(item)
        
        if mcp_calls:
            print(f"✓ Agent made {len(mcp_calls)} MCP tool call(s)")
            print("  MCP integration working correctly!")
        else:
            print("⚠ No MCP tool calls detected in this test")
            print("  This may be expected depending on the test task")
        
        print("\n✓ Agent invocation test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n✗ Error testing agent: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point for agent testing."""
    parser = argparse.ArgumentParser(
        description="Test Foundry agent invocation"
    )
    parser.add_argument(
        "--project-endpoint",
        required=True,
        help="Azure AI Foundry project endpoint"
    )
    parser.add_argument(
        "--agent-name",
        default="ThresholdBreachAnalyst",
        help="Agent name to test (default: ThresholdBreachAnalyst)"
    )
    
    args = parser.parse_args()
    
    # Define test scenarios based on agent type
    test_scenarios = {
        "ThresholdBreachAnalyst": {
            "task": "threshold_breach_analysis",
            "context": {
                "contract_id": "test-contract-001",
                "risk_result": {
                    "var": 150000.00,
                    "dv01": 45000.00,
                },
                "breach_details": [
                    "FX VaR $150,000.00 exceeds threshold $100,000.00"
                ],
                "timestamp": "2024-01-24T10:00:00Z"
            }
        },
        "MarketShockAnalyst": {
            "task": "market_shock_assessment",
            "context": {
                "shock_event": {
                    "currency_pair": "EURUSD",
                    "shock_pct": -2.5,
                    "volatility": 0.18,
                },
                "timestamp": "2024-01-24T10:00:00Z"
            }
        },
        "PortfolioScanAnalyst": {
            "task": "daily_portfolio_risk_scan",
            "context": {
                "scan_type": "comprehensive",
                "timestamp": "2024-01-24T08:00:00Z"
            }
        }
    }
    
    # Get test scenario for the specified agent
    scenario = test_scenarios.get(
        args.agent_name,
        test_scenarios["ThresholdBreachAnalyst"]
    )
    
    # Run async test
    success = asyncio.run(
        test_agent_invocation(
            project_endpoint=args.project_endpoint,
            agent_name=args.agent_name,
            test_task=scenario["task"],
            test_context=scenario["context"],
        )
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
