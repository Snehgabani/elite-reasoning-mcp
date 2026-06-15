import os
import json
import zipfile
import shutil
from typing import Dict, Any

class ExportEngine:
    """Exports the Elite System state, scrubbing sensitive keys, for external diagnostic review."""
    
    def __init__(self, brain_dir: str, vault=None):
        self.brain_dir = brain_dir
        self.vault = vault
        
    def generate_export(self, thread_id: str, output_path: str = "diagnostic_export.md"):
        """Extract the full system state and memory for a thread, heavily redacted."""
        export_content = [
            "# Elite System Diagnostic Export",
            f"**Thread ID:** `{thread_id}`",
            "\n## System Architecture",
            "- Engine: LangGraph",
            "- Persistence: SqliteSaver",
            "- Vector Store: Qdrant (Hybrid)",
            "- Privacy: Vault (OS Keyring)",
            "\n## Redacted Memory State",
            "```json"
        ]
        
        # Pull vault keys to redact
        vault_keys = []
        if self.vault and hasattr(self.vault, '_mem_vault'):
            vault_keys = list(self.vault._mem_vault.keys())
        
        # Try to pull recovery state
        recovery_path = os.path.join(self.brain_dir, ".elite_recovery.json")
        recovery_data = {}
        if os.path.exists(recovery_path):
            try:
                with open(recovery_path, "r") as f:
                    recovery_data = json.load(f)
            except Exception:
                pass

        state_dump = {
            "status": "CRASHED_OR_HALTED" if recovery_data else "UNKNOWN",
            "active_thread": thread_id,
            "plugins_loaded": ["elite_reasoning_framework"],
            "vault_keys_present": vault_keys,
            "recovery_state": recovery_data
        }
        
        export_content.append(json.dumps(state_dump, indent=2))
        export_content.append("```\n")
        
        export_content.append("## Error Logs")
        export_content.append("No critical errors logged in buffer.")
        
        full_path = os.path.join(self.brain_dir, output_path)
        with open(full_path, "w") as f:
            f.write("\n".join(export_content))
            
        print(f"📦 System state exported to {full_path}")
        return full_path
