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
import copy
import getpass
import json
import os
import tempfile
import time
from typing import Optional

DEFAULT_CONFIG = {
    "user_id": "",
    "display_name": "",
    "ide_type": "auto",
    "sync": {
        "enabled": False,
        "hub_url": "http://localhost:8000",
        "auto_sync_on_boot": False,
        "sync_interval_minutes": 60,
    },
    "orchestration": {
        "mode": "auto",             # "auto" | "heuristic" | "llm"
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
        os.makedirs(self.elite_dir, mode=0o700, exist_ok=True)
        os.makedirs(self.brain_dir, mode=0o700, exist_ok=True)
        for path in (self.elite_dir, self.brain_dir):
            try:
                os.chmod(path, 0o700)
            except OSError:
                pass

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
                # Migrate pre-v2 persisted credentials out of the profile.
                # Keys must be supplied by the process environment or keychain,
                # never copied into a project-independent JSON file.
                migrated = _strip_persisted_secrets(stored)
                # Boot-time synchronization can disclose installed-tool and
                # workstation metadata before the user has confirmed a run.
                if isinstance(migrated.get("sync"), dict):
                    migrated["sync"]["auto_sync_on_boot"] = False
                if "ide_type_source" not in stored:
                    # Earlier releases persisted auto-detection, causing a
                    # permanent Antigravity/Zed mismatch after an IDE switch.
                    migrated["ide_type"] = "auto"
                    migrated["ide_type_source"] = "auto"
                # Merge with defaults (in case schema evolved).
                merged = _deep_merge(copy.deepcopy(DEFAULT_CONFIG), migrated)
                if migrated != stored:
                    self._save_config(merged)
                return merged
            except (json.JSONDecodeError, IOError):
                pass

        # First-time setup: auto-detect
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["user_id"] = os.environ.get("ELITE_USER_ID", getpass.getuser())
        config["display_name"] = config["user_id"]
        config["ide_type_source"] = "auto"
        config["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        config["updated_at"] = config["created_at"]

        # Pull non-secret connection configuration from the environment. API
        # keys deliberately stay in environment/keychain-backed process state.
        if os.environ.get("ELITE_SYNC_URL"):
            config["sync"]["hub_url"] = os.environ["ELITE_SYNC_URL"]
            config["sync"]["enabled"] = True
        self._save_config(config)
        return config

    def _save_config(self, config: dict):
        """Persist config atomically with owner-only permissions."""
        config["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.ensure_dirs()
        fd, temporary_path = tempfile.mkstemp(prefix=".config.", suffix=".tmp", dir=self.elite_dir)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(config, handle, indent=2)
                handle.write("\n")
            os.replace(temporary_path, self.config_path)
            os.chmod(self.config_path, 0o600)
        except Exception:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
            raise
        self._config = config

    def save(self):
        """Save current config state."""
        self._save_config(self.config)

    def _detect_ide(self) -> str:
        """Detect which IDE the user is running."""
        explicit = os.environ.get("ELITE_ACTIVE_IDE", "").strip().lower()
        if explicit:
            return explicit
        try:
            from core.orchestration.capabilities import build_capability_registry
            registry = build_capability_registry()
            if registry.active_ide:
                return registry.active_ide
        except Exception:
            pass
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
        configured = self.config.get("ide_type", "unknown")
        if self.config.get("ide_type_source") == "manual" and configured and configured != "auto":
            return configured
        return self._detect_ide()

    # ── Sync ───────────────────────────────────────────────
    @property
    def sync_enabled(self) -> bool:
        return self.config.get("sync", {}).get("enabled", False)

    @property
    def sync_hub_url(self) -> str:
        return self.config.get("sync", {}).get("hub_url", "http://localhost:8000")

    @property
    def sync_api_key(self) -> str:
        return os.environ.get("ELITE_SYNC_API_KEY", "")

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
        from core.orchestration.capabilities import build_capability_registry
        registry = build_capability_registry()
        mcps = registry.names("mcp")
        skills = registry.names("skill")
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


def _strip_persisted_secrets(config: dict) -> dict:
    """Remove legacy secret fields during profile migration."""
    cleaned = copy.deepcopy(config) if isinstance(config, dict) else {}
    sync = cleaned.get("sync")
    if isinstance(sync, dict):
        sync.pop("api_key", None)
    orchestration = cleaned.get("orchestration")
    if isinstance(orchestration, dict):
        orchestration.pop("gemini_api_key", None)
    return cleaned
