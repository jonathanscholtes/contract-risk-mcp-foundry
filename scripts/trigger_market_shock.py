"""Trigger a market shock scenario by invoking the MarketShockAnalyst agent."""

import asyncio
import os
from azure.identity.aio import DefaultAzureCredential
from azure.ai.projects.aio import AIProjectClient

# Configuration
AZURE_AI_PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT", "https://fnd-risk-demo.services.ai.azure.com")
MARKET_SHOCK_AGENT = "MarketShockAnalyst"


async def trigger_market_shock_scenario():
    """
    Invoke the MarketShockAnalyst to simulate and analyze a market shock.
    The agent will use MCP tools to simulate shocks and analyze portfolio impact.
    """
    
    # Scenario: EUR/USD drops 3%, GBP/USD drops 2.5%
    context = {
        "scenario": "fx_shock_day",
        "instructions": "Simulate a market shock: EURUSD drops 3% and GBPUSD drops 2.5%. Then analyze the impact on the portfolio.",
        "expected_shocks": [
            {"currency_pair": "EURUSD", "shock_pct": -3.0},
            {"currency_pair": "GBPUSD", "shock_pct": -2.5}
        ]
    }
    
    print("=" * 60)
    print("Triggering Market Shock Scenario")
    print("=" * 60)
    print(f"Project: {AZURE_AI_PROJECT_ENDPOINT}")
    print(f"Agent: {MARKET_SHOCK_AGENT}")
    print(f"\nScenario: {context['scenario']}")
    print("=" * 60)
    
    async with DefaultAzureCredential() as credential:
        async with AIProjectClient(
            endpoint=AZURE_AI_PROJECT_ENDPOINT,
            credential=credential
        ) as project_client:
            
            # Get the agent
            agent = await project_client.agents.get_agent(agent_name=MARKET_SHOCK_AGENT)
            print(f"\n[Agent] Retrieved: {agent.name} (id: {agent.id})")
            
            async with project_client.get_openai_client() as openai_client:
                # Create conversation
                conversation = await openai_client.conversations.create()
                print(f"[Conversation] Created: {conversation.id}")
                
                # Add user message
                user_message = f"""Please simulate the following market shock scenario:

{context['instructions']}

Use the simulate_shock tool to apply these shocks, then analyze the portfolio impact using the contract and risk tools.
"""
                
                await openai_client.conversations.items.create(
                    conversation_id=conversation.id,
                    items=[{
                        "type": "message",
                        "role": "user",
                        "content": user_message
                    }]
                )
                
                # Get agent response
                print("\n[Agent] Processing scenario...")
                response = await openai_client.responses.create(
                    conversation=conversation.id,
                    extra_body={
                        "agent": {
                            "name": agent.name,
                            "type": "agent_reference"
                        }
                    },
                    input=""
                )
                
                print("\n" + "=" * 60)
                print("Agent Response")
                print("=" * 60)
                print(response.output_text)
                print("=" * 60)


if __name__ == "__main__":
    asyncio.run(trigger_market_shock_scenario())
