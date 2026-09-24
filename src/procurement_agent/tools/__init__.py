"""Deterministic procurement tools. None of them calls the model.

Week 4 catalogue: four functions with explicit schemas, injected roles and
an allow-list. The orchestration layer (``dispatch.invoke``) is the only
entry point the application uses; the model never calls a tool directly.
"""

from .dispatch import TOOLS, invoke

__all__ = ["TOOLS", "invoke"]
