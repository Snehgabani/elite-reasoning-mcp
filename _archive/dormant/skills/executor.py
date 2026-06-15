import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SkillExecutor:
    """
    Executes a skill by combining its instructions with the user's query
    and passing it to an LLM, or running attached scripts if available.
    """
    def __init__(self, llm_client: Any):
        # We inject the LLM client (e.g., ChatAnthropic or ChatGoogleGenAI)
        self.llm = llm_client

    def execute(self, skill_name: str, instructions: str, query: str) -> str:
        """
        Execute the skill.
        In a full implementation, this uses the LLM to process the query
        according to the strict guidelines in the skill instructions.
        """
        logger.info(f"Executing skill: {skill_name}")
        
        prompt = f"""
You are executing the skill: {skill_name}.
Follow these instructions EXACTLY:

<SKILL_INSTRUCTIONS>
{instructions}
</SKILL_INSTRUCTIONS>

User Query: {query}
"""
        
        # Invoke the LLM with the skill prompt
        response = self.llm.invoke(prompt)
        return response.content
