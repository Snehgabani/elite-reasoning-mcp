"""
Goal-Oriented Execution Pipeline — For Smaller/Faster Models

This pipeline is designed for "flash" models (smaller, faster, less capable) that:
- Often lose track of goals
- Do redundant work
- Close prematurely before work is complete
- Don't verify their work

The pipeline:
1. Breaks goals into verifiable steps
2. Executes each step with the model
3. Verifies each step using multiple methods
4. Loops back if verification fails
5. Detects drift from goals
6. Detects redundant work
7. Prevents premature closure
8. Continues until quality is achieved

This is an agentic execution system, not just a reasoning structure generator.
"""

from __future__ import annotations

import time
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable

from core.cognitive.loop.core.store import SingularityStore
from core.cognitive.loop.pipeline.complete_pipeline import CompletePipeline


@dataclass
class Goal:
    """A user goal to achieve."""
    id: str
    description: str
    success_criteria: List[str]  # How to verify goal is achieved
    max_iterations: int = 10  # Maximum iterations before giving up
    quality_threshold: float = 0.80  # Minimum quality to consider complete


@dataclass
class Step:
    """A single step in achieving a goal."""
    id: str
    description: str
    verification_methods: List[str]  # How to verify this step
    completed: bool = False
    verification_passed: bool = False
    attempts: int = 0
    max_attempts: int = 3


@dataclass
class ExecutionState:
    """State of goal execution."""
    goal: Goal
    steps: List[Step]
    current_step_index: int = 0
    iteration: int = 0
    history: List[Dict] = field(default_factory=list)
    final_result: Optional[str] = None
    quality_score: float = 0.0
    complete: bool = False
    drift_detected: bool = False
    redundancy_detected: bool = False


