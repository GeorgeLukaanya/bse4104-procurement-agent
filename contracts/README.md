# Contracts

Machine-readable agreements the code loads at runtime. They live here, at the top
level, so they are findable without reading the docs tree.

| File | What it binds | Explained in |
|---|---|---|
| [`agent-task-contract.json`](agent-task-contract.json) | The bounded agent loop: goal, approved actions, phases, limits, stop conditions and human gates | [`docs/requirements/agent-task-contract.md`](../docs/requirements/agent-task-contract.md) |

## Rules

- **This file is canonical.** The loop reads it at startup and takes its iteration
  cap, time budget and action set from it. The write-up explains the same values;
  if the two disagree, this file is what actually runs.
- **Change a limit here, not in code.** `agent/contract.py` loads it; nothing
  hard-codes the numbers.
- **A missing or malformed contract stops the run.** An unbounded loop is the
  thing the contract exists to prevent, so there is no silent fallback.
- **Precedence for one run:** a command-line flag, then an environment variable,
  then this file.
- **Changing a value is a team decision.** Bump `contract_version` and say why in
  the write-up.
