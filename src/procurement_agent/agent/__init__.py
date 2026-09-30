"""Bounded weekly-reorder workflow. Direct orchestration, no framework.

Charter section 6 steps 3–8 are this loop: a maximum iteration count, a
static allow-list per step, and a human gate before anything is written.
Gemini never calls a tool. A planner may *propose* a call; ``dispatch.invoke``
executes it under the injected role.
"""

from .steps import DEFAULT_MAX_ITERATIONS
from .workflow import AgentResult, run_workflow

__all__ = ["DEFAULT_MAX_ITERATIONS", "AgentResult", "run_workflow"]
