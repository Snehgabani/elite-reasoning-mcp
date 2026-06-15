import os
from langchain_core.messages import HumanMessage
from core.persistence.store import StateStore
from core.persistence.file_store import FileStore
from core.persistence.vector_store import HybridGraphStore
from core.identity.soul import SoulParser
from core.identity.preflight import PreflightChecklist
from core.memory.manager import MemoryManager
from core.memory.retrieval import MemoryRetrieval
from core.skills.registry import SkillRegistry
from core.skills.executor import SkillExecutor
from core.reasoning.elite_framework import EliteReasoningFramework
from app.config import ConfigLoader
from app.graph import build_app_graph

import asyncio
from typing import Dict, Any
import dspy

# Configure LM for DSPy
class MockDSPyLM(dspy.LM):
    def __init__(self):
        super().__init__("mock")
    def __call__(self, prompt=None, messages=None, **kwargs):
        import json
        return [json.dumps({"reasoning": "mock reasoning", "mitigations": "mock mitigations"})]

dspy.configure(lm=MockDSPyLM())

# Mock LLM for fast testing
class MockLLM:
    def invoke(self, *args, **kwargs):
        return HumanMessage(content="This is a mocked response.")

def main():
    brain_dir = os.path.expanduser("~/.gemini/antigravity/scratch/elite-system/brain")
    os.makedirs(brain_dir, exist_ok=True)
    os.makedirs(os.path.join(brain_dir, "memory"), exist_ok=True)
    
    config = ConfigLoader(brain_dir)
    llm = MockLLM()
    
    file_store = FileStore(brain_dir)
    vector_store = HybridGraphStore(brain_dir=brain_dir)
    state_store = StateStore(os.path.join(brain_dir, "state.db"))
    
    soul_parser = SoulParser(brain_dir)
    dependencies = {
        "soul": soul_parser,
        "preflight": PreflightChecklist(soul_parser),
        "memory": MemoryManager(brain_dir, vector_store),
        "retrieval": MemoryRetrieval(vector_store),
        "skills": SkillRegistry(brain_dir, SkillExecutor(llm)),
        "reasoning": EliteReasoningFramework(),
        "llm": llm,
        "config": config,
        "file_store": file_store,
        "state_store": state_store
    }
    
    graph = build_app_graph(dependencies)
    app = graph.compile()
    
    print("Testing graph invocation...")
    input_text = "Apply first principles to building a rocket."
    state = {
        "messages": [HumanMessage(content=input_text)],
        "intent_class": "",
        "framework_stack": [],
        "confidence_cap": 0.0,
        "recall_needed": False,
        "hard_stop": False,
        "memory_context": "",
        "reasoning_output": {},
        "fmea_score": 0
    }
    
    # 1. Setup Langfuse Tracing
    callbacks = []
    if config.get("telemetry.langfuse_enabled", False):
        try:
            from langfuse.langchain import CallbackHandler
            langfuse_handler = CallbackHandler()
            callbacks.append(langfuse_handler)
            print("Langfuse tracing enabled.")
        except Exception as e:
            print(f"Warning: Langfuse CallbackHandler not initialized ({e})")
    
    final_state = app.invoke(state, config={"callbacks": callbacks} if callbacks else None)
    
    response_content = final_state["messages"][-1].content
    print("Agent output:", response_content)
    
    # 2. DeepEval Scoring
    if config.get("telemetry.deepeval_enabled", False):
        print("\nRunning DeepEval unit-tests...")
        from core.telemetry.evaluator import EliteEvaluator
        evaluator = EliteEvaluator(config)
        retrieval_context = [final_state.get("memory_context", "")]
        scores = evaluator.evaluate_response(
            input_text=input_text,
            actual_output=response_content,
            retrieval_context=retrieval_context
        )
        print("DeepEval Scores:", scores)

if __name__ == "__main__":
    main()

