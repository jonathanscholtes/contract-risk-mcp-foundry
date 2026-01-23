"""Risk result data models."""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class FXVaRResult(BaseModel):
    """FX Value at Risk result."""
    
    var: float = Field(..., description="VaR value in base currency")
    confidence: float = Field(..., description="Confidence level (e.g., 0.99)")
    horizon_days: int = Field(..., description="Horizon in days")
    as_of: datetime = Field(..., description="Calculation timestamp")
    simulations: Optional[int] = Field(None, description="Number of simulations run")


class IRDv01Result(BaseModel):
    """Interest Rate DV01 result."""
    
    dv01: float = Field(..., description="Dollar value of a 1bp move")
    currency: str = Field(..., description="Currency")
    as_of: datetime = Field(..., description="Calculation timestamp")


class RiskResult(BaseModel):
    """Risk calculation result."""
    
    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status (succeeded/failed)")
    contract_id: str = Field(..., description="Contract identifier")
    
    result: Optional[Dict[str, Any]] = Field(
        None,
        description="Result data (FXVaRResult or IRDv01Result as dict)"
    )
    
    error: Optional[str] = Field(
        None,
        description="Error message if failed"
    )
    
    completed_at: Optional[datetime] = Field(
        None,
        description="Completion timestamp"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "job-123",
                "status": "succeeded",
                "contract_id": "ctr-001",
                "result": {
                    "var": 125000.12,
                    "confidence": 0.99,
                    "horizon_days": 1,
                    "as_of": "2026-01-23T12:00:00Z"
                }
            }
        }
