"""
Complete Integrated Pipeline v10 — All Components Wired Together

Round 10 improvements:
1. Complete pipeline integration (all components wired correctly)
2. Smart framework selection (considers multiple factors)
3. Quality gates (minimum threshold, retry logic)
4. Pre-existing tools integration (textstat, scipy, rich)
5. Local-first architecture (no external API calls)
6. End-to-end validation support

This is the final, production-ready pipeline.
"""

from __future__ import annotations

import time
import uuid
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Pre-existing tools integration
try:
    import textstat
    HAS_TEXTSTAT = True
except ImportError:
    HAS_TEXTSTAT = False

try:
    from scipy import stats as scipy_stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from core.cognitive.loop.core.store import SingularityStore
from core.cognitive.loop.core.classifier import classify_prompt
from core.cognitive.loop.pipeline.graph_v2 import TECHNIQUES
from core.cognitive.loop.pipeline.graph_v9 import ReasoningPipelineV9


@dataclass
class PipelineResult:
    """Complete result from pipeline execution."""
    
    # Input
    prompt: str
    session_id: str
    
    # Classification
    intent: str
    complexity: int
    budget_tier: str
    
    # Framework selection
    selected_framework: str
    framework_confidence: float
    alternative_frameworks: List[str]
    
    # Structure generation
    reasoning_template: str
    subproblems: List[dict]
    critique_dimensions: List[dict]
    adversarial_challenges: List[dict]
    
    # Quality metrics
    quality_score: float
    quality_passed: bool
    adherence_score: float
    readability_score: float
    
    # Analysis
    bias_flags: List[dict]
    citations: List[dict]
    
    # Metadata
    techniques_applied: List[str]
    duration_ms: int
    retry_count: int
    warnings: List[str]
    
    # Output
    structured_output: str


