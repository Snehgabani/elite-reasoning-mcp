import argparse
import sys
import os

from core.persistence.recovery import RecoveryManager
from scripts.stress_test import run_stress_test

def main():
    parser = argparse.ArgumentParser(description="Elite System CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    # Stress test command
    test_parser = subparsers.add_parser("test", help="Run the diagnostic stress test")
    test_parser.add_argument("--brain-dir", default=os.path.expanduser("~/.gemini/antigravity/scratch/elite-system/brain"))
    test_parser.add_argument("--mock", action="store_true")
    test_parser.add_argument("--step", type=int, default=None)
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export system diagnostic state")
    export_parser.add_argument("--brain-dir", default=os.path.expanduser("~/.gemini/antigravity/scratch/elite-system/brain"))
    
    # Guide command
    guide_parser = subparsers.add_parser("guide", help="Start the interactive Elite Local Guide")
    guide_parser.add_argument("--brain-dir", default=os.path.expanduser("~/.gemini/antigravity/scratch/elite-system/brain"))
    guide_parser.add_argument("--model", default="llama3")
    
    args = parser.parse_args()
    
    if args.command == "test":
        run_stress_test(args.brain_dir, args.mock, args.step)
    elif args.command == "export":
        print("Delegating to core ExportEngine...")
        from core.diagnostics.exporter import ExportEngine
        from core.privacy.vault import VaultManager
        vault = VaultManager(args.brain_dir)
        engine = ExportEngine(args.brain_dir, vault)
        engine.generate_export("active_thread")
    elif args.command == "guide":
        from core.assistance.guide import EliteLocalGuide
        guide = EliteLocalGuide(args.brain_dir, args.model)
        guide.interactive_loop()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
