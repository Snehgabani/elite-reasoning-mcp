"""
Per-User Profile Manager for Elite MCP.

Each user gets:
  - Their own config.json with preferences
  - Their own brain/ directory with isolated data
  - Their own skill preferences and overrides
  - Auto-registration with the team sync hub

Config lives at: ~/.elite-reasoning/config.json
Brain lives at:  ~/.elite-reasoning/brain/
"""
import os
import json
import getpass
import time
from typing import Optional


DEFAULT_CONFIG = {
    "user_id": "",
    "display_name": "",
    "ide_type": "auto",
    "sync": {
        "enabled": False,
        "hub_url": "http://localhost:8000",
        "api_key": "",
        "auto_sync_on_boot": True,
        "sync_interval_minutes": 60,
    },
    "orchestration": {
        "mode": "auto",             # "auto" | "heuristic" | "llm"
        "gemini_api_key": "",       # If blank, falls back from env
        "disabled_mcps": [],        # MCPs to exclude from orchestration
        "disabled_skills": [],      # Skills to exclude from orchestration
        "priority_mcps": [],        # MCPs to always include
        "priority_skills": [],      # Skills to always include
    },
    "quality": {
        "auto_check_anti_patterns": True,
        "auto_record_decisions": True,
        "min_quality_score": 70,
    },
    "shared_skills": [],            # Skills published to the team hub
    "created_at": "",
    "updated_at": "",
}


class UserProfile:
    """Manages per-user configuration and identity."""

    def __init__(self, elite_dir: Optional[str] = None):
        if elite_dir:
            self.elite_dir = elite_dir
        else:
            self.elite_dir = os.environ.get(
                "ELITE_DIR",
                os.path.join(os.path.expanduser("~"), ".elite-reasoning")
            )
        self.config_path = os.path.join(self.elite_dir, "config.json")
        self.brain_dir = os.path.join(self.elite_dir, "brain")
        self._config = None

    def ensure_dirs(self):
        """Create all required directories."""
        os.makedirs(self.elite_dir, exist_ok=True)
        os.makedirs(self.brain_dir, exist_ok=True)

    @property
    def config(self) -> dict:
        if self._config is None:
            self._config = self._load_or_create_config()
        return self._config

    def _load_or_create_config(self) -> dict:
        """Load existing config or create a fresh one with auto-detected defaults."""
        self.ensure_dirs()
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    stored = json.load(f)
                # Merge with defaults (in case schema evolved)
                merged = _deep_merge(DEFAULT_CONFIG.copy(), stored)
                return merged
            except (json.JSONDecodeError, IOError):
                pass

        # First-time setup: auto-detect
        config = DEFAULT_CONFIG.copy()
        config["user_id"] = os.environ.get("ELITE_USER_ID", getpass.getuser())
        config["display_name"] = config["user_id"]
        config["ide_type"] = self._detect_ide()
        config["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        config["updated_at"] = config["created_at"]

        # Pull from env if set
        if os.environ.get("GEMINI_API_KEY"):
            config["orchestration"]["gemini_api_key"] = os.environ["GEMINI_API_KEY"]
        if os.environ.get("ELITE_SYNC_URL"):
            config["sync"]["hub_url"] = os.environ["ELITE_SYNC_URL"]
            config["sync"]["enabled"] = True
        if os.environ.get("ELITE_SYNC_API_KEY"):
            config["sync"]["api_key"] = os.environ["ELITE_SYNC_API_KEY"]

        self._save_config(config)
        return config

    def _save_config(self, config: dict):
        """Persist config to disk."""
        config["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.ensure_dirs()
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
        self._config = config

    def save(self):
        """Save current config state."""
        self._save_config(self.config)

    def _detect_ide(self) -> str:
        """Detect which IDE the user is running."""
        home = os.path.expanduser("~")
        if os.path.isdir(os.path.join(home, ".gemini", "antigravity")):
            return "antigravity"
        if os.path.isdir(os.path.join(home, ".cursor")):
            return "cursor"
        if os.path.isdir(os.path.join(home, ".vscode")):
            return "vscode"
        return "standalone"

    # ── Identity ───────────────────────────────────────────
    @property
    def user_id(self) -> str:
        return self.config.get("user_id", getpass.getuser())

    @property
    def display_name(self) -> str:
        return self.config.get("display_name", self.user_id)

    @property
    def ide_type(self) -> str:
        return self.config.get("ide_type", "unknown")

    # ── Sync ───────────────────────────────────────────────
    @property
    def sync_enabled(self) -> bool:
        return self.config.get("sync", {}).get("enabled", False)

    @property
    def sync_hub_url(self) -> str:
        return self.config.get("sync", {}).get("hub_url", "http://localhost:8000")

    @property
    def sync_api_key(self) -> str:
        return self.config.get("sync", {}).get("api_key", "")

    # ── Orchestration ──────────────────────────────────────
    @property
    def orchestration_mode(self) -> str:
        return self.config.get("orchestration", {}).get("mode", "auto")

    @property
    def disabled_mcps(self) -> list[str]:
        return self.config.get("orchestration", {}).get("disabled_mcps", [])

    @property
    def disabled_skills(self) -> list[str]:
        return self.config.get("orchestration", {}).get("disabled_skills", [])

    @property
    def priority_mcps(self) -> list[str]:
        return self.config.get("orchestration", {}).get("priority_mcps", [])

    @property
    def priority_skills(self) -> list[str]:
        return self.config.get("orchestration", {}).get("priority_skills", [])

    # ── Summary ────────────────────────────────────────────
    def get_profile_summary(self) -> str:
        """Return a human-readable profile summary."""
        from core.tools.orchestration import scan_available_mcps, scan_available_skills
        mcps = scan_available_mcps()
        skills = scan_available_skills()
        return (
            f"# User Profile: {self.display_name}\n\n"
            f"| Field | Value |\n|---|---|\n"
            f"| User ID | `{self.user_id}` |\n"
            f"| IDE | `{self.ide_type}` |\n"
            f"| MCPs | {len(mcps)} installed |\n"
            f"| Skills | {len(skills)} installed |\n"
            f"| Sync | {'✅ Enabled' if self.sync_enabled else '❌ Disabled'} |\n"
            f"| Hub URL | `{self.sync_hub_url}` |\n"
            f"| Orchestration | `{self.orchestration_mode}` |\n"
            f"| Brain Dir | `{self.brain_dir}` |\n"
            f"| Config | `{self.config_path}` |\n"
        )


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base, preserving base keys not in override."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
