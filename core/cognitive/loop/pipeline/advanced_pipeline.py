"""
Advanced Reasoning Pipeline v14 - Integrates Cumulative Reasoning, 
Selection-Inference, and Causal Reasoning frameworks.

This pipeline provides state-of-the-art reasoning capabilities backed by
published research from 2024-2026.
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.cognitive.loop.frameworks.causal_reasoning import CausalReasoningModule
from core.cognitive.loop.frameworks.cumulative_reasoning import CumulativeReasoningFramework
from core.cognitive.loop.frameworks.selection_inference import SelectionInferenceFramework


@dataclass
class AdvancedPipelineConfig:
    """Configuration for advanced reasoning pipeline."""
    # Framework selection
    use_cumulative_reasoning: bool = True
    use_selection_inference: bool = True
    use_causal_reasoning: bool = False  # Requires additional setup
    
    # Cumulative Reasoning params
    cr_max_iterations: int = 10
    
    # Selection-Inference params
    si_num_steps: int = 5
    
    # Causal Reasoning params
    cr_sensitivity_threshold: float = 0.5
    
    # General params
    enable_tracing: bool = True
    enable_pruning: bool = False


class AdvancedReasoningPipeline:
    """
    Advanced reasoning pipeline integrating multiple frameworks.
    
    Combines:
    - Cumulative Reasoning (Zhang et al. 2023)
    - Selection-Inference (Creswell et al. 2022)
    - Causal Reasoning (Multiple papers 2024-2025)
    """
    
    def __init__(self, llm_executor, config: Optional[AdvancedPipelineConfig] = None):
        """
        Initialize advanced reasoning pipeline.
        
        Args:
            llm_executor: LLM executor for generating responses
            config: Pipeline configuration
        """
        self.config = config or AdvancedPipelineConfig()
        self.llm = llm_executor
        
        # Initialize frameworks based on config
        self.cumulative_reasoning = None
        if self.config.use_cumulative_reasoning:
            self.cumulative_reasoning = CumulativeReasoningFramework(
                llm_executor,
                max_iterations=self.config.cr_max_iterations
            )
        
        self.selection_inference = None
        if self.config.use_selection_inference:
            self.selection_inference = SelectionInferenceFramework(
                llm_executor,
                num_steps=self.config.si_num_steps
            )
        
        self.causal_reasoning = None
        if self.config.use_causal_reasoning:
            # Causal reasoning requires a reasoning function
            # For now, we'll use a simple wrapper
            def reasoning_fn(context, question, reasoning_steps=None):
                # Simple reasoning function
                if reasoning_steps:
                    return reasoning_steps[-1] if reasoning_steps else "Unable to determine"
                return "Unable to determine"
            
            self.causal_reasoning = CausalReasoningModule(
                llm_executor,
                reasoning_fn
            )
    
    def reason(
        self,
        problem: str,
        context: Optional[List[str]] = None,
        framework: str = "auto"
    ) -> Dict[str, Any]:
        """
        Perform advanced reasoning on a problem.
        
        Args:
            problem: Problem to solve
            context: Optional context (list of facts)
            framework: Which framework to use ("cumulative", "selection_inference", 
                      "causal", or "auto")
            
        Returns:
            Dictionary with reasoning results
        """
        start_time = time.time()
        
        # Auto-select framework based on problem type
        if framework == "auto":
            framework = self._select_framework(problem, context)
        
        # Route to appropriate framework
        if framework == "cumulative" and self.cumulative_reasoning:
            result = self._run_cumulative_reasoning(problem, context)
        elif framework == "selection_inference" and self.selection_inference:
            result = self._run_selection_inference(problem, context)
        elif framework == "causal" and self.causal_reasoning:
            result = self._run_causal_reasoning(problem, context)
        else:
            # Fallback to cumulative reasoning
            if self.cumulative_reasoning:
                result = self._run_cumulative_reasoning(problem, context)
            elif self.selection_inference:
                result = self._run_selection_inference(problem, context)
            else:
                result = {
                    "error": "No reasoning framework available",
                    "answer": "Unable to perform reasoning"
                }
        
        # Add timing information
        result["total_time_ms"] = int((time.time() - start_time) * 1000)
        result["framework_used"] = framework
        
        return result
    
    def _select_framework(self, problem: str, context: Optional[List[str]]) -> str:
        """
        Automatically select the best framework based on problem characteristics.
        
        Args:
            problem: Problem to solve
            context: Optional context
            
        Returns:
            Framework name ("cumulative", "selection_inference", or "causal")
        """
        problem_lower = problem.lower()
        
        # Check for logical reasoning (use Selection-Inference)
        logic_keywords = [
            "all", "some", "none", "if", "then", "therefore",
            "implies", "conclusion", "premise", "logical",
            "deduce", "infer", "proof"
        ]
        
        if any(kw in problem_lower for kw in logic_keywords):
            if self.selection_inference:
                return "selection_inference"
        
        # Check for complex reasoning (use Cumulative Reasoning)
        complex_keywords = [
            "complex", "multi-step", "analyze", "evaluate",
            "compare", "design", "plan", "strategy"
        ]
        
        if any(kw in problem_lower for kw in complex_keywords):
            if self.cumulative_reasoning:
                return "cumulative"
        
        # Check for causal reasoning
        causal_keywords = [
            "cause", "effect", "why", "because", "consequence",
            "impact", "result", "outcome"
        ]
        
        if any(kw in problem_lower for kw in causal_keywords):
            if self.causal_reasoning:
                return "causal"
        
        # Default to cumulative reasoning
        if self.cumulative_reasoning:
            return "cumulative"
        elif self.selection_inference:
            return "selection_inference"
        else:
            return "causal" if self.causal_reasoning else "cumulative"
    
    def _run_cumulative_reasoning(
        self, 
        problem: str, 
        context: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Run Cumulative Reasoning framework."""
        context_str = "\n".join(context) if context else ""
        
        result = self.cumulative_reasoning.reason(problem, context_str)
        
        return {
            "framework": "cumulative_reasoning",
            "answer": result["answer"],
            "dag": result["dag"],
            "num_iterations": result["num_iterations"],
            "num_propositions": result["num_propositions"],
            "num_verified": result["num_verified"]
        }
    
    def _run_selection_inference(
        self,
        problem: str,
        context: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Run Selection-Inference framework."""
        context_list = context or []
        
        if self.config.enable_tracing:
            result = self.selection_inference.reason_with_trace(context_list, problem)
            return {
                "framework": "selection_inference",
                "trace": result
            }
        else:
            result = self.selection_inference.reason(context_list, problem)
            return {
                "framework": "selection_inference",
                "answer": result["answer"],
                "reasoning_steps": result["reasoning_steps"],
                "num_steps": result["num_steps"]
            }
    
    def _run_causal_reasoning(
        self,
        problem: str,
        context: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Run Causal Reasoning framework."""
        # For causal reasoning, we need reasoning steps
        # First, get some reasoning steps using another framework
        if self.cumulative_reasoning:
            initial_result = self.cumulative_reasoning.reason(problem, "")
            reasoning_steps = [
                prop["content"] 
                for prop in initial_result["dag"]["nodes"].values()
                if prop["status"] == "verified"
            ]
        elif self.selection_inference:
            initial_result = self.selection_inference.reason(context or [], problem)
            reasoning_steps = [
                step["inference"] 
                for step in initial_result["reasoning_steps"]
            ]
        else:
            reasoning_steps = []
        
        # Analyze and prune
        result = self.causal_reasoning.analyze_and_prune(
            reasoning_steps,
            context or [],
            problem,
            sensitivity_threshold=self.config.cr_sensitivity_threshold
        )
        
        return {
            "framework": "causal_reasoning",
            "original_steps": result["original_steps"],
            "pruned_steps": result["pruned_steps"],
            "num_original": result["num_original"],
            "num_pruned": result["num_pruned"],
            "pruning_ratio": result["pruning_ratio"],
            "sensitivity_metrics": result["sensitivity_metrics"]
        }
    
    def compare_frameworks(
        self,
        problem: str,
        context: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Compare all available frameworks on the same problem.
        
        Args:
            problem: Problem to solve
            context: Optional context
            
        Returns:
            Dictionary comparing results from all frameworks
        """
        results = {}
        
        # Run Cumulative Reasoning
        if self.cumulative_reasoning:
            results["cumulative_reasoning"] = self._run_cumulative_reasoning(
                problem, context
            )
        
        # Run Selection-Inference
        if self.selection_inference:
            results["selection_inference"] = self._run_selection_inference(
                problem, context
            )
        
        # Run Causal Reasoning
        if self.causal_reasoning:
            results["causal_reasoning"] = self._run_causal_reasoning(
                problem, context
            )
        
        return results


class MockLLMExecutor:
    """Mock LLM executor for testing."""
    
    def __init__(self, responses: List[str] = None):
        self.responses = responses or []
        self.call_count = 0
    
    def generate(self, prompt: str) -> str:
        """Generate a response."""
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
            self.call_count += 1
            return response
        return "Default response"


def create_test_pipeline(use_all_frameworks: bool = True) -> AdvancedReasoningPipeline:
    """
    Create a test pipeline with mock LLM.
    
    Args:
        use_all_frameworks: Whether to enable all frameworks
        
    Returns:
        Configured pipeline
    """
    mock_llm = MockLLMExecutor()
    
    config = AdvancedPipelineConfig(
        use_cumulative_reasoning=True,
        use_selection_inference=True,
        use_causal_reasoning=use_all_frameworks
    )
    
    return AdvancedReasoningPipeline(mock_llm, config)
