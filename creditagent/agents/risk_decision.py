"""
risk_decision.py
RiskDecisionAgent — compute composite score and determine risk tier + decision.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.risk_calculator import compute_composite


class RiskDecisionAgent:
    """Combine financial and alternative scores into a credit decision."""

    def run(
        self,
        financial_score: int,
        alternative_score: int,
        is_underbanked: bool,
        behavioral_score: int = 500,
    ) -> dict:
        """
        Parameters
        ----------
        financial_score    : int 0-1000
        alternative_score  : int 0-1000
        is_underbanked     : bool — True if no bank account
        behavioral_score   : int 0-1000 — placeholder behavioral metric

        Returns
        -------
        dict with composite_score, risk_tier, decision, credit_terms
        """
        result = compute_composite(
            financial_score=financial_score,
            alternative_score=alternative_score,
            is_underbanked=is_underbanked,
            behavioral_score=behavioral_score,
        )

        # Confidence: higher score → higher confidence
        confidence = result.composite_score / 1000.0

        return {
            "composite_score": result.composite_score,
            "risk_tier": result.risk_tier,
            "decision": result.decision,
            "credit_limit": result.credit_limit,
            "interest_rate_range": result.interest_rate_range,
            "financial_weight": result.financial_weight,
            "alternative_weight": result.alternative_weight,
            "confidence": round(confidence, 3),
            "score_breakdown": {
                "financial_score": financial_score,
                "alternative_score": alternative_score,
                "behavioral_score": behavioral_score,
                "is_underbanked": is_underbanked,
            },
        }
