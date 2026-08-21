"""
Real Benchmark Suite — Validation with actual LLM outputs

This module provides real-world testing of the MCP's effectiveness
by comparing outputs with and without MCP assistance.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


@dataclass
class BenchmarkPrompt:
    """A single benchmark prompt with ground truth."""
    id: str
    prompt: str
    category: str  # debug, build, decide, research, etc.
    difficulty: str  # easy, medium, hard
    ground_truth: str  # Expected good answer
    evaluation_criteria: List[str]  # What makes a good answer
    tags: List[str] = None
    
    def to_dict(self):
        return asdict(self)


@dataclass
class BenchmarkResult:
    """Result from running a benchmark."""
    prompt_id: str
    mode: str  # "with_mcp" or "without_mcp"
    output: str
    duration_ms: int
    mcp_structure: Optional[Dict] = None  # Structure from MCP (if used)
    
    # Evaluation scores (0-10)
    quality_score: float = 0.0
    helpfulness_score: float = 0.0
    accuracy_score: float = 0.0
    completeness_score: float = 0.0
    
    # Detailed evaluation
    criteria_scores: Dict[str, float] = None
    llm_judge_reasoning: str = ""
    
    def to_dict(self):
        return asdict(self)


class RealBenchmarkSuite:
    """
    Real benchmark suite that tests MCP effectiveness with actual LLM calls.
    
    Usage:
        suite = RealBenchmarkSuite(api_key="...", provider="anthropic")
        results = suite.run_all_benchmarks()
        report = suite.generate_report(results)
    """
    
    def __init__(self, api_key: str = None, provider: str = "anthropic"):
        self.api_key = api_key
        self.provider = provider
        self.client = self._init_client()
        self.benchmarks = self._load_benchmarks()
    
    def _init_client(self):
        """Initialize LLM client."""
        if self.provider == "anthropic" and HAS_ANTHROPIC and self.api_key:
            return anthropic.Anthropic(api_key=self.api_key)
        elif self.provider == "openai" and HAS_OPENAI and self.api_key:
            return openai.OpenAI(api_key=self.api_key)
        else:
            return None
    
    def _load_benchmarks(self) -> List[BenchmarkPrompt]:
        """Load benchmark prompts from file or create defaults."""
        benchmark_file = Path(__file__).parent.parent.parent / "benchmarks" / "real_prompts.json"
        
        if benchmark_file.exists():
            with open(benchmark_file) as f:
                data = json.load(f)
                return [BenchmarkPrompt(**b) for b in data]
        else:
            # Create default benchmarks
            return self._create_default_benchmarks()
    
    def _create_default_benchmarks(self) -> List[BenchmarkPrompt]:
        """Create a set of real-world benchmark prompts."""
        return [
            BenchmarkPrompt(
                id="debug_01",
                prompt="My React app keeps re-rendering the entire component tree on every state update. Performance is terrible. How do I fix this?",
                category="debug",
                difficulty="medium",
                ground_truth="Use React.memo for pure components, useMemo for expensive calculations, useCallback for functions passed as props, and check for unnecessary state updates in parent components.",
                evaluation_criteria=[
                    "Identifies root cause (unnecessary re-renders)",
                    "Provides specific solutions (memo, useMemo, useCallback)",
                    "Explains when to use each technique",
                    "Mentions profiling tools (React DevTools)"
                ],
                tags=["react", "performance", "optimization"]
            ),
            BenchmarkPrompt(
                id="build_01",
                prompt="Design a URL shortener service that can handle 100M URLs and 10K requests/second.",
                category="build",
                difficulty="hard",
                ground_truth="Use base62 encoding for short URLs, distributed hash table or database with consistent hashing, CDN for caching, rate limiting, and horizontal scaling.",
                evaluation_criteria=[
                    "Addresses scale requirements",
                    "Proposes efficient encoding scheme",
                    "Considers database design",
                    "Mentions caching and CDN",
                    "Discusses trade-offs"
                ],
                tags=["system-design", "scalability", "distributed-systems"]
            ),
            BenchmarkPrompt(
                id="decide_01",
                prompt="Should we use microservices or monolith for our new e-commerce platform with 50 developers?",
                category="decide",
                difficulty="medium",
                ground_truth="Consider team size, deployment complexity, service boundaries, data consistency needs. Monolith might be better to start, refactor to microservices later if needed.",
                evaluation_criteria=[
                    "Lists pros and cons of each approach",
                    "Considers team size and organization",
                    "Discusses deployment complexity",
                    "Mentions hybrid approaches",
                    "Provides clear recommendation with reasoning"
                ],
                tags=["architecture", "decision-making", "trade-offs"]
            ),
            BenchmarkPrompt(
                id="research_01",
                prompt="What are the latest advances in transformer model efficiency for edge deployment?",
                category="research",
                difficulty="hard",
                ground_truth="Cover quantization (INT8, INT4), knowledge distillation, pruning, neural architecture search for efficient models, and specific models like MobileBERT, TinyBERT, DistilBERT.",
                evaluation_criteria=[
                    "Covers multiple efficiency techniques",
                    "Mentions specific models/approaches",
                    "Provides quantitative comparisons",
                    "Cites recent work (2023-2024)",
                    "Discusses trade-offs (accuracy vs efficiency)"
                ],
                tags=["ml", "transformers", "edge-computing", "research"]
            ),
            BenchmarkPrompt(
                id="debug_02",
                prompt="PostgreSQL query that used to take 100ms now takes 10 seconds after we added 1M rows. EXPLAIN shows sequential scan instead of index scan.",
                category="debug",
                difficulty="medium",
                ground_truth="Check if index exists, run ANALYZE to update statistics, check if query planner is choosing seq scan due to table size, consider partial indexes or expression indexes.",
                evaluation_criteria=[
                    "Identifies likely cause (outdated statistics)",
                    "Suggests ANALYZE command",
                    "Explains query planner behavior",
                    "Provides diagnostic steps",
                    "Mentions index optimization"
                ],
                tags=["postgresql", "performance", "query-optimization"]
            ),
        ]
    
    def run_benchmark(self, benchmark: BenchmarkPrompt, mode: str = "with_mcp") -> BenchmarkResult:
        """Run a single benchmark."""
        if not self.client:
            raise ValueError("No LLM client available. Provide API key.")
        
        start = time.time()
        
        if mode == "with_mcp":
            # Get MCP structure
            from core.cognitive.loop.pipeline.graph_v7 import ReasoningPipelineV7
            from core.cognitive.loop.core.store import SingularityStore
            import tempfile
            
            store = SingularityStore(tempfile.mkdtemp())
            pipeline = ReasoningPipelineV7(store, mode="amplified")
            state = pipeline.run(benchmark.prompt)
            
            # Build prompt with MCP structure
            full_prompt = self._build_prompt_with_mcp(benchmark.prompt, state)
            mcp_structure = {
                "framework": state.reasoning_framework,
                "subproblems": state.subproblems,
                "critique_dimensions": state.critique_dimensions,
            }
        else:
            # Direct prompt without MCP
            full_prompt = benchmark.prompt
            mcp_structure = None
        
        # Call LLM
        output = self._call_llm(full_prompt)
        
        duration_ms = int((time.time() - start) * 1000)
        
        # Evaluate output
        evaluation = self._evaluate_output(benchmark, output)
        
        return BenchmarkResult(
            prompt_id=benchmark.id,
            mode=mode,
            output=output,
            duration_ms=duration_ms,
            mcp_structure=mcp_structure,
            **evaluation
        )
    
    def _build_prompt_with_mcp(self, original_prompt: str, state) -> str:
        """Build prompt that includes MCP structure."""
        parts = [
            "You are an expert assistant. Use the following structured reasoning framework to answer the question.",
            "",
            f"## Question\n{original_prompt}",
            "",
            f"## Reasoning Framework: {state.reasoning_framework}",
            "",
            state.reasoning_template if state.reasoning_template else "",
            "",
            "## Subproblems to Address"
        ]
        
        for sp in state.subproblems:
            parts.append(f"- {sp['name']}: {sp['description']}")
        
        parts.extend([
            "",
            "## Quality Checklist"
        ])
        
        for criterion in state.quality_checklist:
            parts.append(f"- {criterion}")
        
        parts.extend([
            "",
            "Now provide your complete answer following this structure."
        ])
        
        return "\n".join(parts)
    
    def _call_llm(self, prompt: str) -> str:
        """Call LLM API."""
        if self.provider == "anthropic":
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        elif self.provider == "openai":
            response = self.client.chat.completions.create(
                model="gpt-4",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def _evaluate_output(self, benchmark: BenchmarkPrompt, output: str) -> Dict:
        """Evaluate output quality using LLM-as-judge."""
        # Build evaluation prompt
        eval_prompt = f"""You are an expert evaluator. Rate the following answer on a scale of 0-10.

