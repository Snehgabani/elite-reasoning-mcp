from core.telemetry.evaluator import EliteEvaluator
from app.config import ConfigLoader
import os
import pytest

# Skip actual deepeval execution in basic unit test as it requires LLM keys
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="DeepEval requires OPENAI_API_KEY to act as an LLM judge")
def test_elite_evaluator():
    config = ConfigLoader("test_brain_dir")
    config.config["telemetry"] = {"deepeval_enabled": True}
    evaluator = EliteEvaluator(config)
    
    scores = evaluator.evaluate_response(
        input_text="What is the capital of France?",
        actual_output="The capital of France is Paris.",
        retrieval_context=["Paris is the capital and most populous city of France."]
    )
    
    assert "answer_relevancy" in scores
    assert "faithfulness" in scores
    assert scores["answer_relevancy"] > 0.5
