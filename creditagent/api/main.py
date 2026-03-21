"""
api/main.py — FastAPI credit assessment API.
"""

import sys
import os
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import time

from agents.orchestrator import OrchestratorAgent
from mock_data.personas import PERSONAS

app = FastAPI(
    title="CreditAgent API",
    description="AI Multi-Agent Credit Assessment System for SMEs",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single orchestrator instance (model loaded once)
_orchestrator = None


def get_orchestrator() -> OrchestratorAgent:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = OrchestratorAgent()
    return _orchestrator


# ── Request / Response models ────────────────────────────────────────────────

class AssessRequest(BaseModel):
    borrower_id: str


class CreditAssessmentResult(BaseModel):
    borrower_id: str
    borrower_name: str
    scenario: Optional[str] = None
    composite_score: int
    risk_tier: str
    decision: str
    credit_limit: float
    interest_rate_range: str
    financial_score: int
    alternative_score: int
    is_underbanked: bool
    key_strengths: List[str]
    key_concerns: List[str]
    report: str
    bias_detected: bool
    fairness_metrics: Dict[str, Any]
    processing_time_ms: int
    data_completeness: float
    shap_summary: Dict[str, float]
    score_breakdown: Dict[str, Any]
    alternative_signals: Dict[str, Any]
    agent_pipeline: List[Dict[str, Any]]
    confidence: float


class PersonaInfo(BaseModel):
    borrower_id: str
    name: str
    scenario: str
    expected_decision: str
    has_bank_data: bool


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "CreditAgent API"}


@app.get("/personas", response_model=List[PersonaInfo])
def list_personas():
    """List all available demo personas."""
    return [
        PersonaInfo(
            borrower_id=bid,
            name=p["name"],
            scenario=p["scenario"],
            expected_decision=p["expected_decision"],
            has_bank_data=p.get("bank_data") is not None,
        )
        for bid, p in PERSONAS.items()
    ]


@app.post("/assess", response_model=CreditAssessmentResult)
def assess(request: AssessRequest):
    """
    Run full credit assessment for a borrower.

    Body: {"borrower_id": "borrower_001"}
    """
    if request.borrower_id not in PERSONAS:
        raise HTTPException(
            status_code=404,
            detail=f"Borrower '{request.borrower_id}' not found. "
                   f"Available: {list(PERSONAS.keys())}",
        )

    orchestrator = get_orchestrator()

    try:
        result = orchestrator.run(request.borrower_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    return result
