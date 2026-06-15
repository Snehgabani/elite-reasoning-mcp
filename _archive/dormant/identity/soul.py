import re
from pathlib import Path
from typing import Dict, List, Any
from core.persistence.file_store import FileStore

class SoulParser:
    """
    Loads and parses SOUL.md into structured identity constraints.
    Injects identity into LLM system prompts and detects behavioral drift.
    """
    def __init__(self, brain_dir: str):
        self.brain_dir = Path(brain_dir)
        self.file_store = FileStore(brain_dir)
        self.raw_content = ""
        self.identity_dict = {
            "hard_constraints": [],
            "personality_rules": [],
            "preflight_classes": [],
            "fmea_triggers": []
        }
        self.reload()

    def reload(self):
        """Read and parse SOUL.md."""
        content = self.file_store.read("SOUL.md")
        if not content:
            raise FileNotFoundError("SOUL.md not found in brain directory")
        self.raw_content = content
        self._parse()

    def _parse(self):
        """Extract structured rules from SOUL.md."""
        # Simple heuristic parsing (in reality, could use LLM extraction or strict markdown structure)
        
        # Extract Hard Constraints (usually numbered or marked with [HC])
        hc_pattern = re.compile(r'(?:HC\d+:?|[-*] \[HC\]|[-*] \*\*(?:Hard Constraint|Constraint)\*\*:?) (.*)')
        self.identity_dict["hard_constraints"] = hc_pattern.findall(self.raw_content)
        
        # Identify FMEA triggers
        fmea_pattern = re.compile(r'MUST-FMEA:? (.*)')
        self.identity_dict["fmea_triggers"] = fmea_pattern.findall(self.raw_content)

    def get_system_prompt_injection(self) -> str:
        """Get the full SOUL.md text to inject into the system prompt."""
        # System architecture injects the full SOUL.md to ensure strict behavioral compliance
        return f"""<SOUL>
{self.raw_content}
</SOUL>
"""

    def check_drift(self, recent_outputs: List[str]) -> List[str]:
        """
        Check recent outputs against identity constraints.
        Returns a list of warnings if drift is detected.
        """
        warnings = []
        for output in recent_outputs:
            if "happy to help" in output.lower():
                warnings.append("Sycophancy detected: 'happy to help'")
            if output.count("—") > 3:
                warnings.append("Stylistic drift: Excessive use of em-dashes")
        return warnings
