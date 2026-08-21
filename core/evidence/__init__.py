"""Quote-grounded evidence retrieval, multi-hop query planning, and FActScore gating."""

from core.evidence.grounded_search import (
    EvidenceQuote,
    GroundedEvidence,
    extract_quotes,
    grounded_evidence,
    grounding_check,
)
from core.evidence.query_planner import PlannedQuery, QueryPlan, QueryPlanner
from core.evidence.fact_grounder import AtomicClaim, FActScoreGrounder, GroundingVerificationReport

__all__ = [
    "EvidenceQuote",
    "GroundedEvidence",
    "extract_quotes",
    "grounded_evidence",
    "grounding_check",
    "PlannedQuery",
    "QueryPlan",
    "QueryPlanner",
    "AtomicClaim",
    "FActScoreGrounder",
    "GroundingVerificationReport",
]
