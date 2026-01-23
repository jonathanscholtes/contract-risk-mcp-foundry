"""Risk job data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class RiskJobType(str, Enum):
    """Types of risk calculations."""
    FX_VAR = "fx_var"
    IR_DV01 = "ir_dv01"
    STRESS_TEST = "stress_test"


class RiskJobStatus(str, Enum):
    """Status of a risk job."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RiskJob(BaseModel):
    """Risk calculation job."""
    
    job_id: str = Field(..., description="Unique job identifier")
    job_type: RiskJobType = Field(..., description="Type of risk calculation")
    contract_id: str = Field(..., description="Contract to analyze")
    
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Job-specific parameters"
    )
    
    idempotency_key: str = Field(
        ...,
        description="Key to prevent duplicate processing"
    )
    
    submitted_at: Optional[datetime] = Field(
        None,
        description="Job submission timestamp"
    )
    
    status: RiskJobStatus = Field(
        default=RiskJobStatus.PENDING,
        description="Current job status"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "job-123",
                "job_type": "fx_var",
                "contract_id": "ctr-001",
                "params": {
                    "horizon_days": 1,
                    "sims": 20000,
                    "confidence": 0.99
                },
                "idempotency_key": "ctr-001|fx_var|2026-01-23"
            }
        }
