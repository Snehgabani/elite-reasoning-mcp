import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from core.tools.native_tools import NativeTools

def test_native_tools():
    workspace = os.path.expanduser("~/.gemini/antigravity/scratch/elite-system/brain")
    tools = NativeTools(workspace_dir=workspace, auto_approve=True)
    
    # Test 1: Jail test
    safe_path = os.path.join(workspace, "test.txt")
    unsafe_path = "/etc/passwd"
    
    print("Testing path jail...")
    assert tools._is_safe_path(safe_path) == True
    assert tools._is_safe_path(unsafe_path) == False
    print("Path jail test passed.")
    
    # Test 2: Auto-approve logic
    print("Testing interceptor logic...")
    assert any("rm".startswith(c) for c in tools.critical_commands) == True
    assert any("echo".startswith(c) for c in tools.critical_commands) == False
    print("Interceptor logic test passed.")
    
if __name__ == "__main__":
    test_native_tools()
