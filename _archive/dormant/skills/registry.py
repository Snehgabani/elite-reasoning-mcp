import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

class SkillMeta(BaseModel):
    name: str
    description: str
    triggers: List[str] = []

class DynamicSkillTool(BaseTool):
    """
    A LangChain BaseTool wrapper around a System SKILL.md.
    """
    name: str
    description: str
    instructions: str
    executor: Any # Will be SkillExecutor
    
    def _run(self, query: str) -> str:
        """Execute the skill."""
        return self.executor.execute(self.name, self.instructions, query)
        
class SkillRegistry:
    """
    Scans the skills directory (and any additional plugin paths), 
    parses YAML frontmatter in SKILL.md files,
    and dynamically registers LangGraph ToolNodes.
    """
    def __init__(self, brain_dir: str, executor: Any, plugin_paths: List[str] = None):
        self.skills_dir = Path(brain_dir) / "skills"
        self.plugin_paths = [Path(p) for p in (plugin_paths or [])]
        self.executor = executor
        self.skills: Dict[str, DynamicSkillTool] = {}
        
    def load_all(self):
        """Scan and load all skills from the filesystem."""
        paths_to_scan = [self.skills_dir] + self.plugin_paths
        
        for base_path in paths_to_scan:
            if not base_path.exists():
                continue
                
            for skill_file in base_path.rglob("SKILL.md"):
                self._load_skill(skill_file)
            
    def _load_skill(self, filepath: Path):
        """Parse a single SKILL.md file."""
        content = filepath.read_text(encoding="utf-8")
        
        # Parse frontmatter
        if not content.startswith("---\n"):
            return
            
        parts = content.split("---\n", 2)
        if len(parts) < 3:
            return
            
        try:
            frontmatter = yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            logger.warning(f"Skipping skill {filepath.parent.name} due to invalid YAML frontmatter: {e}")
            return
            
        instructions = parts[2]
        
        meta = SkillMeta(
            name=frontmatter.get("name", filepath.parent.name),
            description=frontmatter.get("description", "A dynamic skill"),
            triggers=frontmatter.get("triggers", [])
        )
        
        skill_tool = DynamicSkillTool(
            name=meta.name.replace("-", "_"), # LangChain tools prefer underscores
            description=meta.description,
            instructions=instructions,
            executor=self.executor
        )
        
        # Ensure no accidental overwrites unless it's intended (last loaded wins, prioritizing local)
        # We can just warn on collision, or accept it. We'll accept it.
        if skill_tool.name in self.skills:
            # We don't overwrite user's local quarantine/modifications with global plugins
            # Since local skills_dir is scanned first, we should ignore if already exists?
            # Wait, local skills_dir is first in paths_to_scan, so if we want local to override global,
            # we should skip if it's already in self.skills.
            pass
        else:
            self.skills[skill_tool.name] = skill_tool

    def get_tools(self) -> List[BaseTool]:
        """Get all loaded skills as LangChain tools."""
        return list(self.skills.values())
