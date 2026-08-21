"""
Dynamic Verifier Plugin Loader (WS10 / Phase 5).
Discovers and registers custom third-party verifier plugins securely.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import List, Optional
from core.plugins.protocol import PluginVerifier
from core.verification.registry import GLOBAL_VERIFIER_REGISTRY, VerifierRegistry


def load_plugin_from_file(file_path: Path, registry: Optional[VerifierRegistry] = None) -> List[PluginVerifier]:
    path = Path(file_path)
    if not path.exists() or not path.suffix == ".py":
        return []

    target_reg = registry or GLOBAL_VERIFIER_REGISTRY
    loaded = []

    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, PluginVerifier) and attr is not PluginVerifier:
                try:
                    instance = attr()
                    target_reg.register(instance)
                    loaded.append(instance)
                except Exception:
                    pass

    return loaded
