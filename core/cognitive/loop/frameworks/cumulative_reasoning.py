"""
Cumulative Reasoning Framework - Zhang et al. 2023 (ICLR 2024)

Implements the Proposer-Verifier-Reporter architecture that builds
a Directed Acyclic Graph (DAG) of verified propositions.

Research: "Cumulative Reasoning with Large Language Models" (ICLR 2024)
Results: +24% on Game of 24, +43% on MATH Level 5, 98% on FOLIO
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import uuid
from enum import Enum


class PropositionStatus(Enum):
    PROPOSED = "proposed"
    VERIFIED = "verified"
    REJECTED = "rejected"


@dataclass
class Proposition:
    """A single proposition in the reasoning DAG."""
    id: str
    content: str
    status: PropositionStatus = PropositionStatus.PROPOSED
    parents: List[str] = field(default_factory=list)  # Parent proposition IDs
    children: List[str] = field(default_factory=list)  # Child proposition IDs
    confidence: float = 0.0
    verification_reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class DAG:
    """Directed Acyclic Graph for storing verified propositions."""
    
    def __init__(self):
        self.nodes: Dict[str, Proposition] = {}
        self.roots: List[str] = []  # Propositions with no parents
    
    def add_proposition(self, proposition: Proposition) -> None:
        """Add a proposition to the DAG."""
        self.nodes[proposition.id] = proposition
        
        # Update parent-child relationships
        for parent_id in proposition.parents:
            if parent_id in self.nodes:
                self.nodes[parent_id].children.append(proposition.id)
        
        # If no parents, it's a root
        if not proposition.parents:
            self.roots.append(proposition.id)
    
    def get_proposition(self, prop_id: str) -> Optional[Proposition]:
        """Get a proposition by ID."""
        return self.nodes.get(prop_id)
    
    def get_verified_propositions(self) -> List[Proposition]:
        """Get all verified propositions."""
        return [p for p in self.nodes.values() if p.status == PropositionStatus.VERIFIED]
    
    def get_reasoning_chain(self, prop_id: str) -> List[Proposition]:
        """Get the reasoning chain leading to a proposition."""
        chain = []
        visited = set()
        
        def traverse(current_id: str):
            if current_id in visited:
                return
            visited.add(current_id)
            
            prop = self.get_proposition(current_id)
            if prop:
                # First traverse parents
                for parent_id in prop.parents:
                    traverse(parent_id)
                # Then add current
                chain.append(prop)
        
        traverse(prop_id)
        return chain
    
    def get_all_paths(self) -> List[List[Proposition]]:
        """Get all paths from roots to leaves."""
        paths = []
        
        def dfs(current_id: str, current_path: List[Proposition]):
            prop = self.get_proposition(current_id)
            if not prop:
                return
            
            current_path = current_path + [prop]
            
            # If leaf node (no children), add path
            if not prop.children:
                paths.append(current_path)
            else:
                # Continue DFS
                for child_id in prop.children:
                    dfs(child_id, current_path)
        
        # Start from all roots
        for root_id in self.roots:
            dfs(root_id, [])
        
        return paths
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert DAG to dictionary representation."""
        return {
            "nodes": {k: v.__dict__ for k, v in self.nodes.items()},
            "roots": self.roots,
            "num_propositions": len(self.nodes),
            "num_verified": len(self.get_verified_propositions())
        }