## Question
{benchmark.prompt}

## Ground Truth (for reference)
{benchmark.ground_truth}

## Evaluation Criteria
{chr(10).join(f"- {c}" for c in benchmark.evaluation_criteria)}

## Answer to Evaluate
{output}

## Instructions
Provide scores for:
1. Quality (0-10): Overall quality and clarity
2. Helpfulness (0-10): How helpful is this to the user
3. Accuracy (0-10): How accurate and correct
4. Completeness (0-10): How complete and thorough

Also evaluate each criterion (0-10).

Respond in JSON format:
{{
  "quality": 8,
  "helpfulness": 7,
  "accuracy": 9,
  "completeness": 8,
  "criteria_scores": {{
    "criterion_1": 8,
    "criterion_2": 7
  }},
  "reasoning": "Brief explanation of scores"
}}
"""
        
        try:
            eval_output = self._call_llm(eval_prompt)
            # Parse JSON from response
            import re
            json_match = re.search(r'\{.*\}', eval_output, re.DOTALL)
            if json_match:
                scores = json.loads(json_match.group())
                return {
                    "quality_score": scores.get("quality", 0),
                    "helpfulness_score": scores.get("helpfulness", 0),
                    "accuracy_score": scores.get("accuracy", 0),
                    "completeness_score": scores.get("completeness", 0),
                    "criteria_scores": scores.get("criteria_scores", {}),
                    "llm_judge_reasoning": scores.get("reasoning", "")
                }
        except Exception as e:
            print(f"Evaluation failed: {e}")
        
        return {
            "quality_score": 0,
            "helpfulness_score": 0,
            "accuracy_score": 0,
            "completeness_score": 0,
            "criteria_scores": {},
            "llm_judge_reasoning": "Evaluation failed"
        }
    
    def run_all_benchmarks(self) -> List[BenchmarkResult]:
        """Run all benchmarks in both modes."""
        results = []
        
        for benchmark in self.benchmarks:
            print(f"Running benchmark: {benchmark.id}")
            
            # Run without MCP
            print(f"  - Without MCP...")
            result_without = self.run_benchmark(benchmark, mode="without_mcp")
            results.append(result_without)
            
            # Run with MCP
            print(f"  - With MCP...")
            result_with = self.run_benchmark(benchmark, mode="with_mcp")
            results.append(result_with)
        
        return results
    
    def generate_report(self, results: List[BenchmarkResult]) -> Dict:
        """Generate comprehensive report."""
        # Separate results by mode
        with_mcp = [r for r in results if r.mode == "with_mcp"]
        without_mcp = [r for r in results if r.mode == "without_mcp"]
        
        # Calculate statistics
        def calc_stats(results_list):
            return {
                "count": len(results_list),
                "avg_quality": sum(r.quality_score for r in results_list) / len(results_list),
                "avg_helpfulness": sum(r.helpfulness_score for r in results_list) / len(results_list),
                "avg_accuracy": sum(r.accuracy_score for r in results_list) / len(results_list),
                "avg_completeness": sum(r.completeness_score for r in results_list) / len(results_list),
                "avg_duration_ms": sum(r.duration_ms for r in results_list) / len(results_list),
            }
        
        stats_with = calc_stats(with_mcp)
        stats_without = calc_stats(without_mcp)
        
        # Calculate improvements
        improvements = {
            "quality": stats_with["avg_quality"] - stats_without["avg_quality"],
            "helpfulness": stats_with["avg_helpfulness"] - stats_without["avg_helpfulness"],
            "accuracy": stats_with["avg_accuracy"] - stats_without["avg_accuracy"],
            "completeness": stats_with["avg_completeness"] - stats_without["avg_completeness"],
        }
        
        # Calculate percentage improvements
        pct_improvements = {
            k: (v / stats_without[k.replace("_improvement", "")] * 100) if stats_without[k.replace("_improvement", "")] > 0 else 0
            for k, v in improvements.items()
        }
        
        # Statistical significance (simplified t-test)
        from scipy import stats as scipy_stats
        
        t_tests = {}
        for metric in ["quality", "helpfulness", "accuracy", "completeness"]:
            with_values = [getattr(r, f"{metric}_score") for r in with_mcp]
            without_values = [getattr(r, f"{metric}_score") for r in without_mcp]
            
            if len(with_values) > 1 and len(without_values) > 1:
                t_stat, p_value = scipy_stats.ttest_ind(with_values, without_values)
                t_tests[metric] = {
                    "t_statistic": t_stat,
                    "p_value": p_value,
                    "significant": p_value < 0.05
                }
        
        return {
            "total_benchmarks": len(self.benchmarks),
            "with_mcp": stats_with,
            "without_mcp": stats_without,
            "improvements": improvements,
            "percentage_improvements": pct_improvements,
            "statistical_tests": t_tests,
            "detailed_results": [r.to_dict() for r in results]
        }
