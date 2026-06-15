import logging
import uuid
from pathlib import Path
from typing import List, Dict, Any
from langchain_core.tools import BaseTool, tool

logger = logging.getLogger(__name__)

class WorkflowSkillCreator:
    """
    Distills recent successful workflows into reusable SKILL.md files.
    All newly generated skills are placed in a `.quarantine` folder
    to ensure human review before execution.
    """
    def __init__(self, brain_dir: str):
        self.skills_dir = Path(brain_dir) / "skills"
        self.quarantine_dir = self.skills_dir / ".quarantine"
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

    def extract_workflow(self, state_messages: List[Any], task_name: str, task_description: str) -> str:
        """
        Uses an LLM prompt internally (or locally generated logic)
        to compile a sequence of actions into a markdown instructional document.
        For demonstration/framework purposes, we simulate this output.
        """
        logger.info(f"Extracting workflow for {task_name}")
        
        # In a full implementation, we'd pass `state_messages` to the LLM to generate the instructions.
        instructions = f"""You are executing the {task_name} skill.
Goal: {task_description}

Instructions generated from recent workflow:
1. Initialize the task parameters.
2. Follow the recorded steps.
3. Validate output.
"""
        return instructions

    def create_skill(self, name: str, description: str, state_messages: List[Any] = None) -> Path:
        """
        Generates a new SKILL.md file and writes it to the `.quarantine` folder.
        """
        instructions = self.extract_workflow(state_messages or [], name, description)
        
        # Format the skill
        skill_content = f"""---
name: {name}
description: {description}
triggers:
  - {name}
---
{instructions}
"""
        
        # Create unique directory in quarantine
        skill_id = str(uuid.uuid4())[:8]
        safe_name = name.lower().replace(" ", "-").replace("_", "-")
        skill_path = self.quarantine_dir / f"{safe_name}-{skill_id}"
        skill_path.mkdir(exist_ok=True)
        
        skill_file = skill_path / "SKILL.md"
        skill_file.write_text(skill_content, encoding="utf-8")
        logger.info(f"Auto-created skill '{name}' and placed in quarantine at {skill_file}")
        
        return skill_file

    def get_tools(self) -> List[BaseTool]:
        """Returns the auto-creation tool for LangGraph."""
        
        @tool("create_workflow_skill")
        def create_workflow_skill(name: str, description: str) -> str:
            """
            Distills the recent assistant workflow into a new, reusable skill in the .quarantine folder.
            Use this when the user asks you to save the current workflow as a skill, or you identify a highly reusable pattern.
            """
            path = self.create_skill(name, description)
            return f"Successfully created new skill '{name}'. It has been placed in quarantine at {path} pending human review."
            
        return [create_workflow_skill]

