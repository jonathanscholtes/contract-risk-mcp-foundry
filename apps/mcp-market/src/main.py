"""MCP Market Data Server - provides FX rates and market snapshots."""

import sys
from pathlib import Path

# Add shared contracts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))

from datetime import datetime
from typing import Dict, Optional, Any

import os
from mcp.server.fastmcp import FastMCP
import random
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# Initialize FastMCP server with explicit host/port
mcp = FastMCP(
    name="market",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8000)),
    stateless_http=True,
)

# MongoDB configuration
MONGODB_CONNECTION_STRING = os.getenv("MONGODB_CONNECTION_STRING", "")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "market_db")
MONGODB_MARKET_COLLECTION = os.getenv("MONGODB_MARKET_COLLECTION", "market_data")

# Initialize MongoDB client
mongo_client = None
market_collection = None

def init_mongodb():
    """Initialize MongoDB connection and collections."""
    global mongo_client, market_collection
    
    if not MONGODB_CONNECTION_STRING:
        print("WARNING: MONGODB_CONNECTION_STRING not set. Using in-memory market data.")
        return False
    
    try:
        mongo_client = MongoClient(MONGODB_CONNECTION_STRING)
        db = mongo_client[MONGODB_DATABASE]
        market_collection = db[MONGODB_MARKET_COLLECTION]
        market_collection.create_index("currency_pair", unique=True)
        
        # Test connection
        mongo_client.admin.command('ping')
        print(f"Successfully connected to MongoDB: {MONGODB_DATABASE}")
        return True
    except PyMongoError as e:
        print(f"Failed to connect to MongoDB: {e}")
        print("Falling back to in-memory market data.")
        return False

# In-memory fallback data
market_store: Dict[str, Dict] = {}

# Initialize MongoDB on startup
mongodb_enabled = init_mongodb()


@mcp.tool()
async def get_fx_spot(currency_pair: str) -> Dict[str, Any]:
    """
    Get the current FX spot rate for a currency pair.
    
    Use this tool to:
    - Get current market prices for risk context
    - Check if market data is available before submitting risk jobs
    - Assess market conditions for breach analysis
    
    Args:
        currency_pair: Currency pair code (e.g., 'EURUSD', 'GBPJPY', 'AUDUSD')
    
    Returns:
        Dictionary with:
        - spot: Current FX spot rate
        - as_of: Timestamp of the market data
        - currency_pair: The requested pair
    
    Example:
        - get_fx_spot('EURUSD') → {'spot': 1.0850, 'as_of': '2024-01-30T14:30:00Z'}
    """
    # Try MongoDB first
    if mongodb_enabled and market_collection is not None:
        try:
            doc = market_collection.find_one({"currency_pair": currency_pair})
            if doc:
                return {
                    "currency_pair": currency_pair,
                    "spot": doc.get("spot", 0.0),
                    "as_of": doc.get("as_of", datetime.utcnow().isoformat()),
                }
        except PyMongoError as e:
            print(f"MongoDB error fetching {currency_pair}: {e}")
    
    # Fallback to in-memory data
    if currency_pair in market_store:
        data = market_store[currency_pair]
        return {
            "currency_pair": currency_pair,
            "spot": data.get("spot", 0.0),
            "as_of": data.get("as_of", datetime.utcnow().isoformat()),
        }
    
    # Not found
    return {
        "error": f"Currency pair {currency_pair} not found",
        "spot": 0.0,
    }


@mcp.tool()
async def get_fx_volatility(currency_pair: str) -> Dict[str, Any]:
    """
    Get the current annualized FX volatility for a currency pair.
    
    Use this tool to:
    - Understand current market volatility for risk assessment
    - Compare volatility across currency pairs
    - Assess market stress (volatility spikes indicate market stress)
    
    Args:
        currency_pair: Currency pair code (e.g., 'EURUSD', 'GBPJPY')
    
    Returns:
        Dictionary with:
        - volatility: Annualized volatility (0.10 = 10% annualized)
        - as_of: Timestamp of the market data
        - currency_pair: The requested pair
    
    Interpretation:
        - 0.08 = Low volatility (calm markets)
        - 0.12 = Elevated volatility (some stress)
        - 0.18+ = High volatility (market shock conditions)
    """
    # Try MongoDB first
    if mongodb_enabled and market_collection is not None:
        try:
            doc = market_collection.find_one({"currency_pair": currency_pair})
            if doc:
                return {
                    "currency_pair": currency_pair,
                    "volatility": doc.get("volatility", 0.0),
                    "as_of": doc.get("as_of", datetime.utcnow().isoformat()),
                }
        except PyMongoError as e:
            print(f"MongoDB error fetching {currency_pair}: {e}")
    
    # Fallback to in-memory data
    if currency_pair in market_store:
        data = market_store[currency_pair]
        return {
            "currency_pair": currency_pair,
            "volatility": data.get("volatility", 0.0),
            "as_of": data.get("as_of", datetime.utcnow().isoformat()),
        }
    
    # Not found
    return {
        "error": f"Currency pair {currency_pair} not found",
        "volatility": 0.0,
    }


