"""
Verifier Plugin SDK Protocol (WS10 / Phase 5).
Provides typed interfaces and metadata standards for third-party verifier plugins.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from pydantic import BaseModel, Field
from core.contracts.models import RequirementKind
from core.verification.registry import BaseVerifier


class PluginMetadata(BaseModel):
    name: str
    version: str
    author: str
    description: str
    supported_kinds: List[RequirementKind] = Field(default_factory=list)
    schema_version: str = "1.0.0"


class PluginVerifier(BaseVerifier, ABC):
    """Base class for external verifiers extending Elite Reasoning MCP."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        pass

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def version(self) -> str:
        return self.metadata.version

    @property
    def supported_requirement_kinds(self) -> List[RequirementKind]:
        return self.metadata.supported_kinds
