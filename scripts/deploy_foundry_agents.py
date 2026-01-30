"""
Deploy Foundry Agents for Contract Risk Sentinel Platform.

This script creates autonomous agents in Microsoft Foundry that are invoked
by the AKS orchestrator for risk analysis tasks.

Usage:
    python scripts/deploy_foundry_agents.py \
        --project-endpoint <PROJECT_ENDPOINT> \
        --model-deployment <MODEL_DEPLOYMENT_NAME> \
        --mcp-contracts-url <MCP_CONTRACTS_URL> \
        --mcp-risk-url <MCP_RISK_URL> \
        --mcp-market-url <MCP_MARKET_URL>
"""

import os
import sys
import argparse
from typing import Dict, List
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, MCPTool


class AgentDeployer:
    """Deploy and manage Foundry agents for risk analysis."""
    
    def __init__(
        self,
        project_endpoint: str,
        model_deployment: str,
        mcp_contracts_url: str,
        mcp_risk_url: str,
        mcp_market_url: str,
    ):
        """Initialize the agent deployer.
        
        Args:
            project_endpoint: Azure AI Foundry project endpoint
            model_deployment: Name of the model deployment to use
            mcp_contracts_url: URL for MCP contracts service
            mcp_risk_url: URL for MCP risk service
            mcp_market_url: URL for MCP market service
        """
        self.project_endpoint = project_endpoint
        self.model_deployment = model_deployment
        self.mcp_contracts_url = mcp_contracts_url
        self.mcp_risk_url = mcp_risk_url
        self.mcp_market_url = mcp_market_url
        
        # Initialize project client
        self.project_client = AIProjectClient(
            endpoint=project_endpoint,
            credential=DefaultAzureCredential(),
        )
        
        self.agents = {}
    
    def _create_mcp_tools(self) -> List[MCPTool]:
        """Create MCP tool configurations for agents.
        
        Returns:
            List of MCP tools configured for the platform
        """
        return [
            MCPTool(
                server_label="mcp-contracts",
                server_url=self.mcp_contracts_url,
                require_approval="never",  # Auto-approve for production
            ),
            MCPTool(
                server_label="mcp-risk",
                server_url=self.mcp_risk_url,
                require_approval="never",
            ),
            MCPTool(
                server_label="mcp-market",
                server_url=self.mcp_market_url,
                require_approval="never",
            ),
        ]
    
    def create_threshold_breach_agent(self) -> Dict:
        """Create agent for threshold breach analysis.
        
        This agent is invoked when risk calculations exceed thresholds.
        It analyzes the breach, generates recommendations, and persists memos.
        
        Returns:
            Agent creation result
        """
        instructions = """
You are a Financial Risk Analyst specializing in contract risk monitoring and breach analysis.

You have access to three MCP tool servers:
1) mcp-contracts: Contract registry, term sheets, and risk memo storage
2) mcp-risk: Risk job submission and result retrieval (FX VaR, IR DV01, stress tests)
3) mcp-market: Market data snapshots (FX rates, volatility, IR curves)

TASK: You are invoked when a risk calculation exceeds configured thresholds.

WORKFLOW:
1. Receive breach context with:
   - contract_id: The contract that breached
   - risk_result: The computed risk metrics (var, dv01, etc.)
   - breach_details: Specific threshold violations
   - timestamp: When the breach occurred

2. Retrieve contract details:
   - Use get_contract(contract_id) to get full contract information
   - Review contract type, notional, maturity, underlying assets

3. Analyze the breach:
   - Compare current risk metrics to historical patterns
   - Consider market conditions using get_fx_spot() and get_market_snapshot()
   - Assess severity and urgency

4. Determine risk calculation type:
   - Check contract type from get_contract()
   - For IRS (Interest Rate Swap) contracts: use run_ir_dv01()
   - For FX contracts: use run_fx_var()
   - For other derivatives: use appropriate calculation

5. Generate recommendations:
   - Suggest hedging strategies (if applicable)
   - Recommend position adjustments
   - Identify monitoring priorities

6. Persist analysis:
   - Use write_risk_memo() to store your analysis
   - Include: breach summary, root cause, recommendations, urgency level

OUTPUT FORMAT:
- Be concise but comprehensive
- Use specific contract IDs and risk values
- Provide actionable recommendations
- Flag critical issues requiring immediate attention

RULES:
- Only use data from MCP tools - do not fabricate values
- Always cite contract_id, job_id, and timestamps
- If data is missing, state what's needed and which tool to call
- Use proper risk terminology (VaR, DV01, notional, spot, etc.)
- IMPORTANT: Match risk calculation to contract type (IRS→DV01, FX→VaR)
"""
        
        agent = self.project_client.agents.create_version(
            agent_name="ThresholdBreachAnalyst",
            definition=PromptAgentDefinition(
                model=self.model_deployment,
                instructions=instructions,
                tools=self._create_mcp_tools(),
            ),
        )
        
        self.agents["threshold_breach"] = agent
        print(f"✓ Created ThresholdBreachAnalyst (id: {agent.id}, version: {agent.version})")
        return {"id": agent.id, "name": agent.name, "version": agent.version}
    
    def create_market_shock_agent(self) -> Dict:
        """Create agent for market shock assessment.
        
        This agent is invoked when significant market movements are detected.
        It performs portfolio-wide risk reassessment.
        
        Returns:
            Agent creation result
        """
        instructions = """
You are a Senior Risk Manager specializing in market shock analysis and portfolio stress testing.

You have access to three MCP tool servers:
1) mcp-contracts: Contract registry, term sheets, and risk memo storage
2) mcp-risk: Risk job submission and result retrieval (FX VaR, IR DV01, stress tests)
3) mcp-market: Market data snapshots (FX rates, volatility, IR curves)

TASK: You are invoked when significant market movements are detected (e.g., FX rate shock, volatility spike).

WORKFLOW:
1. Receive shock context with:
   - shock_event: Details of the market movement
   - currency_pair or risk_factor: What moved
   - shock_pct: Magnitude of the movement
   - timestamp: When detected

2. Identify exposed contracts:
   - Use search_contracts() with currency_pair filter
   - Focus on contracts with significant exposure to the shocked asset

3. Submit risk recalculations:
   - For IRS contracts: call run_ir_dv01()
   - For FX contracts: call run_fx_var()
   - Check contract type before calling appropriate calculation
   - Track job_ids for polling

4. Poll for results:
   - Use get_risk_result(job_id) until all jobs complete
   - Handle failures gracefully

5. Analyze portfolio impact:
   - Aggregate total VaR and DV01 exposure
   - Identify contracts with highest sensitivity
   - Compare to pre-shock risk levels

6. Generate portfolio memo:
   - Use write_risk_memo() for each critical contract
   - Create summary-level memo for portfolio-wide impact

7. Prioritize actions:
   - Flag contracts exceeding emergency thresholds
   - Recommend immediate hedging or position review
   - Schedule follow-up monitoring

OUTPUT FORMAT:
- Start with executive summary of portfolio impact
- List critical contracts in order of severity
- Provide specific risk metrics (current vs. threshold)
- Give clear, actionable recommendations

RULES:
- Process exposed contracts in batches if portfolio is large
- Always cite contract_ids, job_ids, and risk values
- Use get_market_snapshot() for current market conditions
- If jobs fail, log errors and continue with available results
- Distinguish between critical breaches and elevated risk
- CRITICAL: Use run_ir_dv01() for IRS contracts, run_fx_var() for FX contracts
"""
        
        agent = self.project_client.agents.create_version(
            agent_name="MarketShockAnalyst",
            definition=PromptAgentDefinition(
                model=self.model_deployment,
                instructions=instructions,
                tools=self._create_mcp_tools(),
            ),
        )
        
        self.agents["market_shock"] = agent
        print(f"✓ Created MarketShockAnalyst (id: {agent.id}, version: {agent.version})")
        return {"id": agent.id, "name": agent.name, "version": agent.version}
    
    def create_portfolio_scan_agent(self) -> Dict:
        """Create agent for scheduled portfolio risk scans.
        
        This agent performs comprehensive daily/intraday risk assessments
        of the entire portfolio.
        
        Returns:
            Agent creation result
        """
        instructions = """
You are a Chief Risk Officer responsible for comprehensive portfolio risk monitoring and reporting.

You have access to three MCP tool servers:
1) mcp-contracts: Contract registry, term sheets, and risk memo storage
2) mcp-risk: Risk job submission and result retrieval (FX VaR, IR DV01, stress tests)
3) mcp-market: Market data snapshots (FX rates, volatility, IR curves)

TASK: You are invoked on a schedule (daily at 8 AM UTC, intraday every 4 hours) to perform comprehensive portfolio risk assessment.

WORKFLOW:
1. Receive scan context with:
   - scan_type: "comprehensive" or "intraday"
   - timestamp: Current scan time

2. Retrieve current market conditions:
   - Use get_market_snapshot() for all relevant FX pairs and IR curves
   - Note any significant market movements since last scan

3. Retrieve all active contracts:
   - Use search_contracts() with appropriate filters
   - Focus on contracts approaching maturity or with large notionals

4. Submit risk calculations:
   - For each contract, retrieve contract type from get_contract()
   - For IRS (Interest Rate Swap) contracts: call run_ir_dv01()
   - For FX contracts: call run_fx_var()
   - Consider running stress tests for critical positions
   - Track all job_ids

5. Poll for results:
   - Use get_risk_result(job_id) for each job
   - Handle timeouts and failures gracefully
   - Continue processing even if some jobs fail

6. Analyze portfolio-wide risk:
   - Aggregate total FX VaR and IR DV01
   - Identify top 10 riskiest contracts
   - Compare to historical risk levels
   - Flag trends (increasing/decreasing risk)

7. Generate executive summary:
   - Create portfolio-level risk memo using write_risk_memo()
   - Include:
     * Total portfolio metrics
     * Top risks and concentrations
     * Threshold breach summary
     * Recommended actions
     * Upcoming maturities requiring attention

8. Flag critical issues:
   - Identify contracts requiring immediate review
   - Highlight new threshold breaches since last scan
   - Note contracts with significant risk increase

OUTPUT FORMAT:
- Executive summary with key metrics
- Risk concentrations by currency pair, counterparty, maturity
- Top 10 riskiest contracts with specific metrics
- Action items prioritized by urgency
- Trends and observations compared to previous scan

RULES:
- Process large portfolios in batches to avoid timeout
- Always include timestamps and job_ids in memos
- If scan type is "intraday", focus on changes since last scan
- If scan type is "comprehensive", perform full assessment
- Flag stale risk data (jobs that haven't refreshed recently)
- Use consistent memo_id format: "portfolio_scan_{timestamp}"
- CRITICAL: Always check contract type - use run_ir_dv01() for IRS, run_fx_var() for FX
"""
        
        agent = self.project_client.agents.create_version(
            agent_name="PortfolioScanAnalyst",
            definition=PromptAgentDefinition(
                model=self.model_deployment,
                instructions=instructions,
                tools=self._create_mcp_tools(),
            ),
        )
        
        self.agents["portfolio_scan"] = agent
        print(f"✓ Created PortfolioScanAnalyst (id: {agent.id}, version: {agent.version})")
        return {"id": agent.id, "name": agent.name, "version": agent.version}
    
    def deploy_all_agents(self) -> Dict:
        """Deploy all agents for the platform.
        
        Returns:
            Dictionary with agent creation results
        """
        print("\n" + "=" * 70)
        print("Deploying Foundry Agents for Contract Risk Sentinel")
        print("=" * 70)
        print(f"Project Endpoint: {self.project_endpoint}")
        print(f"Model Deployment: {self.model_deployment}")
        print(f"MCP Contracts: {self.mcp_contracts_url}")
        print(f"MCP Risk: {self.mcp_risk_url}")
        print(f"MCP Market: {self.mcp_market_url}")
        print("=" * 70 + "\n")
        
        results = {}
        
        try:
            print("Creating agents...")
            results["threshold_breach"] = self.create_threshold_breach_agent()
            results["market_shock"] = self.create_market_shock_agent()
            results["portfolio_scan"] = self.create_portfolio_scan_agent()
            
            print("\n" + "=" * 70)
            print("[OK] All agents deployed successfully!")
            print("=" * 70)
            print("\nAgent Summary:")
            for task, agent in results.items():
                print(f"  {task}:")
                print(f"    Name: {agent['name']}")
                print(f"    ID: {agent['id']}")
                print(f"    Version: {agent['version']}")
            
            print("\n" + "=" * 70)
            print("Next Steps:")
            print("=" * 70)
            print("1. Update AKS orchestrator with agent endpoint and API key")
            print("2. Configure kubectl secret:")
            print("   kubectl create secret generic foundry-agent-secret -n tools \\")
            print(f"     --from-literal=endpoint={self.project_endpoint} \\")
            print("     --from-literal=api-key=<YOUR_API_KEY>")
            print("\n3. Test agent invocation:")
            print("   python scripts/test_agent_invocation.py")
            print("\n")
            
            return results
            
        except Exception as e:
            print(f"\n[X] Error deploying agents: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    def cleanup_agents(self):
        """Delete all deployed agents (useful for redeployment)."""
        print("\nCleaning up agents...")
        for task, agent in self.agents.items():
            try:
                self.project_client.agents.delete_version(
                    agent_name=agent.name,
                    agent_version=agent.version
                )
                print(f"[OK] Deleted {agent.name}")
            except Exception as e:
                print(f"[X] Error deleting {agent.name}: {e}")


def main():
    """Main entry point for agent deployment."""
    parser = argparse.ArgumentParser(
        description="Deploy Foundry agents for Contract Risk Sentinel platform"
    )
    parser.add_argument(
        "--project-endpoint",
        required=True,
        help="Azure AI Foundry project endpoint"
    )
    parser.add_argument(
        "--model-deployment",
        required=True,
        help="Model deployment name (e.g., 'gpt-4o')"
    )
    parser.add_argument(
        "--mcp-contracts-url",
        default="http://mcp-contracts.tools.svc.cluster.local:8000",
        help="MCP contracts service URL"
    )
    parser.add_argument(
        "--mcp-risk-url",
        default="http://mcp-risk.tools.svc.cluster.local:8000",
        help="MCP risk service URL"
    )
    parser.add_argument(
        "--mcp-market-url",
        default="http://mcp-market.tools.svc.cluster.local:8000",
        help="MCP market service URL"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up existing agents before deployment"
    )
    
    args = parser.parse_args()
    
    # Create deployer
    deployer = AgentDeployer(
        project_endpoint=args.project_endpoint,
        model_deployment=args.model_deployment,
        mcp_contracts_url=args.mcp_contracts_url,
        mcp_risk_url=args.mcp_risk_url,
        mcp_market_url=args.mcp_market_url,
    )
    
    # Deploy agents
    results = deployer.deploy_all_agents()
    
    # Optionally cleanup after deployment (for testing)
    if args.cleanup:
        deployer.cleanup_agents()
    
    return results


if __name__ == "__main__":
    main()
