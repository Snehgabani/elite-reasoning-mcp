"""
Causal Reasoning Module - Multiple papers 2024-2025

Implements counterfactual sensitivity training and causal pruning
to ensure models are causally sensitive to reasoning content.

Research: 
- "Causal Consistency Regularization" (2025) - +32.8% on GSM8K
- "Causal Sufficiency and Necessity" (2025) - +8.4% on MATH-500
- "Making Reasoning Matter" (2024)
"""

import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, List


@dataclass
class CausalTestResult:
    """Result of a causal sensitivity test."""
    step_index: int
    original_step: str
    perturbed_step: str
    original_answer: str
    perturbed_answer: str
    answer_changed: bool
    causally_sensitive: bool
    perturbation_type: str
    reasoning: str = ""


class CounterfactualGenerator:
    """Generates counterfactual perturbations of reasoning steps."""
    
    def __init__(self, llm_executor):
        self.llm = llm_executor
    
    def perturb(self, reasoning_step: str, perturbation_type: str = "random") -> str:
        """
        Generate a perturbed version of a reasoning step.
        
        Args:
            reasoning_step: Original reasoning step
            perturbation_type: Type of perturbation
            
        Returns:
            Perturbed reasoning step
        """
        if perturbation_type == "random":
            return self._random_perturbation(reasoning_step)
        elif perturbation_type == "negation":
            return self._negate_step(reasoning_step)
        elif perturbation_type == "substitution":
            return self._substitute_entities(reasoning_step)
        elif perturbation_type == "llm":
            return self._llm_perturbation(reasoning_step)
        else:
            return reasoning_step
    
    def _random_perturbation(self, step: str) -> str:
        """Randomly perturb a reasoning step."""
        words = step.split()
        if len(words) < 3:
            return step
        
        # Randomly replace 1-2 words
        num_replacements = min(2, len(words) // 3)
        indices = random.sample(range(len(words)), num_replacements)
        
        replacements = ["something", "another thing", "a different value", 
                       "an alternative", "a different approach"]
        
        for idx in indices:
            words[idx] = random.choice(replacements)
        
        return " ".join(words)
    
    def _negate_step(self, step: str) -> str:
        """Negate a reasoning step."""
        # Simple negation
        if step.startswith("not "):
            return step[4:]
        else:
            return "not " + step
    
    def _substitute_entities(self, step: str) -> str:
        """Substitute entities in a reasoning step."""
        # Entity substitution pairs
        substitutions = [
            ("Alice", "Bob"),
            ("first", "second"),
            ("all", "some"),
        ]
        
        result = step
        # Use simultaneous replacement to avoid double-substitution
        # Only substitute if the original entity is present
        for old, new in substitutions:
            if old in result:
                result = result.replace(old, new)
                break  # Only do one substitution per call
        
        return result
    
    def _llm_perturbation(self, step: str) -> str:
        """Use LLM to generate a perturbed step."""
        prompt = f"""Generate a plausible but different version of this reasoning step:

Original: {step}

Generate a different but plausible version (change key details, values, or relationships):
"""
        
        response = self.llm.generate(prompt)
        return response.strip()


class CausalSensitivityChecker:
    """Checks if model is causally sensitive to reasoning content."""
    
    def __init__(self, llm_executor, reasoning_fn: Callable):
        """
        Initialize causal sensitivity checker.
        
        Args:
            llm_executor: LLM executor
            reasoning_fn: Function that performs reasoning and returns answer
        """
        self.llm = llm_executor
        self.reasoning_fn = reasoning_fn
        self.perturbation_generator = CounterfactualGenerator(llm_executor)
    
    def test_causal_sensitivity(
        self, 
        reasoning_steps: List[str], 
        context: Any,
        question: str,
        perturbation_types: List[str] = None
    ) -> List[CausalTestResult]:
        """
        Test if model is causally sensitive to reasoning steps.
        
        Args:
            reasoning_steps: List of reasoning steps
            context: Context for reasoning
            question: Question to answer
            perturbation_types: Types of perturbations to test
            
        Returns:
            List of causal test results
        """
        if perturbation_types is None:
            perturbation_types = ["random", "negation", "substitution"]
        
        # Get original answer
        original_answer = self.reasoning_fn(context, question)
        
        results = []
        
        # Test each reasoning step
        for step_idx, step in enumerate(reasoning_steps):
            for perturbation_type in perturbation_types:
                # Perturb this step
                perturbed_step = self.perturbation_generator.perturb(
                    step, perturbation_type
                )
                
                # Create perturbed reasoning steps
                perturbed_steps = reasoning_steps.copy()
                perturbed_steps[step_idx] = perturbed_step
                
                # Get answer with perturbed reasoning
                # Note: This assumes reasoning_fn can accept modified reasoning steps
                # In practice, you'd need to modify the reasoning function to accept
                # perturbed reasoning steps
                perturbed_answer = self.reasoning_fn(
                    context, 
                    question,
                    reasoning_steps=perturbed_steps  # This parameter needs to be supported
                )
                
                # Check if answer changed
                answer_changed = original_answer != perturbed_answer
                
                # If answer didn't change, model is NOT causally sensitive to this step
                causally_sensitive = answer_changed
                
                result = CausalTestResult(
                    step_index=step_idx,
                    original_step=step,
                    perturbed_step=perturbed_step,
                    original_answer=original_answer,
                    perturbed_answer=perturbed_answer,
                    answer_changed=answer_changed,
                    causally_sensitive=causally_sensitive,
                    perturbation_type=perturbation_type,
                    reasoning=f"Answer {'changed' if answer_changed else 'unchanged'} when step perturbed"
                )
                results.append(result)
        
        return results
    
    def compute_causal_sensitivity_score(
        self, 
        test_results: List[CausalTestResult]
    ) -> Dict[str, Any]:
        """
        Compute causal sensitivity score from test results.
        
        Args:
            test_results: List of causal test results
            
        Returns:
            Dictionary with sensitivity metrics
        """
        total_tests = len(test_results)
        sensitive_tests = sum(1 for r in test_results if r.causally_sensitive)
        
        sensitivity_score = sensitive_tests / total_tests if total_tests > 0 else 0.0
        
        # Break down by perturbation type
        by_type = {}
        for result in test_results:
            ptype = result.perturbation_type
            if ptype not in by_type:
                by_type[ptype] = {"total": 0, "sensitive": 0}
            by_type[ptype]["total"] += 1
            if result.causally_sensitive:
                by_type[ptype]["sensitive"] += 1
        
        for ptype in by_type:
            total = by_type[ptype]["total"]
            sensitive = by_type[ptype]["sensitive"]
            by_type[ptype]["score"] = sensitive / total if total > 0 else 0.0
        
        # Break down by step
        by_step = {}
        for result in test_results:
            step_idx = result.step_index
            if step_idx not in by_step:
                by_step[step_idx] = {"total": 0, "sensitive": 0}
            by_step[step_idx]["total"] += 1
            if result.causally_sensitive:
                by_step[step_idx]["sensitive"] += 1
        
        for step_idx in by_step:
            total = by_step[step_idx]["total"]
            sensitive = by_step[step_idx]["sensitive"]
            by_step[step_idx]["score"] = sensitive / total if total > 0 else 0.0
        
        return {
            "overall_sensitivity": sensitivity_score,
            "total_tests": total_tests,
            "sensitive_tests": sensitive_tests,
            "by_perturbation_type": by_type,
            "by_step": by_step,
            "interpretation": self._interpret_score(sensitivity_score)
        }
    
    def _interpret_score(self, score: float) -> str:
        """Interpret causal sensitivity score."""
        if score >= 0.8:
            return "High causal sensitivity - model is highly sensitive to reasoning content"
        elif score >= 0.6:
            return "Good causal sensitivity - model is mostly sensitive to reasoning content"
        elif score >= 0.4:
            return "Moderate causal sensitivity - model is sometimes sensitive to reasoning content"
        elif score >= 0.2:
            return "Low causal sensitivity - model is rarely sensitive to reasoning content"
        else:
            return "Very low causal sensitivity - model is not causally sensitive to reasoning content"


class CausalPruner:
    """Prunes unnecessary reasoning steps based on causal analysis."""
    
    def __init__(self, causal_checker: CausalSensitivityChecker):
        """
        Initialize causal pruner.
        
        Args:
            causal_checker: Causal sensitivity checker
        """
        self.causal_checker = causal_checker
    
    def prune_reasoning_steps(
        self,
        reasoning_steps: List[str],
        context: Any,
        question: str,
        sensitivity_threshold: float = 0.5
    ) -> List[str]:
        """
        Prune reasoning steps that are not causally sensitive.
        
        Args:
            reasoning_steps: List of reasoning steps
            context: Context for reasoning
            question: Question to answer
            sensitivity_threshold: Minimum sensitivity score to keep step
            
        Returns:
            Pruned list of reasoning steps
        """
        # Test causal sensitivity
        test_results = self.causal_checker.test_causal_sensitivity(
            reasoning_steps, context, question
        )
        
        # Compute sensitivity by step
        sensitivity_by_step = {}
        for result in test_results:
            step_idx = result.step_index
            if step_idx not in sensitivity_by_step:
                sensitivity_by_step[step_idx] = []
            sensitivity_by_step[step_idx].append(result.causally_sensitive)
        
        # Compute average sensitivity per step
        avg_sensitivity = {}
        for step_idx, sensitivities in sensitivity_by_step.items():
            avg_sensitivity[step_idx] = sum(sensitivities) / len(sensitivities)
        
        # Keep only steps above threshold
        pruned_steps = []
        for step_idx, step in enumerate(reasoning_steps):
            sensitivity = avg_sensitivity.get(step_idx, 0.0)
            if sensitivity >= sensitivity_threshold:
                pruned_steps.append(step)
        
        return pruned_steps


class CausalReasoningModule:
    """
    Main Causal Reasoning module.
    
    Combines counterfactual generation, sensitivity checking, and pruning.
    """
    
    def __init__(self, llm_executor, reasoning_fn: Callable):
        """
        Initialize Causal Reasoning module.
        
        Args:
            llm_executor: LLM executor
            reasoning_fn: Function that performs reasoning
        """
        self.causal_checker = CausalSensitivityChecker(llm_executor, reasoning_fn)
        self.pruner = CausalPruner(self.causal_checker)
    
    def analyze_and_prune(
        self,
        reasoning_steps: List[str],
        context: Any,
        question: str,
        sensitivity_threshold: float = 0.5
    ) -> Dict[str, Any]:
        """
        Analyze causal sensitivity and prune unnecessary steps.
        
        Args:
            reasoning_steps: List of reasoning steps
            context: Context for reasoning
            question: Question to answer
            sensitivity_threshold: Minimum sensitivity to keep step
            
        Returns:
            Dictionary with analysis results and pruned steps
        """
        # Test causal sensitivity
        test_results = self.causal_checker.test_causal_sensitivity(
            reasoning_steps, context, question
        )
        
        # Compute sensitivity score
        sensitivity_metrics = self.causal_checker.compute_causal_sensitivity_score(
            test_results
        )
        
        # Prune reasoning steps
        pruned_steps = self.pruner.prune_reasoning_steps(
            reasoning_steps, context, question, sensitivity_threshold
        )
        
        return {
            "original_steps": reasoning_steps,
            "pruned_steps": pruned_steps,
            "num_original": len(reasoning_steps),
            "num_pruned": len(pruned_steps),
            "pruning_ratio": len(pruned_steps) / len(reasoning_steps) if reasoning_steps else 0.0,
            "sensitivity_metrics": sensitivity_metrics,
            "test_results": [
                {
                    "step_index": r.step_index,
                    "original_step": r.original_step,
                    "perturbed_step": r.perturbed_step,
                    "answer_changed": r.answer_changed,
                    "causally_sensitive": r.causally_sensitive,
                    "perturbation_type": r.perturbation_type
                }
                for r in test_results
            ]
        }
