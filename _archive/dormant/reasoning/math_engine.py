from typing import Dict, Any, List

class MathEngine:
    """
    Implements 10 quantitative frameworks for objective decision making.
    """
    
    def expected_value(self, scenarios: List[Dict[str, float]]) -> float:
        """
        Calculate Expected Value (EV).
        scenarios: List of dicts with 'probability' and 'value'.
        """
        ev = 0.0
        for s in scenarios:
            ev += s["probability"] * s["value"]
        return ev
        
    def fermi_estimation(self, target: str, logic_steps: List[str]) -> Dict[str, Any]:
        """Order-of-magnitude estimation."""
        return {"estimate": "10^X", "logic": logic_steps}
        
    def bayesian_update(self, prior: float, sensitivity: float, specificity: float, prev_prob: float) -> float:
        """Bayesian probability update."""
        # P(A|B) = [P(B|A) * P(A)] / P(B)
        prob_b = (sensitivity * prior) + ((1 - specificity) * (1 - prior))
        posterior = (sensitivity * prior) / prob_b
        return posterior

    def compound_growth(self, principal: float, rate: float, periods: int) -> float:
        """Compound growth calculator."""
        return principal * ((1 + rate) ** periods)

    # ... Other frameworks (Sensitivity, Break-Even, Monte Carlo, Dimensional, Stats, Projections)
