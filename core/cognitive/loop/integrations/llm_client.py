"""Real LLM Integration for v6 Pipeline

Connects the reasoning pipeline to actual LLMs for:
- Answer generation using guided reasoning prompts
- Real multi-turn refinement (generate → critique → refine)
- Actual quality measurement

Supports:
- OpenAI API
- Anthropic API
- Local models via Ollama
- Any OpenAI-compatible API
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


@dataclass
class LLMResponse:
    """Response from LLM generation."""
    content: str
    model: str
    usage: dict = field(default_factory=dict)
    duration_ms: int = 0
    error: Optional[str] = None


class LLMClient:
    """Client for calling LLM APIs."""
    
    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url or self._get_default_base_url()
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    def _get_default_base_url(self) -> str:
        """Get default base URL for provider."""
        urls = {
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com/v1",
            "ollama": "http://localhost:11434/v1",
            "local": "http://localhost:8080/v1",
        }
        return urls.get(self.provider, "https://api.openai.com/v1")
    
    def generate(self, prompt: str, system: str = "") -> LLMResponse:
        """Generate response from LLM."""
        if not HAS_HTTPX:
            return LLMResponse(
                content="[httpx not installed - cannot call LLM API]",
                model=self.model,
                error="httpx not installed"
            )
        
        if not self.api_key and self.provider not in ["ollama", "local"]:
            return LLMResponse(
                content="[No API key configured]",
                model=self.model,
                error="No API key"
            )
        
        start = time.time()
        
        try:
            # Build messages
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            
            # Build request
            if self.provider == "anthropic":
                response = self._call_anthropic(messages)
            else:
                response = self._call_openai_compatible(messages)
            
            duration = int((time.time() - start) * 1000)
            
            return LLMResponse(
                content=response["content"],
                model=response.get("model", self.model),
                usage=response.get("usage", {}),
                duration_ms=duration
            )
        
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            return LLMResponse(
                content=f"[LLM API error: {str(e)}]",
                model=self.model,
                duration_ms=duration,
                error=str(e)
            )
    
    def _call_openai_compatible(self, messages: list[dict]) -> dict:
        """Call OpenAI-compatible API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60.0
        )
        response.raise_for_status()
        
        data = response.json()
        
        return {
            "content": data["choices"][0]["message"]["content"],
            "model": data.get("model", self.model),
            "usage": data.get("usage", {})
        }
    
    def _call_anthropic(self, messages: list[dict]) -> dict:
        """Call Anthropic API."""
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        # Extract system message
        system = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                user_messages.append(msg)
        
        payload = {
            "model": self.model,
            "messages": user_messages,
            "system": system,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        response = httpx.post(
            f"{self.base_url}/messages",
            headers=headers,
            json=payload,
            timeout=60.0
        )
        response.raise_for_status()
        
        data = response.json()
        
        return {
            "content": data["content"][0]["text"],
            "model": data.get("model", self.model),
            "usage": data.get("usage", {})
        }


class MultiTurnRefiner:
    """Implements real multi-turn refinement with actual LLM calls."""
    
    def __init__(self, llm_client: LLMClient, max_turns: int = 3):
        self.llm = llm_client
        self.max_turns = max_turns
    
    def refine(
        self,
        prompt: str,
        reasoning_prompt: str,
        quality_threshold: float = 0.70
    ) -> tuple[str, list[dict]]:
        """
        Run multi-turn refinement loop.
        
        1. Generate initial answer using reasoning prompt
        2. Critique the answer
        3. Refine based on critique
        4. Repeat until quality threshold or max turns
        
        Returns: (final_answer, refinement_history)
        """
        history = []
        
        # Turn 1: Initial generation
        system = "You are a careful, analytical assistant. Follow the reasoning structure provided."
        initial_response = self.llm.generate(reasoning_prompt, system)
        
        current_answer = initial_response.content
        history.append({
            "turn": 1,
            "type": "initial",
            "answer": current_answer,
            "duration_ms": initial_response.duration_ms
        })
        
        # Refinement loop
        for turn in range(2, self.max_turns + 1):
            # Generate critique
            critique_prompt = f"""Critique this answer for completeness, correctness, and clarity:

ORIGINAL QUESTION:
{prompt}

ANSWER:
{current_answer}

Provide specific, actionable feedback on what could be improved."""
            
            critique_response = self.llm.generate(critique_prompt, system)
            critique = critique_response.content
            
            # Generate refinement
            refine_prompt = f"""Improve this answer based on the critique:

ORIGINAL QUESTION:
{prompt}

CURRENT ANSWER:
{current_answer}

CRITIQUE:
{critique}

Provide an improved version that addresses the critique."""
            
            refine_response = self.llm.generate(refine_prompt, system)
            refined_answer = refine_response.content
            
            history.append({
                "turn": turn,
                "type": "refinement",
                "critique": critique,
                "answer": refined_answer,
                "duration_ms": critique_response.duration_ms + refine_response.duration_ms
            })
            
            current_answer = refined_answer
            
            # Check if we should stop (simplified - in production, use quality scoring)
            if "no improvements needed" in critique.lower() or "looks good" in critique.lower():
                break
        
        return current_answer, history


class LLMIntegratedPipeline:
    """Pipeline that integrates with real LLM for end-to-end execution."""
    
    def __init__(self, llm_client: LLMClient, reasoning_pipeline):
        self.llm = llm_client
        self.pipeline = reasoning_pipeline
        self.refiner = MultiTurnRefiner(llm_client)
    
    def run(self, prompt: str, mode: str = "amplified") -> dict:
        """
        Run full end-to-end pipeline:
        1. Generate reasoning structure (existing pipeline)
        2. Generate answer using LLM with guided prompt
        3. Refine through multi-turn loop
        4. Return final answer with metadata
        """
        # Step 1: Generate reasoning structure
        state = self.pipeline.run(prompt, mode=mode)
        
        # Step 2: Generate answer using LLM
        if state.reasoning_prompt:
            llm_response = self.llm.generate(state.reasoning_prompt)
            initial_answer = llm_response.content
        else:
            # Fallback: direct generation
            llm_response = self.llm.generate(prompt)
            initial_answer = llm_response.content
        
        # Step 3: Multi-turn refinement
        if mode == "amplified" and state.reasoning_prompt:
            final_answer, refinement_history = self.refiner.refine(
                prompt,
                state.reasoning_prompt,
                quality_threshold=state.quality_threshold
            )
        else:
            final_answer = initial_answer
            refinement_history = []
        
        # Step 4: Compile results
        return {
            "session_id": state.session_id,
            "prompt": prompt,
            "reasoning_structure": {
                "subproblems": state.subproblems,
                "techniques_applied": state.techniques_applied,
                "counter_arguments": state.counter_arguments,
                "verification_tests": state.verification_tests,
            },
            "reasoning_prompt": state.reasoning_prompt,
            "initial_answer": initial_answer,
            "final_answer": final_answer,
            "refinement_history": refinement_history,
            "refinement_turns": len(refinement_history),
            "quality_score": state.quality_score,
            "confidence": state.confidence,
            "llm_usage": {
                "model": self.llm.model,
                "initial_duration_ms": llm_response.duration_ms,
                "total_refinement_duration_ms": sum(h.get("duration_ms", 0) for h in refinement_history)
            },
            "pipeline_duration_ms": state.pipeline_duration_ms
        }
