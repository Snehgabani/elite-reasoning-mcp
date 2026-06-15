import os
import asyncio
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
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
import dspy

# Configure LM for DSPy
class MockDSPyLM(dspy.LM):
    def __init__(self):
        super().__init__("mock")
    def __call__(self, prompt=None, messages=None, **kwargs):
        import json
        return [json.dumps({"reasoning": "mock reasoning", "mitigations": "mock mitigations"})]

dspy.configure(lm=MockDSPyLM())

class MockLLMWithTools:
    def __init__(self):
        self.tools = []
        self.call_count = 0

    def bind_tools(self, tools):
        self.tools = tools
        return self

    def invoke(self, messages, *args, **kwargs):
        self.call_count += 1
        
        # On the first call, pretend to invoke a tool
        if self.call_count == 1 and self.tools:
            tool_name = self.tools[0].name
            return AIMessage(
                content="",
                tool_calls=[{
                    "name": tool_name,
                    "args": {"query": "test query"},
                    "id": "call_123"
                }]
            )
        
        # On subsequent calls, return the final response
        return AIMessage(content="Final response after tool execution")

def main():
    brain_dir = os.path.expanduser("~/.gemini/antigravity/scratch/elite-system/brain")
    os.makedirs(brain_dir, exist_ok=True)
    os.makedirs(os.path.join(brain_dir, "skills"), exist_ok=True)
    
    # Create a dummy skill to load
    skill_path = os.path.join(brain_dir, "skills", "dummy_skill", "SKILL.md")
    os.makedirs(os.path.dirname(skill_path), exist_ok=True)
    with open(skill_path, "w") as f:
        f.write("---\nname: dummy_test_skill\ndescription: A test skill\n---\nTest Instructions\n")
    
    config = ConfigLoader(brain_dir)
    llm = MockLLMWithTools()
    
    file_store = FileStore(brain_dir)
    vector_store = HybridGraphStore(brain_dir=brain_dir)
    state_store = StateStore(os.path.join(brain_dir, "state.db"))
    
    # We need to mock SkillExecutor's internal LLM as well
    class MockInnerLLM:
        def invoke(self, prompt):
            return AIMessage(content="Mock tool execution output")
            
    skill_executor = SkillExecutor(MockInnerLLM())
    soul_parser = SoulParser(brain_dir)
    registry = SkillRegistry(brain_dir, skill_executor)
    registry.load_all()
    
    dependencies = {
        "soul": soul_parser,
        "preflight": PreflightChecklist(soul_parser),
        "memory": MemoryManager(brain_dir, vector_store),
        "retrieval": MemoryRetrieval(vector_store),
        "skills": registry,
        "reasoning": EliteReasoningFramework(),
        "llm": llm,
        "config": config,
        "file_store": file_store,
        "state_store": state_store
    }
    
    graph = build_app_graph(dependencies)
    app = graph.compile()
    
    print("Testing graph tool calling invocation...")
    input_text = "Run the dummy skill."
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
    
    final_state = app.invoke(state)
    
    print("Messages in final state:")
    for m in final_state["messages"]:
        if isinstance(m, HumanMessage):
            print(f"Human: {m.content}")
        elif isinstance(m, AIMessage):
            if m.tool_calls:
                print(f"AI requested tool: {m.tool_calls[0]['name']}")
            else:
                print(f"AI: {m.content}")
        elif isinstance(m, ToolMessage):
            print(f"Tool Result: {m.content}")
            
    assert llm.call_count == 2, "LLM should have been called twice (once for tool call, once for final response)"
    print("Stress test PASSED: Graph successfully executes ToolNode loop.")
    
    # Cleanup
    os.remove(skill_path)
    os.rmdir(os.path.dirname(skill_path))

if __name__ == "__main__":
    main()
