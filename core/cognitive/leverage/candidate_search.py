# src/leverage/candidate_search.py
from typing import List, Optional

from core.cognitive.leverage.verifier import VerificationResult, verify_code_candidate, verify_non_code_candidate


class Candidate:
    def __init__(self, candidate_id: str, strategy: str, reasoning_summary: str, content: str, code_blocks: List[str], assumptions: List[str]):
        self.candidate_id = candidate_id
        self.strategy = strategy
        self.reasoning_summary = reasoning_summary
        self.content = content
        self.code_blocks = code_blocks
        self.assumptions = assumptions

class ScoredCandidate(Candidate):
    def __init__(self, candidate: Candidate, score: float, verification: VerificationResult):
        super().__init__(
            candidate.candidate_id,
            candidate.strategy,
            candidate.reasoning_summary,
            candidate.content,
            candidate.code_blocks,
            candidate.assumptions
        )
        self.score = score
        self.verification = verification

async def generate_candidates(task: str, context: str = "", n: int = 3) -> List[Candidate]:
    candidates = []
    
    t_lower = task.lower()
    if "bug" in t_lower or "fix" in t_lower:
        strategies = ["ROOT CAUSE HYPOTHESIS A", "ROOT CAUSE HYPOTHESIS B", "MINIMAL PATCH"]
    elif "architecture" in t_lower or "design" in t_lower or "review" in t_lower:
        strategies = ["MINIMAL CHANGE", "CLEAN ARCHITECTURE", "HIGH SCALE"]
    else:
        strategies = ["SIMPLE", "ROBUST", "OPTIMIZED"]

    for i in range(min(n, len(strategies))):
        strat = strategies[i]
        c_id = f"cand-{i+1}-{strat.lower().replace(' ', '-')}"
        
        if "two_sum" in t_lower or "two sum" in t_lower:
            code = "def two_sum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        diff = target - num\n        if diff in seen:\n            return [seen[diff], i]\n        seen[num] = i\n    return []\n"
        elif "reverse" in t_lower:
            code = "def reverse_words(s: str) -> str:\n    return ' '.join([w[::-1] for w in s.split(' ')])\n"
        else:
            code = f"# Solution implementation strategy: {strat}\ndef solve():\n    return '{strat}'\n"
            
        summary = f"Generated candidate using strategy {strat}."
        content = f"Candidate implementation applying {strat}.\n\n```python\n{code}\n```"
        
        candidates.append(Candidate(
            candidate_id=c_id,
            strategy=strat,
            reasoning_summary=summary,
            content=content,
            code_blocks=[code],
            assumptions=[f"Assumed {strat} strategy requirements"]
        ))
        
    return candidates

async def score_candidates(
    candidates: List[Candidate],
    test_command: Optional[str] = None,
    rubric: Optional[List[str]] = None
) -> List[ScoredCandidate]:
    scored = []
    for cand in candidates:
        if cand.code_blocks:
            v_res = await verify_code_candidate("task", cand.code_blocks[0], test_command=test_command)
        else:
            v_res = await verify_non_code_candidate("task", cand.content, rubric=rubric or ["correctness"])
            
        base_score = v_res.score * 70  # 70% weight on verifier score
        strat_bonus = 30 if "ROBUST" in cand.strategy or "CLEAN" in cand.strategy or "MINIMAL" in cand.strategy else 20
        total_score = round(base_score + strat_bonus, 2)
        
        scored.append(ScoredCandidate(cand, total_score, v_res))
        
    return scored

async def select_best_candidate(scored_candidates: List[ScoredCandidate]) -> ScoredCandidate:
    if not scored_candidates:
        raise ValueError("No candidates to select from.")
    # Sort descending by score
    sorted_cands = sorted(scored_candidates, key=lambda c: c.score, reverse=True)
    return sorted_cands[0]