class Proposer:
    """Proposes potential reasoning steps based on current context."""
    
    def __init__(self, llm_executor):
        self.llm = llm_executor
    
    def propose(self, dag: DAG, problem: str, context: str = "") -> List[Proposition]:
        """
        Propose new reasoning steps based on current DAG state.
        
        Args:
            dag: Current reasoning DAG
            problem: Original problem to solve
            context: Additional context
            
        Returns:
            List of proposed propositions
        """
        # Build prompt for proposer
        verified_props = dag.get_verified_propositions()
        verified_text = "\n".join([f"- {p.content}" for p in verified_props])
        context_block = f"ADDITIONAL CONTEXT:\n{context}" if context else ""

        prompt = f"""You are a reasoning proposer. Your task is to propose the next logical step in solving a problem.

PROBLEM:
{problem}

CURRENT REASONING STATE:
{verified_text if verified_text else "No propositions yet."}

{context_block}

Based on the current reasoning state, propose 1-3 next logical steps. Each proposition should:
1. Build on previous propositions (if any)
2. Move closer to solving the problem
3. Be verifiable

For each proposition, provide:
- content: The proposition statement
- confidence: Your confidence (0.0-1.0)
- reasoning: Why this is the next logical step

Respond in JSON format:
{{
  "propositions": [
    {{
      "content": "...",
      "confidence": 0.8,
      "reasoning": "..."
    }}
  ]
}}
"""
        
        # Call LLM
        response = self.llm.generate(prompt)
        
        # Parse response
        try:
            import json
            data = json.loads(response)
            propositions = []
            
            for prop_data in data.get("propositions", []):
                prop = Proposition(
                    id=str(uuid.uuid4()),
                    content=prop_data["content"],
                    confidence=prop_data.get("confidence", 0.5),
                    metadata={"reasoning": prop_data.get("reasoning", "")}
                )
                propositions.append(prop)
            
            return propositions
        except Exception as e:
            # Fallback: single proposition
            return [Proposition(
                id=str(uuid.uuid4()),
                content=response,
                confidence=0.5,
                metadata={"error": str(e)}
            )]


class Verifier:
    """Verifies proposed reasoning steps."""
    
    def __init__(self, llm_executor, symbolic_verifier=None):
        self.llm = llm_executor
        self.symbolic_verifier = symbolic_verifier  # Optional symbolic verifier
    
    def verify(self, proposition: Proposition, dag: DAG, problem: str) -> bool:
        """
        Verify if a proposition is logically valid.
        
        Args:
            proposition: Proposition to verify
            dag: Current reasoning DAG
            problem: Original problem
            
        Returns:
            True if verified, False otherwise
        """
        # Try symbolic verifier first (if available)
        if self.symbolic_verifier:
            try:
                return self.symbolic_verifier.verify(proposition, dag)
            except Exception:
                pass  # Fall back to LLM verification
        
        # Build prompt for verifier
        verified_props = dag.get_verified_propositions()
        verified_text = "\n".join([f"- {p.content}" for p in verified_props])
        
        # Get reasoning chain for this proposition
        chain = dag.get_reasoning_chain(proposition.id)
        chain_text = "\n".join([f"Step {i+1}: {p.content}" for i, p in enumerate(chain)])
        
        prompt = f"""You are a reasoning verifier. Your task is to verify if a proposition is logically valid.

PROBLEM:
{problem}

REASONING CHAIN SO FAR:
{chain_text if chain_text else "No previous steps."}

PROPOSITION TO VERIFY:
{proposition.content}

Verify if this proposition:
1. Logically follows from previous steps (if any)
2. Is factually correct
3. Moves toward solving the problem
4. Is not redundant with previous steps

Respond in JSON format:
{{
  "verified": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "Explanation of why verified or rejected"
}}
"""
        
        # Call LLM
        response = self.llm.generate(prompt)
        
        # Parse response
        try:
            import json
            data = json.loads(response)
            verified = data.get("verified", False)
            confidence = data.get("confidence", 0.5)
            reasoning = data.get("reasoning", "")
            
            # Update proposition
            proposition.status = PropositionStatus.VERIFIED if verified else PropositionStatus.REJECTED
            proposition.confidence = confidence
            proposition.verification_reason = reasoning
            
            return verified
        except Exception as e:
            # Fallback: reject
            proposition.status = PropositionStatus.REJECTED
            proposition.verification_reason = f"Verification error: {str(e)}"
            return False


