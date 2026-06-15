import yaml
from pathlib import Path

class ConfigLoader:
    """
    Loads system configuration mapping to System's config.json structure.
    """
    def __init__(self, brain_dir: str):
        self.config_path = Path(brain_dir) / "config.yaml"
        self.config = self._default_config()
        self.load()
        
    def _default_config(self) -> dict:
        return {
            "executive_llm": {
                "provider": "anthropic",
                "default_model": "claude-3-5-sonnet-20240620"
            },
            "reasoning_llm": {
                "provider": "deepseek",
                "default_model": "deepseek-reasoner",
                "fallback_provider": "anthropic",
                "fallback_model": "claude-3-opus-20240229"
            },
            "memory": {
                "vector_db": "qdrant",
                "embedding_model": "BAAI/bge-small-en-v1.5",
                "consolidation_interval_sec": 14400
            },
            "watchdog": {
                "heartbeat_interval_sec": 300
            },
            "telemetry": {
                "langfuse_enabled": True,
                "deepeval_enabled": True
            }
        }
        
    def load(self):
        """Load configuration from file if it exists."""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if loaded:
                    # Update config, preserving defaults for missing keys
                    self._update_nested_dict(self.config, loaded)
                    
    def _update_nested_dict(self, d, u):
        for k, v in u.items():
            if isinstance(v, dict):
                d[k] = self._update_nested_dict(d.get(k, {}), v)
            else:
                d[k] = v
        return d
        
    def get(self, key_path: str, default=None):
        """Get a config value using dot notation (e.g. 'llm.provider')."""
        keys = key_path.split(".")
        val = self.config
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val
