# Prompts

Versioned prompt specifications. The prompt actually sent to the model lives in
[`src/procurement_agent/prompts.py`](../src/procurement_agent/prompts.py).

Changing prompt text without bumping `prompt_version` in `config.py` invalidates
evaluation results recorded against the old version.

| File | Purpose |
|---|---|
| [`quotation-extraction-v1.md`](quotation-extraction-v1.md) | Prompt Specification v1.0 and version history (Week 2) |
