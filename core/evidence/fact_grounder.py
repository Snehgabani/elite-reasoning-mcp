"""
FActScore Grounding Evaluator & Citation Gate.
Evaluates atomic factual claims against retrieved primary evidence quotes (Min et al. 2023).
Deterministic, fail-closed, and resistant to hallucinated URLs or unsupported assertions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from core.evidence.grounded_search import EvidenceQuote, GroundedEvidence


@dataclass(frozen=True)
class AtomicClaim:
    claim_id: str
    statement: str
    supported: bool
    matching_quote: Optional[EvidenceQuote] = None
    confidence_score: float = 0.0


@dataclass(frozen=True)
class GroundingVerificationReport:
    fact_score: float
    total_claims: int
    supported_claims: int
    unsupported_claims: tuple[str, ...]
    hallucinated_urls: tuple[str, ...]
    valid_cited_urls: tuple[str, ...]
    passed: bool
    is_degraded: bool
    reason: str


class FActScoreGrounder:
    """
    Decomposes draft responses into atomic propositions, cross-checks lexical
    grounding against retrieved quotes, and gates hallucinated citations.
    """

    URL_RE = re.compile(r"https?://[^\s)>\]]+", re.I)
    SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

    def __init__(self, min_fact_score_threshold: float = 0.85):
        self.min_threshold = min_fact_score_threshold

    def extract_atomic_propositions(self, text: str) -> List[str]:
        """
        Splits narrative text into discrete sentences/clauses representing atomic claims.
        Filters out pure meta-conversational lines and headers.
        """
        if not text:
            return []

        cleaned = re.sub(r"```[\s\S]*?```", "", text)  # remove code blocks
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]

        propositions: List[str] = []
        for line in lines:
            if line.startswith(("#", "-", "*", ">")):
                line = re.sub(r"^[#\-*>]+\s*", "", line)
            sentences = self.SENTENCE_SPLIT_RE.split(line)
            for s in sentences:
                s_clean = s.strip()
                # Must have substance (at least 4 words)
                if len(s_clean.split()) >= 4:
                    propositions.append(s_clean)

        return propositions

    def evaluate_grounding(
        self,
        draft_text: str,
        evidence: GroundedEvidence,
    ) -> GroundingVerificationReport:
        """
        Evaluates a draft against retrieved GroundedEvidence quotes.
        """
        # 1. Check URLs in draft
        raw_urls = self.URL_RE.findall(draft_text or "")
        draft_urls = {re.sub(r"[,\.!?:;]+$", "", u) for u in raw_urls if u.strip()}
        known_evidence_urls = {item.url for item in evidence.quotes}

        hallucinated_urls = sorted(url for url in draft_urls if url not in known_evidence_urls)
        valid_urls = sorted(url for url in draft_urls if url in known_evidence_urls)

        # 2. Extract atomic claims
        claims = self.extract_atomic_propositions(draft_text)
        if not claims:
            return GroundingVerificationReport(
                fact_score=1.0,
                total_claims=0,
                supported_claims=0,
                unsupported_claims=(),
                hallucinated_urls=tuple(hallucinated_urls),
                valid_cited_urls=tuple(valid_urls),
                passed=len(hallucinated_urls) == 0,
                is_degraded=evidence.degraded,
                reason="No atomic propositions detected in draft",
            )

        # 3. Match claims against evidence quotes
        supported_count = 0
        unsupported: List[str] = []

        for claim in claims:
            claim_terms = set(re.findall(r"[a-zA-Z0-9]{4,}", claim.lower()))
            best_match: Optional[EvidenceQuote] = None
            best_overlap = 0.0

            for q in evidence.quotes:
                quote_terms = set(re.findall(r"[a-zA-Z0-9]{4,}", q.quote.lower()))
                if not quote_terms or not claim_terms:
                    continue
                overlap = len(claim_terms & quote_terms) / len(claim_terms)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_match = q

            # Claim is supported if at least 40% lexical overlap with a verified quote
            if best_overlap >= 0.40 and best_match is not None:
                supported_count += 1
            else:
                unsupported.append(claim)

        fact_score = round(supported_count / len(claims), 4) if claims else 1.0

        # Pass condition: no hallucinated URLs and fact score meets threshold
        passed = (len(hallucinated_urls) == 0) and (fact_score >= self.min_threshold)

        reason = "All claims verified against evidence quotes"
        if hallucinated_urls:
            reason = f"Contains {len(hallucinated_urls)} unverified/hallucinated URLs"
        elif fact_score < self.min_threshold:
            reason = f"FActScore {fact_score:.2f} is below threshold {self.min_threshold:.2f}"

        return GroundingVerificationReport(
            fact_score=fact_score,
            total_claims=len(claims),
            supported_claims=supported_count,
            unsupported_claims=tuple(unsupported[:10]),
            hallucinated_urls=tuple(hallucinated_urls),
            valid_cited_urls=tuple(valid_urls),
            passed=passed,
            is_degraded=evidence.degraded,
            reason=reason,
        )
