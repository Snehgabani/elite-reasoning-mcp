"""Action Registry — Protocol-based dispatch with fuzzy matching.

Replaces if/elif trees in verb_tools.py with testable action classes.
Auto-generates enum schema from registrations.
Fuzzy-matches typos with difflib.get_close_matches."""
import logging
import difflib
from typing import Protocol, Any, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class Action(Protocol):
    """Protocol that all action handlers must implement."""
    name: str
    verb: str
    description: str

    def execute(self, store, **kwargs) -> str: ...


class ActionRegistry:
    """Registry of verb actions with fuzzy matching and deprecation support.

    Usage:
        registry = ActionRegistry()
        registry.register(HealthCheckAction())
        result = registry.dispatch("introspect", "health", store)
    """

    def __init__(self):
        self._actions: dict[str, dict[str, Action]] = {}  # verb -> {action_name -> Action}
        self._aliases: dict[str, tuple[str, str]] = {}     # alias -> (verb, action_name)
        self._deprecated: dict[str, str] = {}              # old_name -> new_name

    def register(self, action: Action):
        """Register an action handler."""
        self._actions.setdefault(action.verb, {})[action.name] = action
        logger.debug(f"Registered action: {action.verb}/{action.name}")

    def register_alias(self, alias: str, verb: str, action_name: str):
        """Register an alias that maps to an existing action."""
        self._aliases[alias] = (verb, action_name)

    def register_deprecation(self, old_name: str, new_name: str):
        """Register a deprecated action name with its replacement."""
        self._deprecated[old_name] = new_name

    def dispatch(self, verb: str, action: str, store, **kwargs) -> str:
        """Dispatch to the appropriate action handler.

        Returns the action's string result or an error message.
        """
        # Check deprecation
        if action in self._deprecated:
            new_name = self._deprecated[action]
            logger.warning(f"Action '{action}' is deprecated, use '{new_name}'")
            action = new_name

        # Check aliases
        if action in self._aliases:
            verb, action = self._aliases[action]

        # Exact match
        verb_actions = self._actions.get(verb, {})
        handler = verb_actions.get(action)
        if handler:
            return handler.execute(store, **kwargs)

        # Fuzzy match
        all_names = list(verb_actions.keys())
        matches = difflib.get_close_matches(action, all_names, n=3, cutoff=0.6)
        if matches:
            suggestion = ", ".join(f"'{m}'" for m in matches)
            return f"❌ Unknown action '{action}'. Did you mean: {suggestion}?"

        # List available
        if all_names:
            available = ", ".join(sorted(all_names))
            return f"❌ Unknown action '{action}' for verb '{verb}'. Available: {available}"
        return f"❌ No actions registered for verb '{verb}'"

    def get_schema(self, verb: str) -> list[str]:
        """Get list of available actions for a verb (for enum schema)."""
        return sorted(self._actions.get(verb, {}).keys())

    def get_all_actions(self) -> dict[str, list[str]]:
        """Get all registered actions grouped by verb."""
        return {verb: sorted(actions.keys()) for verb, actions in self._actions.items()}

    def get_action_help(self, verb: str, action: str) -> str | None:
        """Get the description for a specific action."""
        handler = self._actions.get(verb, {}).get(action)
        return handler.description if handler else None
