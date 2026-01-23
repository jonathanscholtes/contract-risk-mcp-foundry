"""MCP Market Data Server - provides FX rates and market snapshots."""

import sys
from pathlib import Path

# Add shared contracts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))

from datetime import datetime
from typing import Dict, Optional
from mcp.server.fastmcp import FastMCP
import random

# Initialize FastMCP server
mcp = FastMCP("market")


# Simulated market data
MARKET_DATA = {
    "EURUSD": {"spot": 1.0850, "volatility": 0.08},
    "GBPUSD": {"spot": 1.2650, "volatility": 0.09},
    "USDJPY": {"spot": 148.50, "volatility": 0.10},
    "AUDUSD": {"spot": 0.6580, "volatility": 0.11},
    "USDCAD": {"spot": 1.3920, "volatility": 0.07},
    "USDCHF": {"spot": 0.8850, "volatility": 0.08},
}


@mcp.tool()
def get_fx_spot(currency_pair: str) -> Dict[str, float]:
    """
    Get the current FX spot rate for a currency pair.
    
    Args:
        currency_pair: Currency pair (e.g., 'EURUSD')
    
    Returns:
        Dictionary with spot rate and timestamp
    """
    if currency_pair not in MARKET_DATA:
        return {
            "error": f"Currency pair {currency_pair} not supported",
            "spot": 0.0,
        }
    
    data = MARKET_DATA[currency_pair]
    # Add small random noise to simulate market movement
    spot = data["spot"] * (1 + random.uniform(-0.001, 0.001))
    
    return {
        "currency_pair": currency_pair,
        "spot": round(spot, 6),
        "as_of": datetime.utcnow().isoformat(),
    }


@mcp.tool()
def get_fx_volatility(currency_pair: str) -> Dict[str, float]:
    """
    Get the annualized volatility for a currency pair.
    
    Args:
        currency_pair: Currency pair (e.g., 'EURUSD')
    
    Returns:
        Dictionary with volatility and timestamp
    """
    if currency_pair not in MARKET_DATA:
        return {
            "error": f"Currency pair {currency_pair} not supported",
            "volatility": 0.0,
        }
    
    data = MARKET_DATA[currency_pair]
    
    return {
        "currency_pair": currency_pair,
        "volatility": data["volatility"],
        "as_of": datetime.utcnow().isoformat(),
    }


@mcp.tool()
def get_market_snapshot() -> Dict[str, Dict[str, float]]:
    """
    Get a snapshot of all available market data.
    
    Returns:
        Dictionary of all currency pairs with their spot rates and volatilities
    """
    snapshot = {}
    for pair, data in MARKET_DATA.items():
        spot = data["spot"] * (1 + random.uniform(-0.001, 0.001))
        snapshot[pair] = {
            "spot": round(spot, 6),
            "volatility": data["volatility"],
        }
    
    snapshot["as_of"] = datetime.utcnow().isoformat()
    return snapshot


@mcp.tool()
def simulate_shock(currency_pair: str, shock_pct: float) -> Dict[str, float]:
    """
    Simulate a shock scenario for a currency pair.
    
    Args:
        currency_pair: Currency pair (e.g., 'EURUSD')
        shock_pct: Percentage shock (e.g., -3.0 for a 3% drop)
    
    Returns:
        Dictionary with shocked rate and original rate
    """
    if currency_pair not in MARKET_DATA:
        return {
            "error": f"Currency pair {currency_pair} not supported",
        }
    
    original_spot = MARKET_DATA[currency_pair]["spot"]
    shocked_spot = original_spot * (1 + shock_pct / 100)
    
    # Temporarily update market data to reflect shock
    MARKET_DATA[currency_pair]["spot"] = shocked_spot
    
    return {
        "currency_pair": currency_pair,
        "original_spot": round(original_spot, 6),
        "shocked_spot": round(shocked_spot, 6),
        "shock_pct": shock_pct,
        "shock_absolute": round(shocked_spot - original_spot, 6),
        "as_of": datetime.utcnow().isoformat(),
    }


@mcp.tool()
def reset_market_data() -> Dict[str, str]:
    """
    Reset market data to original values.
    
    Returns:
        Confirmation message
    """
    global MARKET_DATA
    MARKET_DATA = {
        "EURUSD": {"spot": 1.0850, "volatility": 0.08},
        "GBPUSD": {"spot": 1.2650, "volatility": 0.09},
        "USDJPY": {"spot": 148.50, "volatility": 0.10},
        "AUDUSD": {"spot": 0.6580, "volatility": 0.11},
        "USDCAD": {"spot": 1.3920, "volatility": 0.07},
        "USDCHF": {"spot": 0.8850, "volatility": 0.08},
    }
    
    return {
        "message": "Market data reset to original values",
        "as_of": datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
