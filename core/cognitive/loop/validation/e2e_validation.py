"""
End-to-End Validation — Test Complete Pipeline as Real User Would

This validates the entire pipeline from prompt to structured output,
simulating how a real user would interact with the MCP.
"""

import tempfile
import time
from dataclasses import dataclass
from typing import Dict, List

from core.cognitive.loop.core.store import SingularityStore
from core.cognitive.loop.pipeline.complete_pipeline import CompletePipeline, verify_local_first


@dataclass
class E2ETestCase:
    """A single E2E test case."""
    id: str
    prompt: str
    expected_intent: str
    expected_framework: str  # One of the expected frameworks
    min_quality: float  # Minimum acceptable quality score


# E2E test cases
E2E_TEST_CASES = [
    E2ETestCase(
        id="e2e_debug_01",
        prompt="My React app keeps re-rendering on every state update. How do I fix this performance issue?",
        expected_intent="debug",
        expected_framework="reflexion",  # or five_whys, chain_of_thought
        min_quality=0.5
    ),
    E2ETestCase(
        id="e2e_build_01",
        prompt="Build a REST API endpoint that accepts user registration with email validation and password hashing.",
        expected_intent="build",
        expected_framework="verification_circuits",  # or decomposition
        min_quality=0.5
    ),
    E2ETestCase(
        id="e2e_decide_01",
        prompt="Should we use PostgreSQL or MongoDB for our e-commerce platform with complex queries and 50K daily users?",
        expected_intent="decide",
        expected_framework="pros_cons_analysis",
        min_quality=0.5
    ),
    E2ETestCase(
        id="e2e_research_01",
        prompt="What are the latest advances in transformer model efficiency for edge deployment in 2024?",
        expected_intent="research",
        expected_framework="self_ask",  # or socratic_method
        min_quality=0.5
    ),
    E2ETestCase(
        id="e2e_design_01",
        prompt="Design a URL shortener service that can handle 100M URLs and 10K requests per second.",
        expected_intent="design",
        expected_framework="tree_of_thoughts",  # or first_principles
        min_quality=0.5
    ),
    E2ETestCase(
        id="e2e_optimize_01",
        prompt="My PostgreSQL query takes 10 seconds on a table with 1M rows. EXPLAIN shows sequential scan. How do I optimize it?",
        expected_intent="debug",  # or optimize
        expected_framework="five_whys",  # or first_principles
        min_quality=0.5
    ),
]


