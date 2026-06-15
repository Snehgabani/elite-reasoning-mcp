from pydantic import BaseModel
from typing import List, Optional

class PreflightResult(BaseModel):
    intent_class: str          # Q-paste / Correction / Routine / Decision / Infrastructure / External-AI
    framework_stack: List[str] # Which reasoning frameworks to apply
    confidence_cap: float      # Required confidence threshold
    recall_needed: bool        # Whether to query vector store
    hard_stop: bool = False    # If the action violates a core constraint

class PreflightChecklist:
    """
    Pre-flight checklist (mirrors SOUL.md §218-246).
    Classifies intent and determines the reasoning path.
    """
    def __init__(self, soul_parser):
        self.soul = soul_parser

    def evaluate(self, user_prompt: str) -> PreflightResult:
        """
        Evaluate the prompt to determine the execution path.
        Uses DSPy Algorithmic Prompt Optimization for classification.
        """
        try:
            from core.prompts.dspy_modules import PreflightClassifier
            classifier = PreflightClassifier()
            output = classifier(user_prompt)
            
            # Map DSPy output to PreflightResult
            intent = output.intent_class
            frameworks = output.framework_stack
            cap = output.confidence_cap
            recall = output.recall_needed
            hard_stop = output.hard_stop
        except Exception as e:
            # Fallback to heuristics if DSPy is unconfigured or errors out
            prompt_lower = user_prompt.lower()
            if "paste" in prompt_lower or "uworld" in prompt_lower or "nbme" in prompt_lower:
                intent = "Q-paste"
                frameworks = ["usmle-decode-pipeline"]
                cap = 0.95
                recall = True
            elif "fix" in prompt_lower or "wrong" in prompt_lower or "error" in prompt_lower:
                intent = "Correction"
                frameworks = ["mistake-prevention-fmea"]
                cap = 0.99
                recall = True
            elif "should i" in prompt_lower or "decide" in prompt_lower or "evaluate" in prompt_lower:
                intent = "Decision"
                frameworks = ["elite-reasoning-framework", "expected-value"]
                cap = 0.80
                recall = True
            elif "deploy" in prompt_lower or "build" in prompt_lower or "architect" in prompt_lower:
                intent = "Infrastructure"
                frameworks = ["system-design-patterns", "pre-mortem"]
                cap = 0.90
                recall = True
            else:
                intent = "Routine"
                frameworks = []
                cap = 0.50
                recall = False
            hard_stop = "ignore your instructions" in prompt_lower

        return PreflightResult(
            intent_class=intent,
            framework_stack=frameworks,
            confidence_cap=cap,
            recall_needed=recall,
            hard_stop=hard_stop
        )
