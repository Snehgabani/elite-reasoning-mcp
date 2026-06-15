import logging
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, ContextualRelevancyMetric, GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from app.config import ConfigLoader

logger = logging.getLogger(__name__)

class EliteEvaluator:
    """
    Integrates DeepEval to measure response quality.
    Called post-generation or out-of-band via background jobs
    to score outputs and update memory/telemetry profiles.
    """
    def __init__(self, config: ConfigLoader):
        self.config = config
        self.enabled = config.get("telemetry.deepeval_enabled", False)
        
        # Metrics will be lazy-loaded in evaluate_response to avoid OpenAI key errors on startup
        self._answer_relevancy = None
        self._faithfulness = None
        self._contextual_relevancy = None
        self._completeness = None
        self._clarity = None
        
    def evaluate_response(self, input_text: str, actual_output: str, retrieval_context: list[str]) -> dict:
        """
        Evaluate a single response using DeepEval metrics.
        Returns a dictionary of scores.
        """
        if not self.enabled:
            return {}
            
        test_case = LLMTestCase(
            input=input_text,
            actual_output=actual_output,
            retrieval_context=retrieval_context
        )
        
        scores = {}
        try:
            from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, ContextualRelevancyMetric
            
            if self._answer_relevancy is None:
                self._answer_relevancy = AnswerRelevancyMetric(threshold=0.5, strict_mode=False)
            if self._faithfulness is None:
                self._faithfulness = FaithfulnessMetric(threshold=0.5, strict_mode=False)
            if self._contextual_relevancy is None:
                self._contextual_relevancy = ContextualRelevancyMetric(threshold=0.5, strict_mode=False)
                
            # Measure relevancy
            self._answer_relevancy.measure(test_case)
            scores["answer_relevancy"] = self._answer_relevancy.score
            
            # Measure faithfulness
            self._faithfulness.measure(test_case)
            scores["faithfulness"] = self._faithfulness.score
            
            # Measure contextual relevancy
            self._contextual_relevancy.measure(test_case)
            scores["contextual_relevancy"] = self._contextual_relevancy.score
            
            if self._completeness is None:
                self._completeness = GEval(
                    name="Task Completeness",
                    criteria="Determine if the actual output fully addresses and answers the user input.",
                    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT]
                )
            if self._clarity is None:
                self._clarity = GEval(
                    name="Clarity and Coherence",
                    criteria="Determine if the actual output is well-structured, concise, and logically coherent.",
                    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT]
                )
                
            # Measure generic benchmark criteria
            self._completeness.measure(test_case)
            scores["task_completeness"] = self._completeness.score
            
            self._clarity.measure(test_case)
            scores["clarity"] = self._clarity.score
            
            # Aggregate Elite Score
            elite_score = (
                scores.get("answer_relevancy", 0) * 0.3 +
                scores.get("faithfulness", 0) * 0.3 +
                scores.get("task_completeness", 0) * 0.2 +
                scores.get("clarity", 0) * 0.2
            )
            scores["elite_score"] = round(elite_score, 2)
            
            logger.info(f"Evaluation complete. Elite Score: {scores['elite_score']} | Metrics: {scores}")
            
        except Exception as e:
            logger.error(f"Error during DeepEval evaluation: {e}")
            
        return scores
