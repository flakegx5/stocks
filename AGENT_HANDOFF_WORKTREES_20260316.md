# Agent Handoff - Worktree Setup

## Purpose

This note is for the next agent taking over the repository after the worktree split.

The repo now uses four sibling worktrees under one parent directory:

- `<worktree-root>/main` -> `main`
- `<worktree-root>/data` -> `codex/data-pipeline`
- `<worktree-root>/indicators` -> `codex/indicators`
- `<worktree-root>/frontend` -> `codex/frontend`

`main` is the integration worktree. Feature work should happen in the other three directories unless the task is explicitly about merge, release, or shared integration.

## Routing

Choose the worktree by task type:

- data ingestion, scraping, session/login flow, update automation, raw JSON refresh:
  `<worktree-root>/data`
- derived metrics, ranking rules, build pipeline, output schema, backend-side tests:
  `<worktree-root>/indicators`
- HTML, CSS, JS UI, layout, filters, sorting UX, rendering performance:
  `<worktree-root>/frontend`
- final merge validation, branch sync, docs that affect all lanes:
  `<worktree-root>/main`

If a task spans multiple lanes, prefer this order:

1. land minimal shared changes first
2. merge to `main`
3. rebase the remaining lane worktrees onto `origin/main`

## Key Files By Lane

Data lane:

- `scrape_iwencai_xhr.py`
- `scripts/audit_missing_financials.py`
- `scripts/hkex_second_pass.py`
- `hk_stocks_data_new.json`

Indicators lane:

- `build_html.py`
- `stocks_build/config.py`
- `stocks_build/metrics.py`
- `stocks_build/pipeline.py`
- `tests/test_build_logic.py`

Frontend lane:

- `index.html`
- `assets/styles/dashboard.css`
- `assets/scripts/dashboard.js`

Shared references:

- `README.md`
- `WORKTREE_GUIDE.md`
- `CLAUDE.md`

## First Steps For Any Agent

Run these commands inside the selected worktree:

```bash
git status
git fetch origin
git rebase origin/main
```

If the task touches scraping or build output, also inspect:

```bash
sed -n '1,220p' README.md
sed -n '1,220p' WORKTREE_GUIDE.md
```

## Common Commands

Data lane:

```bash
python3 scrape_iwencai_xhr.py --login
python3 scrape_iwencai_xhr.py --build
python3 scripts/audit_missing_financials.py --write-json debug_responses/missing_financial_audit.json
python3 scripts/hkex_second_pass.py --out debug_responses/hkex_second_pass/final_candidates.json
```

Indicators lane:

```bash
python3 build_html.py
python3 -m unittest tests.test_build_logic
python3 -m unittest tests.test_audit_missing_financials
python3 -m unittest tests.test_hkex_second_pass
```

Frontend lane:

```bash
python3 build_html.py
open index.html
```

## Validation Expectations

Before handing off or merging:

- record which worktree was used
- record whether `git rebase origin/main` succeeded
- list files changed
- run the narrowest relevant tests
- mention if generated files such as `data.js` changed

## Current State

This handoff only covers repository structure and workflow. It does not imply that pending feature branches are merged.

The worktree layout was reorganized into a single parent folder on 2026-03-16, and `git worktree repair` was run afterward to refresh path metadata.

## Cautions

- do not create manual copies of the repo for isolation
- do not let multiple agents edit the same worktree simultaneously
- do not use `main` as a long-running feature branch
- if a worktree folder is moved again, run `git worktree repair`
