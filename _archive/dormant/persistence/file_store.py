import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

class FileStore:
    """
    Atomic markdown file manager.
    Implements atomic writes with temp+rename pattern to prevent corruption on crash.
    """
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, relative_path: str) -> Path:
        """Resolve a relative path against the base directory."""
        path = self.base_dir / relative_path
        # Basic security check to prevent path traversal
        if not str(path.resolve()).startswith(str(self.base_dir.resolve())):
            raise ValueError(f"Path traversal detected: {relative_path}")
        return path

    def read(self, relative_path: str) -> Optional[str]:
        """Read a file's contents. Returns None if the file doesn't exist."""
        path = self._get_path(relative_path)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def write(self, relative_path: str, content: str) -> None:
        """
        Atomically write content to a file.
        Uses a temporary file and os.replace() which is atomic on POSIX.
        """
        path = self._get_path(relative_path)
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create a temporary file in the same directory (to ensure it's on the same filesystem)
        fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
        
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            
            # Atomic replace
            os.replace(temp_path, path)
        except Exception as e:
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e

    def append(self, relative_path: str, content: str) -> None:
        """
        Atomically append content to a file.
        Reads existing content, appends, and uses atomic write.
        """
        existing = self.read(relative_path) or ""
        # Ensure newline separation if existing content doesn't end with one
        if existing and not existing.endswith("\n"):
            existing += "\n"
        
        new_content = existing + content
        self.write(relative_path, new_content)

    def delete(self, relative_path: str) -> bool:
        """Delete a file. Returns True if deleted, False if it didn't exist."""
        path = self._get_path(relative_path)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_files(self, relative_dir: str = "") -> list[str]:
        """List all files in a directory relative to the base dir."""
        dir_path = self._get_path(relative_dir)
        if not dir_path.exists() or not dir_path.is_dir():
            return []
        
        files = []
        for path in dir_path.rglob("*"):
            if path.is_file() and not path.name.startswith("."):
                files.append(str(path.relative_to(self.base_dir)))
        return files
