import pytest
from pathlib import Path
from core.skills.auto_creator import WorkflowSkillCreator

def test_workflow_skill_creator(tmp_path):
    brain_dir = tmp_path / "brain"
    creator = WorkflowSkillCreator(str(brain_dir))
    
    # Check quarantine dir was created
    quarantine_dir = brain_dir / "skills" / ".quarantine"
    assert quarantine_dir.exists()
    assert quarantine_dir.is_dir()
    
    # Test creation of skill
    skill_file = creator.create_skill(
        name="Test Workflow",
        description="A test workflow description"
    )
    
    assert skill_file.exists()
    assert "test-workflow" in skill_file.parent.name
    
    content = skill_file.read_text(encoding="utf-8")
    assert "name: Test Workflow" in content
    assert "description: A test workflow description" in content
    assert "triggers:" in content

def test_workflow_skill_creator_tools(tmp_path):
    brain_dir = tmp_path / "brain"
    creator = WorkflowSkillCreator(str(brain_dir))
    
    tools = creator.get_tools()
    assert len(tools) == 1
    
    tool = tools[0]
    assert tool.name == "create_workflow_skill"
    
    # Invoke the tool
    result = tool.invoke({"name": "Another Workflow", "description": "Another test description"})
    assert "Successfully created new skill 'Another Workflow'" in result
    assert "quarantine" in result