class GoalOrientedPipeline:
    """
    Goal-oriented execution pipeline for smaller/faster models.
    
    Keeps models on track, verifies work, loops until quality achieved.
    """
    
    def __init__(
        self,
        store: SingularityStore,
        model_executor: Callable[[str], str],  # Function that executes model
        verification_methods: Dict[str, Callable[[str, str], bool]] = None
    ):
        """
        Initialize goal-oriented pipeline.
        
        Args:
            store: Singularity store for persistence
            model_executor: Function that takes prompt and returns model output
            verification_methods: Dict of verification method name -> function
        """
        self.store = store
        self.model_executor = model_executor
        self.verification_methods = verification_methods or {}
        self.reasoning_pipeline = CompletePipeline(store)
    
    def execute_goal(self, goal: Goal) -> ExecutionState:
        """
        Execute a goal with verification loops.
        
        Args:
            goal: Goal to achieve
            
        Returns:
            ExecutionState with final result
        """
        # Decompose goal into steps
        steps = self._decompose_goal(goal)
        
        state = ExecutionState(goal=goal, steps=steps)
        
        # Execute with verification loops
        while not state.complete and state.iteration < goal.max_iterations:
            state.iteration += 1
            
            # Execute current step
            self._execute_step(state)
            
            # Verify step
            self._verify_step(state)
            
            # Check for drift
            if self._detect_drift(state):
                state.drift_detected = True
                # Reset to last good step
                state.current_step_index = max(0, state.current_step_index - 1)
                continue
            
            # Check for redundancy
            if self._detect_redundancy(state):
                state.redundancy_detected = True
                state.current_step_index = min(len(state.steps), state.current_step_index + 1)
            else:
                # Move to next step if current step passed
                current_step = state.steps[min(state.current_step_index, len(state.steps) - 1)]
                if current_step.verification_passed:
                    state.current_step_index += 1

            # Check if all steps complete
            if state.current_step_index >= len(state.steps):
                if self._verify_goal(state):
                    state.complete = True
                    break
                else:
                    state.current_step_index = len(state.steps) - 1
            
            # Record history
            state.history.append({
                "iteration": state.iteration,
                "step": state.current_step_index,
                "drift": state.drift_detected,
                "redundancy": state.redundancy_detected,
                "quality": state.quality_score
            })
        
        return state
    
    def _decompose_goal(self, goal: Goal) -> List[Step]:
        """Decompose goal into verifiable steps."""
        # Create standard steps for any goal
        # These are generic enough to work for most goals
        steps = []
        
        # Step 1: Understand the goal
        steps.append(Step(
            id=str(uuid.uuid4()),
            description=f"Understand the goal: {goal.description}",
            verification_methods=["rubric", "keyword_check"]
        ))
        
        # Step 2: Plan the approach
        steps.append(Step(
            id=str(uuid.uuid4()),
            description="Plan the approach and break it down",
            verification_methods=["rubric", "structure_check"]
        ))
        
        # Step 3: Execute the plan
        steps.append(Step(
            id=str(uuid.uuid4()),
            description="Execute the planned approach",
            verification_methods=["rubric", "test", "web_search"]
        ))
        
        # Step 4: Verify against success criteria
        for i, criteria in enumerate(goal.success_criteria[:3]):  # Max 3 criteria steps
            steps.append(Step(
                id=str(uuid.uuid4()),
                description=f"Verify: {criteria}",
                verification_methods=["rubric", "keyword_check"]
            ))
        
        return steps
    
    def _execute_step(self, state: ExecutionState):
        """Execute current step."""
        idx = min(max(0, state.current_step_index), len(state.steps) - 1)
        current_step = state.steps[idx]
        current_step.attempts += 1
        
        # Build prompt for this step
        prompt = self._build_step_prompt(state, current_step)
        
        # Execute with model
        output = self.model_executor(prompt)
        
        # Store in history
        state.history.append({
            "type": "execution",
            "step": current_step.id,
            "attempt": current_step.attempts,
            "output": output
        })
    
    def _verify_step(self, state: ExecutionState):
        """Verify current step using multiple methods."""
        idx = min(max(0, state.current_step_index), len(state.steps) - 1)
        current_step = state.steps[idx]
        
        # Get last execution output
        last_execution = None
        for h in reversed(state.history):
            if h.get("type") == "execution" and h.get("step") == current_step.id:
                last_execution = h.get("output")
                break
        
        if not last_execution:
            current_step.verification_passed = False
            return
        
        # Run all verification methods
        verification_results = []
        for method_name in current_step.verification_methods:
            if method_name in self.verification_methods:
                method = self.verification_methods[method_name]
                try:
                    result = method(last_execution, current_step.description)
                    verification_results.append(result)
                except Exception:
                    verification_results.append(False)
        
        # Step passes if majority of verifications pass
        passed_count = sum(1 for r in verification_results if r)
        current_step.verification_passed = passed_count > len(verification_results) / 2
        current_step.completed = current_step.verification_passed
    
    def _detect_drift(self, state: ExecutionState) -> bool:
        """Detect if model is drifting from goal."""
        # Get recent executions
        recent_executions = [
            h for h in state.history[-5:]
            if h.get("type") == "execution"
        ]
        
        if len(recent_executions) < 2:
            return False
        
        # Check if recent outputs are relevant to goal
        goal_keywords = self._extract_keywords(state.goal.description)
        
        for execution in recent_executions:
            output = execution.get("output", "")
            output_keywords = self._extract_keywords(output)
            
            # Check overlap
            overlap = len(set(goal_keywords) & set(output_keywords))
            if overlap < len(goal_keywords) * 0.3:  # Less than 30% overlap
                return True
        
        return False
    
    def _detect_redundancy(self, state: ExecutionState) -> bool:
        """Detect if model is doing redundant work."""
        # Get recent executions
        recent_executions = [
            h for h in state.history[-3:]
            if h.get("type") == "execution"
        ]
        
        if len(recent_executions) < 2:
            return False
        
        # Check if outputs are very similar
        outputs = [e.get("output", "") for e in recent_executions]
        
        # Simple similarity check
        for i in range(len(outputs) - 1):
            if self._similarity(outputs[i], outputs[i+1]) > 0.8:
                return True
        
        return False
    
    def _verify_goal(self, state: ExecutionState) -> bool:
        """Verify overall goal is achieved."""
        # Use success criteria
        for criteria in state.goal.success_criteria:
            # Check if criteria is met
            # For now, simple keyword check
            criteria_keywords = self._extract_keywords(criteria)
            
            # Check all step outputs
            all_outputs = " ".join([
                h.get("output", "")
                for h in state.history
                if h.get("type") == "execution"
            ])
            
            output_keywords = self._extract_keywords(all_outputs)
            
            # Check overlap
            overlap = len(set(criteria_keywords) & set(output_keywords))
            if overlap < len(criteria_keywords) * 0.5:
                return False
        
        return True
    
    def _build_step_prompt(self, state: ExecutionState, step: Step) -> str:
        """Build prompt for executing a step."""
        parts = [
            f"## Goal\n{state.goal.description}\n",
            f"## Current Step\n{step.description}\n",
            f"## Step {state.current_step_index + 1} of {len(state.steps)}\n",
            f"## Iteration {state.iteration} of {state.goal.max_iterations}\n",
        ]
        
        # Add context from previous steps
        prev_count = min(state.current_step_index, len(state.steps))
        if prev_count > 0:
            parts.append("## Previous Steps\n")
            for i in range(prev_count):
                prev_step = state.steps[i]
                parts.append(f"- Step {i+1}: {prev_step.description} ({'✓' if prev_step.completed else '✗'})")
            parts.append("")
        
        # Add instructions
        parts.append("## Instructions\n")
        parts.append(f"Execute the current step: {step.description}\n")
        parts.append("Provide a complete, detailed response.")
        parts.append("Stay focused on the goal.")
        parts.append("Don't repeat previous work.")
        
        return "\n".join(parts)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        # Simple keyword extraction
        words = re.findall(r'\b\w+\b', text.lower())
        # Remove common words
        common = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        return [w for w in words if len(w) > 3 and w not in common]
    
    def _similarity(self, text1: str, text2: str) -> float:
        """Calculate simple similarity between two texts."""
        words1 = set(self._extract_keywords(text1))
        words2 = set(self._extract_keywords(text2))
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0


