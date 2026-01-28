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
    Get the current FX spot rate for a currency pair from MongoDB.
    
    Args:
        currency_pair: Currency pair (e.g., 'EURUSD')
    
    Returns:
        Dictionary with spot rate and timestamp
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
    Get the annualized volatility for a currency pair from MongoDB.
    
    Args:
        currency_pair: Currency pair (e.g., 'EURUSD')
    
    Returns:
        Dictionary with volatility and timestamp
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
    Get a snapshot of all available market data from MongoDB.
    
    Returns:
        Dictionary of all currency pairs with their spot rates and volatilities
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
