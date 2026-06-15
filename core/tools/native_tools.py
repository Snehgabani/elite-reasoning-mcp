import logging
import subprocess
from pathlib import Path
from typing import Any, List

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

class NativeTools:
    def __init__(self, workspace_dir: str, auto_approve: bool = False):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.auto_approve = auto_approve
        # List of dangerous commands that bypass auto-approve
        self.critical_commands = [
            "rm", "mv", "sudo", "npm install", "pip install",
            "apt", "brew install", "chown", "chmod", "git push",
            "docker rm", "docker kill"
        ]

    def _is_safe_path(self, path: str) -> bool:
        """Ensure the path is within the workspace directory to prevent traversal attacks."""
        try:
            target_path = Path(path).resolve()
            return self.workspace_dir in target_path.parents or target_path == self.workspace_dir
        except Exception:
            return False

    def get_tools(self) -> List[Any]:

        @tool
        def read_host_file(filepath: str) -> str:
            """Read the contents of a file in the workspace."""
            if not self._is_safe_path(filepath):
                return f"Error: Path {filepath} is outside the allowed workspace {self.workspace_dir}"
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                return f"Failed to read file: {e}"

        @tool
        def write_host_file(filepath: str, content: str) -> str:
            """Write content to a file in the workspace."""
            if not self._is_safe_path(filepath):
                return f"Error: Path {filepath} is outside the allowed workspace {self.workspace_dir}"
            try:
                target = Path(filepath)
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"Successfully wrote to {filepath}"
            except Exception as e:
                return f"Failed to write file: {e}"

        @tool
        def run_terminal_command(command: str) -> str:
            """Execute a terminal command. The system will automatically intercept critical commands for user approval."""
            cmd_lower = command.strip().lower()
            is_critical = any(cmd_lower.startswith(cmd) for cmd in self.critical_commands)

            requires_approval = True
            if self.auto_approve and not is_critical:
                requires_approval = False

            if requires_approval:
                reason = "Critical command detected" if is_critical else "Auto-approve is disabled"
                print(f"\n[GOVERNANCE INTERCEPT: {reason}]")
                print(f"The agent wants to execute: `{command}`")

                # We use input() to block execution and prompt the user in the CLI.
                try:
                    response = input("Approve execution? (y/N): ").strip().lower()
                    if response not in ['y', 'yes']:
                        return "Command execution rejected by user."
                except EOFError:
                    return "Command execution rejected (EOF)."

            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=str(self.workspace_dir) # Jail terminal execution default dir
                )
                output = result.stdout
                if result.stderr:
                    output += f"\nSTDERR:\n{result.stderr}"
                return output if output else "Command executed successfully with no output."
            except subprocess.TimeoutExpired:
                return "Command execution timed out after 120 seconds."
            except Exception as e:
                return f"Failed to execute command: {e}"

        return [read_host_file, write_host_file, run_terminal_command]