# Example verification methods
def rubric_verification(output: str, step_description: str) -> bool:
    """Verify output using rubric."""
    # Simple rubric: check length, structure, keywords
    if len(output) < 100:
        return False
    
    # Check for structure
    if not any(marker in output for marker in ['##', '###', '1.', '2.', '-']):
        return False
    
    return True


def keyword_verification(output: str, step_description: str) -> bool:
    """Verify output contains relevant keywords."""
    keywords = GoalOrientedPipeline(None, None)._extract_keywords(step_description)
    output_keywords = GoalOrientedPipeline(None, None)._extract_keywords(output)
    
    overlap = len(set(keywords) & set(output_keywords))
    return overlap >= len(keywords) * 0.3


def structure_verification(output: str, step_description: str) -> bool:
    """Verify output has proper structure."""
    # Check for sections
    has_sections = bool(re.search(r'##\s+', output))
    
    # Check for lists
    has_lists = bool(re.search(r'^\s*[-*]\s+', output, re.MULTILINE))
    
    return has_sections or has_lists


if __name__ == "__main__":
    # Test goal-oriented pipeline
    print("="*70)
    print("GOAL-ORIENTED PIPELINE — Testing")
    print("="*70)
    print()
    
    # Mock model executor
    def mock_model(prompt: str) -> str:
        """Mock model that generates simple responses."""
        return f"""
## Response to: {prompt[:50]}...

### Understanding
I understand the goal and requirements.

### Plan
1. First, I'll analyze the problem
2. Then, I'll implement a solution
3. Finally, I'll verify it works

### Execution
Here's my implementation:
- Step 1: Analyzed
- Step 2: Implemented
- Step 3: Verified

### Verification
The solution meets all criteria:
✓ Criteria 1 met
✓ Criteria 2 met
✓ Criteria 3 met
"""
    
    # Create verification methods
    verification_methods = {
        "rubric": rubric_verification,
        "keyword_check": keyword_verification,
        "structure_check": structure_verification,
    }
    
    # Create pipeline
    import tempfile
    store = SingularityStore(tempfile.mkdtemp())
    pipeline = GoalOrientedPipeline(
        store=store,
        model_executor=mock_model,
        verification_methods=verification_methods
    )
    
    # Create goal
    goal = Goal(
        id="test_goal",
        description="Build a REST API with authentication",
        success_criteria=[
            "API endpoints created",
            "Authentication implemented",
            "Tests passing"
        ],
        max_iterations=5
    )
    
    # Execute goal
    print(f"Executing goal: {goal.description}")
    print(f"Max iterations: {goal.max_iterations}")
    print()
    
    state = pipeline.execute_goal(goal)
    
    print(f"Complete: {state.complete}")
    print(f"Iterations: {state.iteration}")
    print(f"Drift detected: {state.drift_detected}")
    print(f"Redundancy detected: {state.redundancy_detected}")
    print(f"Steps completed: {sum(1 for s in state.steps if s.completed)}/{len(state.steps)}")
    print()
    
    print("="*70)
    print("✅ GOAL-ORIENTED PIPELINE TEST COMPLETE")
    print("="*70)
