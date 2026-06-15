import pytest
from pathlib import Path
from core.skills.registry import SkillRegistry

class DummyExecutor:
    def execute(self, name, instructions, query):
        pass

def test_registry_multiple_paths(tmp_path):
    brain_dir = tmp_path / "brain"
    brain_skills = brain_dir / "skills"
    brain_skills.mkdir(parents=True)
    
    # Create local skill
    local_skill = brain_skills / "local"
    local_skill.mkdir()
    (local_skill / "SKILL.md").write_text("---\nname: local-skill\n---\ninstructions", encoding="utf-8")
    
    # Create plugin dir
    plugin_dir = tmp_path / "global_plugins"
    plugin_dir.mkdir()
    plugin_skill = plugin_dir / "global"
    plugin_skill.mkdir()
    (plugin_skill / "SKILL.md").write_text("---\nname: global-skill\n---\ninstructions", encoding="utf-8")
    
    registry = SkillRegistry(str(brain_dir), DummyExecutor(), [str(plugin_dir)])
    registry.load_all()
    
    tools = registry.get_tools()
    names = [t.name for t in tools]
    
    assert "local_skill" in names
    assert "global_skill" in names
    assert len(tools) == 2