class Reporter:
    """Determines when to stop and synthesizes final answer."""
    
    def __init__(self, llm_executor):
        self.llm = llm_executor
    
    def should_stop(self, dag: DAG, problem: str) -> bool:
        """
        Determine if reasoning should stop.
        
        Args:
            dag: Current reasoning DAG
            problem: Original problem
            
        Returns:
            True if should stop, False otherwise
        """
        verified_props = dag.get_verified_propositions()
        
        # If no verified propositions, continue
        if not verified_props:
            return False
        
        # Build prompt for reporter
        verified_text = "\n".join([f"- {p.content}" for p in verified_props])
        
        prompt = f"""You are a reasoning reporter. Your task is to determine if the reasoning is complete.

PROBLEM:
{problem}

VERIFIED PROPOSITIONS:
{verified_text}

Determine if the verified propositions are sufficient to answer the problem.

Consider:
1. Do the propositions fully address the problem?
2. Are there any gaps in the reasoning?
3. Is the answer clear and complete?

Respond in JSON format:
{{
  "complete": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "Explanation of why complete or incomplete"
}}
"""
        
        # Call LLM
        response = self.llm.generate(prompt)
        
        # Parse response
        try:
            import json
            data = json.loads(response)
            return data.get("complete", False)
        except Exception:
            return False
    
    def synthesize(self, dag: DAG, problem: str) -> str:
        """
        Synthesize final answer from verified propositions.
        
        Args:
            dag: Current reasoning DAG
            problem: Original problem
            
        Returns:
            Final answer string
        """
        verified_props = dag.get_verified_propositions()
        verified_text = "\n".join([f"- {p.content}" for p in verified_props])
        
        # Get all reasoning paths
        paths = dag.get_all_paths()
        paths_text = ""
        for i, path in enumerate(paths[:3]):  # Limit to 3 paths
            path_text = " → ".join([p.content for p in path])
            paths_text += f"\nPath {i+1}: {path_text}"
        
        prompt = f"""You are a reasoning reporter. Synthesize a final answer from the verified reasoning.

PROBLEM:
{problem}

VERIFIED PROPOSITIONS:
{verified_text}

REASONING PATHS:
{paths_text}

Based on the verified propositions and reasoning paths, provide a clear, complete answer to the problem.

Your answer should:
1. Directly address the problem
2. Be based on the verified propositions
3. Be clear and well-structured
4. Include relevant reasoning from the propositions

Provide your final answer:
"""
        
        # Call LLM
        response = self.llm.generate(prompt)
        
        return response


class CumulativeReasoningFramework:
    """
    Main Cumulative Reasoning framework.
    
    Implements the Proposer-Verifier-Reporter architecture.
    """
    
    def __init__(self, llm_executor, symbolic_verifier=None, max_iterations: int = 10):
        """
        Initialize Cumulative Reasoning framework.
        
        Args:
            llm_executor: LLM executor for generating responses
            symbolic_verifier: Optional symbolic verifier for verification
            max_iterations: Maximum number of propose-verify iterations
        """
        self.proposer = Proposer(llm_executor)
        self.verifier = Verifier(llm_executor, symbolic_verifier)
        self.reporter = Reporter(llm_executor)
        self.max_iterations = max_iterations
    
    def reason(self, problem: str, context: str = "") -> Dict[str, Any]:
        """
        Perform cumulative reasoning on a problem.
        
        Args:
            problem: Problem to solve
            context: Additional context
            
        Returns:
            Dictionary with final answer and reasoning DAG
        """
        # Initialize DAG
        dag = DAG()
        
        # Iterative propose-verify cycle
        iteration = 0
        while iteration < self.max_iterations:
            # Check if should stop
            if self.reporter.should_stop(dag, problem):
                break
            
            # Propose new propositions
            propositions = self.proposer.propose(dag, problem, context)
            
            # Verify each proposition
            for prop in propositions:
                # Add to DAG (as proposed)
                dag.add_proposition(prop)
                
                # Verify
                if self.verifier.verify(prop, dag, problem):
                    # Verified - keep in DAG
                    pass
                else:
                    # Rejected - mark as rejected
                    prop.status = PropositionStatus.REJECTED
            
            iteration += 1
        
        # Synthesize final answer
        final_answer = self.reporter.synthesize(dag, problem)
        
        return {
            "answer": final_answer,
            "dag": dag.to_dict(),
            "num_iterations": iteration,
            "num_propositions": len(dag.nodes),
            "num_verified": len(dag.get_verified_propositions())
        }
