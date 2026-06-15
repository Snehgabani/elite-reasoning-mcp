import sys
import os

# Ensure the parent directory is in sys.path just in case uv run doesn't perfectly resolve it
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.cli import main as cli_main

def main():
    cli_main()

if __name__ == "__main__":
    main()
