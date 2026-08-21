# src/skills.py
# After every successful task, this mines the trace for reusable patterns.
# This is what makes the system get smarter over time.

import json
import os
from datetime import datetime

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

load_dotenv()

_LLM_BASE = os.getenv("ELITE_LLM_BASE", "http://127.0.0.1:4096/v1")
_LLM_KEY = os.getenv("ELITE_LLM_KEY", "local-proxy")
_LLM_MODEL = os.getenv("ELITE_LLM_MODEL", "opencode-zen/deepseek-v4-flash-free")

SKILL_MINER_LLM = ChatOpenAI(  # via llm-proxy:4096 -> opencode-zen free
    model=_LLM_MODEL,
    temperature=0.0,
    base_url=_LLM_BASE,
    api_key=_LLM_KEY,
    max_tokens=int(os.getenv("ELITE_LLM_MAX_TOKENS", "8192")),
)


def mine_skill_from_trace(task: str, reasoning_state: dict, outcome: str) -> bool:
    """
    Analyzes a completed reasoning trace.
    If a reusable pattern is found, saves it as a skill file.
    Returns True if a skill was saved, False otherwise.

    Only saves skills from SUCCESSFUL traces (outcome == "success").
    """

    if outcome != "success":
        return False

    system_prompt = """
You are a Skill Extractor.
Analyze this reasoning trace and determine if it contains a REUSABLE pattern
that would help solve similar problems faster in the future.

A good skill:
- Applies to a class of problems, not just this one
- Has clear trigger conditions
- Has a repeatable reasoning structure

If a reusable skill exists, return JSON:
{
  "worth_saving": true,
  "skill_name": "short-hyphenated-name",
  "trigger": "when to use this skill",
  "node_type": "PLAN|REASON|REFLECT",
  "reasoning_template": "the reusable reasoning pattern as markdown"
}

If NOT worth saving, return:
{"worth_saving": false}
"""

    trace_summary = f"""
TASK: {task}
TASK TYPE: {reasoning_state.get("task_type", "general")}
PLAN: {reasoning_state.get("plan_nodes", [])}
REASONING STEPS: {reasoning_state.get("reason_nodes", [])}
BACKTRACK COUNT: {reasoning_state.get("backtrack_count", 0)}
CONCLUDE: {reasoning_state.get("conclude_node", "")}
"""

    response = SKILL_MINER_LLM.invoke([SystemMessage(content=system_prompt), HumanMessage(content=trace_summary)])

    try:
        data = json.loads(response.content)

        if not data.get("worth_saving", False):
            return False

        # Write the skill file
        skill_name = data.get("skill_name", "unnamed-skill")
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        skill_path = os.path.join(project_root, ".ai", "skills", f"{skill_name}.md")
        os.makedirs(os.path.dirname(skill_path), exist_ok=True)

        skill_content = f"""# skill: {skill_name}
## trigger: {data.get("trigger", "")}
## node_type: {data.get("node_type", "REASON")}
## created: {datetime.now().isoformat()}
## mined_from_task: {task[:100]}

## reasoning_template:
{data.get("reasoning_template", "")}
"""

        with open(skill_path, "w") as f:
            f.write(skill_content)

        print(f"✅ New skill saved: {skill_path}")
        return True

    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️ Skill mining failed: {e}")
        return False
