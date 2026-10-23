# CI/CD and security checks

GitHub Actions runs [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) on every push and pull request. This note is the map of what each check is for, what it cannot do, and what to turn on in the GitHub UI.

## What CI is, in this project

Jobs run **only when the changed files match that job**. A docs-only PR does not run pytest or Bandit. GitHub required checks cannot be “sometimes absent”, so one job named **CI** always reports: it is green if every *applicable* job passed or was skipped, and red only if a job that did run failed.

| Job | Tool | Runs when these paths change | Blocks merge? |
|---|---|---|---|
| Pytest | pytest | `src/`, `tests/`, `fixtures/`, `tools/`, `pyproject.toml` | Only then |
| Bandit | [Bandit](https://bandit.readthedocs.io/) | `src/`, `.semgrep/`, `pyproject.toml`, the CI workflow | Only then |
| Semgrep | [Semgrep](https://semgrep.dev/) | same as Bandit | Only then |
| pip-audit | [pip-audit](https://pypi.org/project/pip-audit/) | `pyproject.toml` | Only then |
| Secrets hygiene | git | always (cheap; catching a committed `.env` always matters) | Always |
| Branch contains main | git | always, except pushes to `main` itself | Always (PRs / feature branches) |
| RAG / tool / agent tests | pytest | matching `src/` and `tests/` paths, and only if those test files exist | Only then |
| **CI** | aggregator | always | **This is the one to require on `main`** |

Bandit and Semgrep are **SAST** (static application security testing): they inspect source. They are not a pentest and they do not call Gemini.

## “Must pull main before pushing”

GitHub **cannot refuse** `git push` to `ft-your-name` just because you have not merged main. The commits land; CI then fails the **Branch contains origin/main** job.

What that job asks: is `origin/main` an ancestor of your HEAD? If not, you are behind.

```bash
git fetch origin
git merge origin/main
git push
```

Rebase is also fine (`git rebase origin/main`) if the team agrees to rebase.

**To block merging into `main` until CI is green and the branch is current**, someone with admin on the repo (George) should set, once:

1. Settings → Rules → Rulesets → New branch ruleset
2. Target: `main`
3. Require a pull request before merging
4. Require status checks to pass: tick **CI** only (the aggregator). Do not require Bandit, Pytest, Semgrep as separate required checks — if you do, a docs-only PR cannot merge because those jobs were skipped.
5. Require branches to be up to date before merging

Do **not** apply “require status checks” to every feature branch: that setting is for protecting `main`, not for locking people out of their own branches.

Direct pushes to `main` should be off. Work goes through a PR.

## Run the same checks locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[ci]"
pip install semgrep          # large; CI installs it for you

pytest
bandit -r src -c pyproject.toml -ll
semgrep scan --config p/python --config p/security-audit --config p/secrets --config .semgrep/ --error --metrics=off
pip install -e ".[gemini]"
pip-audit
```

No API key is required for pytest, Bandit, or Semgrep.

## Charter rules in `.semgrep/`

`.semgrep/agent-safety.yml` forbids helpers named like `issue_purchase_order`, `contact_supplier`, or `commit_funds`. Those names do not exist today, so the rule is silent. If a later week adds a tool that places an order, CI fails even if pytest is green. That is S7/S8 as a pipeline gate.

Add more rules there as Week 4 tools land (for example: no HTTP client in a tool that is supposed to be in-process only).

## If a check fails and you think it is wrong

- **Bandit / Semgrep:** read the finding. Bandit is set to report medium and high only (`-ll`), so a lone `assert` in `client.py` does not fail CI. If a finding is a false positive, document why in the PR; skip one line with `# nosec` (Bandit) or `nosemgrep` (Semgrep) — not a blanket disable.
- **pip-audit:** pin or upgrade the package. Do not ignore a CVE in `google-genai` without writing it in the AI engineering log. When an upgrade is impossible because another dependency pins the old version, add the advisory IDs to [`.github/pip-audit-exceptions.txt`](../../.github/pip-audit-exceptions.txt) with the package, the date, the reason and the condition for removing them. CI ignores exactly those IDs and still fails on anything else. The current entries are 35 Pillow 12.3.0 advisories, held back by fastembed (23 October 2026).
- **Behind main:** merge main; do not skip the job.

## Evidence for the course

Week 7 asks for guardrail evidence. A green CI run (Actions tab → a workflow run URL) is part of that pack: tests, SAST, dependency audit, and the “no PO helper” rules. Paste the run URL into the weekly report.
