"""Contract data models."""

from datetime import date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ContractType(str, Enum):
    """Types of financial contracts."""
    FX_FORWARD = "fx_forward"
    FX_SWAP = "fx_swap"
    IRS = "interest_rate_swap"
    CROSS_CURRENCY_SWAP = "cross_currency_swap"


class CurrencyPair(str, Enum):
    """Supported currency pairs."""
    EURUSD = "EURUSD"
    GBPUSD = "GBPUSD"
    USDJPY = "USDJPY"
    AUDUSD = "AUDUSD"
    USDCAD = "USDCAD"
    USDCHF = "USDCHF"


class Contract(BaseModel):
    """Financial contract with risk exposures."""
    
    contract_id: str = Field(..., description="Unique contract identifier")
    contract_type: ContractType = Field(..., description="Type of contract")
    counterparty: str = Field(..., description="Counterparty name")
    
    # FX specific
    currency_pair: Optional[CurrencyPair] = Field(None, description="Currency pair for FX contracts")
    notional_base: Optional[float] = Field(None, description="Notional in base currency")
    notional_quote: Optional[float] = Field(None, description="Notional in quote currency")
    strike_rate: Optional[float] = Field(None, description="Contract exchange rate")
    
    # IR specific
    fixed_rate: Optional[float] = Field(None, description="Fixed rate for IR swaps")
    notional: Optional[float] = Field(None, description="Notional for IR swaps")
    currency: Optional[str] = Field(None, description="Currency for IR swaps")
    
    # Common
    trade_date: date = Field(..., description="Trade date")
    maturity_date: date = Field(..., description="Maturity date")
    
    # Risk memo tracking
    last_risk_memo_date: Optional[date] = Field(None, description="Date of last risk assessment")
    
    class Config:
        json_schema_extra = {
            "example": {
                "contract_id": "ctr-001",
                "contract_type": "fx_forward",
                "counterparty": "ABC Bank",
                "currency_pair": "EURUSD",
                "notional_base": 1000000.0,
                "notional_quote": 1100000.0,
                "strike_rate": 1.10,
                "trade_date": "2026-01-15",
                "maturity_date": "2026-07-15"
            }
        }