class E2EValidator:
    """Validate complete pipeline end-to-end."""
    
    def __init__(self, store: SingularityStore):
        self.store = store
        self.pipeline = CompletePipeline(store)
    
    def run_validation(self, test_cases: List[E2ETestCase] = None) -> Dict:
        """Run E2E validation on all test cases."""
        if test_cases is None:
            test_cases = E2E_TEST_CASES
        
        results = []
        passed = 0
        failed = 0
        
        print(f"Running E2E validation on {len(test_cases)} test cases...")
        print()
        
        for test_case in test_cases:
            print(f"Testing: {test_case.id}")
            print(f"  Prompt: {test_case.prompt[:60]}...")
            
            # Run pipeline
            start = time.time()
            result = self.pipeline.run(test_case.prompt)
            duration = time.time() - start
            
            # Validate results
            validation = self._validate_result(result, test_case)
            
            test_result = {
                "id": test_case.id,
                "prompt": test_case.prompt,
                "result": result,
                "validation": validation,
                "duration_s": duration,
                "passed": validation["all_checks_passed"]
            }
            
            results.append(test_result)
            
            if validation["all_checks_passed"]:
                passed += 1
                print("  ✅ PASSED")
            else:
                failed += 1
                print("  ❌ FAILED")
                for check, passed_check in validation["checks"].items():
                    if not passed_check:
                        print(f"     - {check}: FAILED")
            
            print(f"  Framework: {result.selected_framework} (confidence: {result.framework_confidence:.2f})")
            print(f"  Quality: {result.quality_score:.3f} (min: {test_case.min_quality})")
            print(f"  Duration: {duration:.2f}s")
            print()
        
        # Generate report
        report = self._generate_report(results, passed, failed)
        
        return report
    
    def _validate_result(self, result, test_case: E2ETestCase) -> Dict:
        """Validate a single result against test case expectations."""
        checks = {}
        
        # Check 1: Intent classification
        checks["intent_correct"] = result.intent == test_case.expected_intent
        
        # Check 2: Framework selection (flexible - accept alternatives)
        expected_frameworks = {
            "debug": ["reflexion", "five_whys", "chain_of_thought"],
            "build": ["verification_circuits", "decomposition", "react"],
            "decide": ["pros_cons_analysis", "react", "devil_advocate"],
            "research": ["self_ask", "socratic_method", "tree_of_thoughts"],
            "design": ["tree_of_thoughts", "first_principles", "meta_prompting"],
            "optimize": ["first_principles", "reflexion", "chain_of_thought"],
        }
        
        acceptable_frameworks = expected_frameworks.get(
            test_case.expected_intent, [test_case.expected_framework]
        )
        checks["framework_acceptable"] = result.selected_framework in acceptable_frameworks
        
        # Check 3: Quality threshold
        checks["quality_met"] = result.quality_score >= test_case.min_quality
        
        # Check 4: Quality passed gate
        checks["quality_passed"] = result.quality_passed
        
        # Check 5: Has structure
        checks["has_structure"] = len(result.reasoning_template) > 100
        
        # Check 6: Has subproblems
        checks["has_subproblems"] = len(result.subproblems) > 0
        
        # Check 7: Has critique dimensions
        checks["has_critiques"] = len(result.critique_dimensions) > 0
        
        # Check 8: Reasonable duration (< 5 seconds)
        checks["reasonable_duration"] = result.duration_ms < 5000
        
        # Check 9: Framework confidence > 0.3
        checks["framework_confident"] = result.framework_confidence > 0.3
        
        # Check 10: Readability score > 0.3
        checks["readable"] = result.readability_score > 0.3
        
        # Overall pass/fail
        all_passed = all(checks.values())
        
        return {
            "checks": checks,
            "all_checks_passed": all_passed,
            "passed_count": sum(checks.values()),
            "total_count": len(checks)
        }
    
    def _generate_report(self, results: List[Dict], passed: int, failed: int) -> Dict:
        """Generate comprehensive E2E report."""
        total = len(results)
        
        # Calculate statistics
        avg_quality = sum(r["result"].quality_score for r in results) / total
        avg_duration = sum(r["duration_s"] for r in results) / total
        avg_confidence = sum(r["result"].framework_confidence for r in results) / total
        
        # Count framework usage
        framework_counts = {}
        for r in results:
            fw = r["result"].selected_framework
            framework_counts[fw] = framework_counts.get(fw, 0) + 1
        
        # Count check failures
        check_failures = {}
        for r in results:
            for check, passed_check in r["validation"]["checks"].items():
                if not passed_check:
                    check_failures[check] = check_failures.get(check, 0) + 1
        
        # Generate conclusion
        pass_rate = passed / total
        if pass_rate >= 0.9:
            conclusion = "✅ EXCELLENT: E2E validation passed with high success rate"
        elif pass_rate >= 0.7:
            conclusion = "⚠ GOOD: E2E validation passed with acceptable success rate"
        elif pass_rate >= 0.5:
            conclusion = "⚠ FAIR: E2E validation passed with moderate success rate"
        else:
            conclusion = "❌ POOR: E2E validation failed with low success rate"
        
        report = {
            "summary": {
                "total_tests": total,
                "passed": passed,
                "failed": failed,
                "pass_rate": pass_rate,
            },
            "statistics": {
                "avg_quality": avg_quality,
                "avg_duration_s": avg_duration,
                "avg_framework_confidence": avg_confidence,
            },
            "framework_usage": framework_counts,
            "check_failures": check_failures,
            "conclusion": conclusion,
            "detailed_results": results,
        }
        
        return report


def run_e2e_validation(store: SingularityStore = None) -> Dict:
    """Run E2E validation and return results."""
    if store is None:
        store = SingularityStore(tempfile.mkdtemp())
    
    validator = E2EValidator(store)
    report = validator.run_validation()
    
    return report


if __name__ == "__main__":
    # Run E2E validation
    print("="*70)
    print("END-TO-END VALIDATION — Testing Complete Pipeline")
    print("="*70)
    print()
    
    # Verify local-first
    print("Verifying local-first architecture...")
    local_check = verify_local_first()
    
    if local_check["local_first"]:
        print("✅ Local-first verified")
    else:
        print("❌ External API calls detected")
    
    print()
    
    # Run E2E validation
    report = run_e2e_validation()
    
    print("="*70)
    print("E2E VALIDATION RESULTS")
    print("="*70)
    print()
    
    print(f"Total tests: {report['summary']['total_tests']}")
    print(f"Passed: {report['summary']['passed']}")
    print(f"Failed: {report['summary']['failed']}")
    print(f"Pass rate: {report['summary']['pass_rate']:.1%}")
    print()
    
    print("Statistics:")
    print(f"  Avg quality: {report['statistics']['avg_quality']:.3f}")
    print(f"  Avg duration: {report['statistics']['avg_duration_s']:.2f}s")
    print(f"  Avg framework confidence: {report['statistics']['avg_framework_confidence']:.2f}")
    print()
    
    print("Framework usage:")
    for fw, count in sorted(report['framework_usage'].items(), key=lambda x: x[1], reverse=True):
        print(f"  {fw}: {count}")
    print()
    
    if report['check_failures']:
        print("Check failures:")
        for check, count in sorted(report['check_failures'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {check}: {count}")
        print()
    
    print("="*70)
    print("CONCLUSION")
    print("="*70)
    print()
    print(report['conclusion'])
    print()
