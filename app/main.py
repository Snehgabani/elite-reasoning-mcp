import os
import sys
import warnings

# Filter benign FastMCP / Pydantic forward reference warning in Python 3.13
warnings.filterwarnings("ignore", module="pydantic_settings")

# Ensure the parent directory is in sys.path just in case uv run doesn't perfectly resolve it
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.cli import main as cli_main  # noqa: E402


def main():
    cli_main()


if __name__ == "__main__":
    main()

