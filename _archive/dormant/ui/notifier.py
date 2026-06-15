import sys

class SystemNotifier:
    """
    A notification layer designed to provide a smooth, non-coder friendly UX.
    Translates complex background system operations into easy-to-understand alerts.
    """
    def __init__(self, verbose=True):
        self.verbose = verbose

    def notify(self, message: str, icon: str = "ℹ️", color_code: str = "\033[94m"):
        """Sends a standard notification to the user."""
        if not self.verbose:
            return
        
        # ANSI reset code
        reset = "\033[0m"
        print(f"{color_code}{icon} {message}{reset}")

    def alert(self, message: str):
        """Sends an important alert or warning."""
        self.notify(message, icon="⚠️", color_code="\033[93m")

    def success(self, message: str):
        """Sends a success notification."""
        self.notify(message, icon="✅", color_code="\033[92m")
        
    def working(self, message: str):
        """Indicates background work, workflow orchestration, or auto-creation is happening."""
        self.notify(message, icon="🔄", color_code="\033[96m")
        
    def thinking(self, message: str):
        """Indicates deep reasoning or framework application."""
        self.notify(message, icon="🧠", color_code="\033[95m")
        
    def guide(self, message: str):
        """Provides helpful guidance or best practices to the user."""
        self.notify(message, icon="💡", color_code="\033[92m")
