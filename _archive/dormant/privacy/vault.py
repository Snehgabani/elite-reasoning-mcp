import os
import getpass
import logging
from pathlib import Path
from dotenv import load_dotenv, set_key

logger = logging.getLogger(__name__)

class VaultManager:
    """
    Manages secure credentials via .env and confidential documents in the brain/vault.
    Guarantees secrets are loaded into the OS environment and never leaked into static configs.
    """
    def __init__(self, brain_dir: str):
        self.brain_path = Path(brain_dir)
        self.env_path = self.brain_path / ".env"
        self.vault_path = self.brain_path / "vault"
        
        self._initialize()

    def _initialize(self):
        """Ensure vault directory and .env exist, and load the environment."""
        self.vault_path.mkdir(parents=True, exist_ok=True)
        
        # Touch .env if it doesn't exist
        if not self.env_path.exists():
            self.env_path.touch(mode=0o600)  # rw------- permissions
            
        # Load any existing variables
        load_dotenv(dotenv_path=self.env_path)

    def require_secret(self, key_name: str, prompt_message: str):
        """
        Check if a secret exists in the environment.
        Since the Elite System is now an IDE Augmentation Layer, we do not halt execution
        if a secret is missing. The IDE handles execution, so this is mostly for third-party tools.
        """
        if os.environ.get(key_name):
            return os.environ.get(key_name)
        return None

    def get_secret(self, key_name: str) -> str | None:
        """Get a secret from the environment."""
        return os.environ.get(key_name)

    def get_vault_path(self) -> str:
        """Returns the absolute path to the confidential vault."""
        return str(self.vault_path)