@mcp.tool()
async def get_market_snapshot() -> Dict[str, Any]:
    """
    Get a complete snapshot of all available market data (all currency pairs, rates, volatilities).
    
    Use this tool to:
    - Assess overall market conditions in one call
    - Check which currency pairs have available data
    - Identify which currency pairs are experiencing volatility spikes
    - Get comprehensive market context for portfolio risk assessment
    
    Returns:
        Dictionary with:
        - [currency_pair]: Dictionary with 'spot' rate and 'volatility' for each pair
        - as_of: Timestamp of the snapshot
    
    Example Response:
        {
          'EURUSD': {'spot': 1.0850, 'volatility': 0.10},
          'GBPJPY': {'spot': 168.50, 'volatility': 0.12},
          'as_of': '2024-01-30T14:30:00Z'
        }
    
    Workflow for Market Shock Assessment:
        1. Call get_market_snapshot() to get current conditions
        2. Compare volatilities - if any spike significantly, may indicate shock
        3. Find affected contracts with search_contracts(currency_pair=...)
        4. Submit fresh risk calculations for those contracts
        5. Compare new VaR to historical patterns
    """
    snapshot = {}
    
    # Try MongoDB first
    if mongodb_enabled and market_collection is not None:
        try:
            docs = market_collection.find({})
            for doc in docs:
                pair = doc.get("currency_pair")
                if pair:
                    snapshot[pair] = {
                        "spot": doc.get("spot", 0.0),
                        "volatility": doc.get("volatility", 0.0),
                    }
            if snapshot:
                snapshot["as_of"] = datetime.utcnow().isoformat()
                return snapshot
        except PyMongoError as e:
            print(f"MongoDB error fetching snapshot: {e}")
    
    # Fallback to in-memory data
    for pair, data in market_store.items():
        snapshot[pair] = {
            "spot": data.get("spot", 0.0),
            "volatility": data.get("volatility", 0.0),
        }
    
    snapshot["as_of"] = datetime.utcnow().isoformat()
    return snapshot


@mcp.tool()
async def simulate_shock(currency_pair: str, shock_pct: float) -> Dict[str, Any]:
    """
    Simulate a shock scenario for a currency pair.
    Returns the shocked value without persisting it.
    
    Args:
        currency_pair: Currency pair (e.g., 'EURUSD')
        shock_pct: Percentage shock (e.g., -3.0 for a 3% drop)
    
    Returns:
        Dictionary with shocked rate and original rate
    """
    original_spot = None
    
    # Try to get original spot from MongoDB
    if mongodb_enabled and market_collection is not None:
        try:
            doc = market_collection.find_one({"currency_pair": currency_pair})
            if doc:
                original_spot = doc.get("spot")
        except PyMongoError as e:
            print(f"MongoDB error: {e}")
    
    # Fallback to in-memory
    if original_spot is None and currency_pair in market_store:
        original_spot = market_store[currency_pair].get("spot")
    
    # Not found
    if original_spot is None:
        return {
            "error": f"Currency pair {currency_pair} not found",
        }
    
    shocked_spot = original_spot * (1 + shock_pct / 100)
    
    return {
        "currency_pair": currency_pair,
        "original_spot": round(original_spot, 6),
        "shocked_spot": round(shocked_spot, 6),
        "shock_pct": shock_pct,
        "shock_absolute": round(shocked_spot - original_spot, 6),
        "as_of": datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run(transport="streamable-http")
