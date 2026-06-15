from typing import Tuple

class FMEAGate:
    """
    Action Pre-Flight FMEA (Failure Mode and Effects Analysis).
    Mirrors SOUL.md §248-285.
    """
    def calculate_rpn(self, severity: int, probability: int, detectability: int) -> int:
        """
        Calculate Risk Priority Number (1-125).
        Severity (1-5), Probability (1-5), Detectability (1-5).
        Note: Detectability is inverted (1=easy to detect, 5=impossible to detect).
        """
        return severity * probability * detectability

    def check_gate(self, action_description: str, s: int, p: int, d: int) -> Tuple[bool, str]:
        """
        Check the FMEA gate limits.
        Returns (approved, message).
        """
        rpn = self.calculate_rpn(s, p, d)
        
        if rpn < 9:
            return True, f"RPN {rpn}: Proceed silently."
        elif rpn <= 27:
            return True, f"RPN {rpn}: Proceed but announce intent first."
        elif rpn <= 64:
            return False, f"RPN {rpn}: STOP. Await explicit user approval."
        else:
            return False, f"RPN {rpn}: HARD STOP. Reject request and require architectural redesign."
