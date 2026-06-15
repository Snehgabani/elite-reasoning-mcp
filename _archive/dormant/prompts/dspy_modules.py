import dspy
from pydantic import BaseModel, Field

class PreflightOutput(BaseModel):
    intent_class: str = Field(description="One of: Q-paste, Correction, Routine, Decision, Infrastructure, External-AI, Clarification")
    framework_stack: list[str] = Field(description="List of reasoning frameworks to apply (e.g., 'elite-reasoning-framework')")
    confidence_cap: float = Field(description="Required confidence threshold between 0.0 and 1.0")
    recall_needed: bool = Field(description="Whether to query the vector store")
    hard_stop: bool = Field(description="True if the action violates a core constraint")

class PreflightSignature(dspy.Signature):
    """Classify the user prompt to determine execution path. If the request is ambiguous, lacks a goal, or requires a timeline, classify as 'Clarification'."""
    user_prompt = dspy.InputField(desc="The message from the user")
    
    classification: PreflightOutput = dspy.OutputField()

class PreflightClassifier(dspy.Module):
    def __init__(self):
        super().__init__()
        # Use TypedPredictor if available in DSPy 2.x, otherwise fallback to Predict
        try:
            self.classifier = dspy.TypedPredictor(PreflightSignature)
        except AttributeError:
            self.classifier = dspy.Predict(PreflightSignature)
        
    def forward(self, user_prompt: str) -> PreflightOutput:
        prediction = self.classifier(user_prompt=user_prompt)
        # TypedPredictor returns the pydantic model directly on the field
        if hasattr(prediction, 'classification'):
            return prediction.classification
        
        # Fallback parsing if we used standard Predict without Types
        return PreflightOutput(
            intent_class="Routine",
            framework_stack=[],
            confidence_cap=0.5,
            recall_needed=False,
            hard_stop=False
        )
