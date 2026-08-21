"""
Selection-Inference Framework - Creswell et al. 2022 (ICLR 2023)

Implements alternating Selection and Inference modules for interpretable,
causal reasoning.

Research: "Selection-Inference: Exploiting Large Language Models for 
Interpretable Logical Reasoning" (ICLR 2023)
Results: +100% improvement over vanilla baseline, 7B outperforms 280B
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ReasoningStep:
    """A single reasoning step in Selection-Inference."""
    step_num: int
    selection: List[str]  # Selected facts
    inference: str  # Inferred fact
    reasoning: str = ""  # Explanation


class Selector:
    """Selects relevant facts from context for inference."""
    
    def __init__(self, llm_executor):
        self.llm = llm_executor
    
    def select(self, context: List[str], question: str, 
               previous_inferences: List[str] = None) -> List[str]:
        """
        Select relevant facts from context.
        
        Args:
            context: List of facts in context
            question: Question to answer
            previous_inferences: Previously inferred facts
            
        Returns:
            List of selected facts
        """
        # Build context text
        context_text = "\n".join([f"{i+1}. {fact}" for i, fact in enumerate(context)])
        
        # Add previous inferences to context
        if previous_inferences:
            context_text += "\n\nPREVIOUS INFERENCES:\n"
            context_text += "\n".join([f"- {inf}" for inf in previous_inferences])
        
        prompt = f"""You are a fact selector. Your task is to select the most relevant facts for answering a question.

QUESTION:
{question}

AVAILABLE FACTS:
{context_text}

Select the 1-3 most relevant facts for answering the question. Only select facts that are:
1. Directly relevant to the question
2. Sufficient to make a logical inference
3. Not redundant with each other

Respond with ONLY the selected facts (one per line), no additional text:
"""
        
        # Call LLM
        response = self.llm.generate(prompt)
        
        # Parse response (extract lines)
        selected = []
        for line in response.strip().split("\n"):
            line = line.strip()
            # Remove numbering if present
            if line and (line[0].isdigit() or line.startswith("-")):
                # Remove leading numbers/dashes
                parts = line.split(".", 1)
                if len(parts) > 1:
                    line = parts[1].strip()
                else:
                    line = line.lstrip("- ").strip()
            
            if line:
                selected.append(line)
        
        return selected


class Inferrer:
    """Infers new facts from selected facts."""
    
    def __init__(self, llm_executor):
        self.llm = llm_executor
    
    def infer(self, selection: List[str], question: str) -> str:
        """
        Infer a new fact from selected facts.
        
        Args:
            selection: Selected facts
            question: Question to answer
            
        Returns:
            Inferred fact
        """
        # Build selection text
        selection_text = "\n".join([f"- {fact}" for fact in selection])
        
        prompt = f"""You are a logical inferrer. Your task is to infer a new fact from selected facts.

SELECTED FACTS:
{selection_text}

Based ONLY on these facts, infer ONE new fact that logically follows.

Rules:
1. Only use information from the selected facts
2. Make a logical deduction, not a guess
3. Do not introduce new information
4. Make only ONE inference

Respond with ONLY the inferred fact (one sentence), no additional text:
"""
        
        # Call LLM
        response = self.llm.generate(prompt)
        
        # Return first line only
        inference = response.strip().split("\n")[0].strip()
        
        return inference


class SelectionInferenceFramework:
    """
    Main Selection-Inference framework.
    
    Implements alternating Selection and Inference modules.
    """
    
    def __init__(self, llm_executor, num_steps: int = 5):
        """
        Initialize Selection-Inference framework.
        
        Args:
            llm_executor: LLM executor for generating responses
            num_steps: Number of selection-inference steps
        """
        self.selector = Selector(llm_executor)
        self.inferrer = Inferrer(llm_executor)
        self.num_steps = num_steps
    
    def reason(self, context: List[str], question: str) -> Dict[str, Any]:
        """
        Perform selection-inference reasoning.
        
        Args:
            context: List of facts in context
            question: Question to answer
            
        Returns:
            Dictionary with final answer and reasoning steps
        """
        current_context = context.copy()
        previous_inferences = []
        reasoning_steps = []
        
        for step_num in range(self.num_steps):
            # Selection: Choose relevant facts
            selection = self.selector.select(
                current_context, 
                question, 
                previous_inferences
            )
            
            # If no facts selected, stop
            if not selection:
                break
            
            # Inference: Derive new fact
            inference = self.inferrer.infer(selection, question)
            
            # Record reasoning step
            step = ReasoningStep(
                step_num=step_num + 1,
                selection=selection,
                inference=inference,
                reasoning=f"Selected {len(selection)} facts and inferred: {inference}"
            )
            reasoning_steps.append(step)
            
            # Add inference to context for next iteration
            current_context.append(inference)
            previous_inferences.append(inference)
        
        # Final answer is the last inference
        final_answer = previous_inferences[-1] if previous_inferences else "Unable to determine answer"
        
        return {
            "answer": final_answer,
            "reasoning_steps": [
                {
                    "step": step.step_num,
                    "selection": step.selection,
                    "inference": step.inference,
                    "reasoning": step.reasoning
                }
                for step in reasoning_steps
            ],
            "num_steps": len(reasoning_steps),
            "context_size": len(context),
            "final_context_size": len(current_context)
        }
    
    def reason_with_trace(self, context: List[str], question: str) -> str:
        """
        Perform reasoning and return formatted trace.
        
        Args:
            context: List of facts in context
            question: Question to answer
            
        Returns:
            Formatted reasoning trace
        """
        result = self.reason(context, question)
        
        # Build trace
        trace = f"QUESTION: {question}\n\n"
        trace += "REASONING TRACE:\n"
        trace += "=" * 60 + "\n\n"
        
        for step in result["reasoning_steps"]:
            trace += f"Step {step['step']}:\n"
            trace += f"  Selection:\n"
            for fact in step['selection']:
                trace += f"    - {fact}\n"
            trace += f"  Inference: {step['inference']}\n"
            trace += "\n"
        
        trace += "=" * 60 + "\n"
        trace += f"FINAL ANSWER: {result['answer']}\n"
        
        return trace