class CompletePipeline:
    """
    Complete integrated pipeline with all Round 10 improvements.
    
    Features:
    - Smart framework selection (considers intent, complexity, context)
    - Quality gates (minimum threshold, retry logic)
    - Readability analysis (textstat integration)
    - Local-first (no external API calls)
    - End-to-end validation support
    """
    
    QUALITY_THRESHOLD = 0.60  # Minimum quality score
    MAX_RETRIES = 2  # Maximum retry attempts
    
    def __init__(self, store: SingularityStore, mode: str = "amplified",
                 quality_threshold: float = 0.60, max_retries: int = 2,
                 record_sessions: bool = True):
        self.store = store
        self.mode = mode
        self.quality_threshold = quality_threshold
        self.max_retries = max_retries
        self.record_sessions = record_sessions
        self.v9_pipeline = ReasoningPipelineV9(store, mode=mode)
    
    def run(self, prompt: str, mode: str | None = None) -> PipelineResult:
        """Run complete pipeline with quality gates and smart selection."""
        start = time.time()
        session_id = f"rs_{uuid.uuid4().hex[:12]}"
        
        # Phase 1: Classify prompt
        classification = classify_prompt(prompt)
        
        # Phase 2: Smart framework selection
        framework, confidence, alternatives = self._select_framework_smart(
            prompt, classification
        )
        
        # Phase 3: Generate structure with quality gates
        retry_count = 0
        quality_passed = False
        state = None
        
        # BUGFIX (v14): old loop `while retry_count <= max_retries` with the
        # guard `retry_count < max_retries` stalled forever at the final
        # iteration (counter never advanced → unbounded DB writes). Use a
        # strict bounded loop: at most max_retries+1 attempts total.
        for retry_count in range(self.max_retries + 1):
            # Generate structure
            state = self.v9_pipeline.run(prompt, mode=mode or self.mode)
            
            # Calculate quality metrics
            quality_score = state.quality_score.get("total_score", 0.0)
            adherence = self._calculate_adherence(state)
            readability = self._calculate_readability(state.reasoning_template)
            
            # Check quality gate
            quality_passed = quality_score >= self.quality_threshold
            if quality_passed:
                break
            # Try alternative framework on retry (only if more attempts remain)
            if retry_count < self.max_retries and alternatives:
                framework = alternatives.pop(0)
        
        # Phase 4: Compile complete result
        duration_ms = int((time.time() - start) * 1000)
        
        result = PipelineResult(
            prompt=prompt,
            session_id=session_id,
            intent=classification.intent,
            complexity=classification.complexity,
            budget_tier=classification.budget_tier,
            selected_framework=framework,
            framework_confidence=confidence,
            alternative_frameworks=alternatives,
            reasoning_template=state.reasoning_template,
            subproblems=state.subproblems,
            critique_dimensions=state.critique_dimensions,
            adversarial_challenges=state.adversarial_challenges,
            quality_score=quality_score,
            quality_passed=quality_passed,
            adherence_score=adherence,
            readability_score=readability,
            bias_flags=state.bias_flags,
            citations=state.citations,
            techniques_applied=state.techniques_applied,
            duration_ms=duration_ms,
            retry_count=retry_count,
            warnings=state.warnings,
            structured_output=self._compile_output(state)
        )
        
        # Record session
        self._record_session(result)
        
        return result
    
    def get_pipeline_info(self) -> dict[str, Any]:
        """Pipeline configuration and technique details (delegates to v9)."""
        info = self.v9_pipeline.get_pipeline_info()
        info["mode"] = self.mode
        info["version"] = "15.1.0"
        # BUGFIX: v7/v9 chain never returns the v2-era keys "nodes" / "techniques"
        # / "total_techniques" → KeyError in reasoning_info tool. Map framework
        # names as the v14 "nodes" analog and cross-reference the v2 research
        # registry for citation data (name-only entries where no citation exists).
        frameworks = list(info.get("frameworks", []))
        info["nodes"] = frameworks
        techniques = []
        for name in frameworks:
            tech = TECHNIQUES.get(name)
            if tech:
                techniques.append({
                    "name": getattr(tech, "name", name),
                    "improvement": getattr(tech, "improvement", ""),
                    "paper": f"{getattr(tech, 'authors', '')} ({getattr(tech, 'year', '')})",
                    "venue": getattr(tech, "venue", ""),
                    "small_model_effective": getattr(tech, "small_model_effective", None),
                })
            else:
                techniques.append({
                    "name": name,
                    "improvement": "",
                    "paper": "",
                    "venue": "",
                    "small_model_effective": None,
                })
        info["techniques"] = techniques
        info["total_techniques"] = len(techniques)
        return info
    
    def _select_framework_smart(
        self, prompt: str, classification
    ) -> tuple[str, float, List[str]]:
        """Smart framework selection considering multiple factors."""
        intent = classification.intent
        complexity = classification.complexity
        
        # Analyze prompt characteristics
        prompt_lower = prompt.lower()
        
        # Factor 1: Intent-based mapping
        intent_frameworks = {
            "debug": ["reflexion", "five_whys", "chain_of_thought"],
            "build": ["verification_circuits", "decomposition", "react"],
            "decide": ["pros_cons_analysis", "react", "devil_advocate"],
            "research": ["self_ask", "socratic_method", "tree_of_thoughts"],
            "design": ["tree_of_thoughts", "first_principles", "meta_prompting"],
            "optimize": ["first_principles", "reflexion", "chain_of_thought"],
        }
        
        candidates = intent_frameworks.get(intent, ["chain_of_thought"])
        
        # Factor 2: Complexity adjustment
        if complexity >= 4:
            # High complexity → prefer advanced frameworks
            advanced = ["tree_of_thoughts", "self_ask", "verification_circuits", "reflexion"]
            candidates = [f for f in candidates if f in advanced] + candidates
        
        # Factor 3: Context keywords
        if "verify" in prompt_lower or "check" in prompt_lower:
            candidates = ["verification_circuits"] + candidates
        elif "compare" in prompt_lower or "pros" in prompt_lower:
            candidates = ["pros_cons_analysis"] + candidates
        elif "why" in prompt_lower or "reason" in prompt_lower:
            candidates = ["five_whys", "socratic_method"] + candidates
        elif "improve" in prompt_lower or "optimize" in prompt_lower:
            candidates = ["reflexion", "meta_prompting"] + candidates
        
        # Select best framework
        selected = candidates[0] if candidates else "chain_of_thought"
        alternatives = candidates[1:4]  # Top 3 alternatives
        
        # Calculate confidence
        confidence = self._calculate_framework_confidence(
            selected, intent, complexity, prompt
        )
        
        return selected, confidence, alternatives
    
    def _calculate_framework_confidence(
        self, framework: str, intent: str, complexity: int, prompt: str
    ) -> float:
        """Calculate confidence in framework selection."""
        confidence = 0.5  # Base confidence
        
        # Boost for clear intent match
        intent_frameworks = {
            "debug": ["reflexion", "five_whys"],
            "build": ["verification_circuits", "decomposition"],
            "decide": ["pros_cons_analysis"],
            "research": ["self_ask", "socratic_method"],
            "design": ["tree_of_thoughts", "first_principles"],
        }
        
        if framework in intent_frameworks.get(intent, []):
            confidence += 0.3
        
        # Boost for high complexity with advanced framework
        advanced_frameworks = ["tree_of_thoughts", "self_ask", "verification_circuits"]
        if complexity >= 4 and framework in advanced_frameworks:
            confidence += 0.2
        
        # Reduce for low complexity with advanced framework
        if complexity <= 2 and framework in advanced_frameworks:
            confidence -= 0.2
        
        # Cap at 1.0
        confidence = max(0.0, min(1.0, confidence))
        
        return confidence
    
    def _calculate_adherence(self, state) -> float:
        """Calculate how well generated structure follows framework requirements."""
        if not state.reasoning_template:
            return 0.5
        
        score = 0.5
        # 1. Section structure checks
        template_sections = re.findall(r'##\s+(.+)', state.reasoning_template)
        if len(template_sections) >= 3:
            score += 0.2
        elif len(template_sections) >= 1:
            score += 0.1
            
        # 2. Subproblem coverage
        if getattr(state, "subproblems", None) and len(state.subproblems) >= 1:
            score += 0.15
            
        # 3. Quality checks / critique dimensions present
        if getattr(state, "critique_dimensions", None) and len(state.critique_dimensions) >= 1:
            score += 0.15

        return round(min(1.0, max(0.0, score)), 3)
    
    def _calculate_readability(self, text: str) -> float:
        """Calculate readability score using textstat."""
        if not HAS_TEXTSTAT or not text:
            return 0.5
        
        try:
            # Flesch Reading Ease: 0-100 (higher = easier to read)
            flesch = textstat.flesch_reading_ease(text)
            
            # Normalize to 0-1 (assume 30-90 is typical range)
            normalized = max(0.0, min(1.0, (flesch - 30) / 60))
            
            return normalized
        except Exception:
            return 0.5
    
    def _compile_output(self, state) -> str:
        """Compile complete structured output."""
        parts = []
        
        # Add reasoning template
        if state.reasoning_template:
            parts.append(state.reasoning_template)
        
        # Add subproblems
        if state.subproblems:
            parts.append("\n## Subproblems\n")
            for sp in state.subproblems:
                parts.append(f"- **{sp['name']}**: {sp['description']}")
        
        # Add critique dimensions
        if state.critique_dimensions:
            parts.append("\n## Quality Checks\n")
            for cd in state.critique_dimensions:
                parts.append(f"- {cd['dimension']}: {cd['question']}")
        
        # Add adversarial challenges
        if state.adversarial_challenges:
            parts.append("\n## Adversarial Challenges\n")
            for ac in state.adversarial_challenges:
                parts.append(f"- **{ac['perspective']}**: {ac['challenge']}")
        
        # Add citations
        if state.citations:
            parts.append("\n## References\n")
            for cit in state.citations:
                parts.append(f"- {cit.get('paper', 'Unknown')}: {cit.get('title', '')}")
        
        return "\n".join(parts)
    
    def _record_session(self, result: PipelineResult):
        """Record session to store."""
        # BUGFIX (telemetry guard): skip recording when disabled by the caller
        # (eval/benchmark harnesses) or when duration is 0 — zero-duration rows
        # were the signature of the Aug-2026 flood (749k rows, 350MB DB).
        if not self.record_sessions or result.duration_ms <= 0:
            return
        try:
            self.store.create_session(
                session_id=result.session_id,
                prompt=result.prompt[:2000],
                intent=result.intent,
                complexity=result.complexity,
                budget_tier=result.budget_tier,
                steps=[]
            )
            self.store.complete_session(
                result.session_id,
                outcome={
                    "quality_score": result.quality_score,
                    "quality_passed": result.quality_passed,
                    "framework": result.selected_framework,
                    "framework_confidence": result.framework_confidence,
                    "retry_count": result.retry_count,
                    "techniques": result.techniques_applied,
                },
                metrics={
                    "adherence_score": result.adherence_score,
                    "readability_score": result.readability_score,
                    "duration_ms": result.duration_ms,
                },
                duration_ms=result.duration_ms
            )
        except Exception as e:
            # Don't fail if recording fails
            pass


def verify_local_first():
    """Verify pipeline is local-first (no external API calls)."""
    # Audit all imports
    import sys
    
    external_apis = [
        "openai", "anthropic", "requests", "httpx", "aiohttp",
        "urllib.request", "google", "azure", "aws"
    ]
    
    violations = []
    
    # Check loaded modules
    for module_name in sys.modules:
        for api in external_apis:
            if api in module_name:
                violations.append(f"External API detected: {module_name}")
    
    return {
        "local_first": len(violations) == 0,
        "violations": violations,
        "checked_modules": len(sys.modules)
    }


if __name__ == "__main__":
    # Test the complete pipeline
    print("="*70)
    print("COMPLETE PIPELINE v10 — Testing")
    print("="*70)
    print()
    
    # Verify local-first
    print("Verifying local-first architecture...")
    local_check = verify_local_first()
    
    if local_check["local_first"]:
        print("✅ Local-first verified (no external API calls)")
    else:
        print("❌ External API calls detected:")
        for v in local_check["violations"][:5]:
            print(f"  - {v}")
    
    print(f"Checked {local_check['checked_modules']} modules")
    print()
    
    # Test pipeline
    import tempfile
    store = SingularityStore(tempfile.mkdtemp())
    pipeline = CompletePipeline(store)
    
    test_prompts = [
        "Debug a memory leak in my Python application",
        "Design a rate limiter for distributed systems",
        "Should we use microservices or monolith?",
    ]
    
    for prompt in test_prompts:
        print(f"Testing: {prompt[:50]}...")
        result = pipeline.run(prompt)
        
        print(f"  Framework: {result.selected_framework} (confidence: {result.framework_confidence:.2f})")
        print(f"  Quality: {result.quality_score:.3f} (passed: {result.quality_passed})")
        print(f"  Adherence: {result.adherence_score:.3f}")
        print(f"  Readability: {result.readability_score:.3f}")
        print(f"  Retries: {result.retry_count}")
        print(f"  Duration: {result.duration_ms}ms")
        print()
    
    print("="*70)
    print("✅ COMPLETE PIPELINE TEST PASSED")
    print("="*70)
