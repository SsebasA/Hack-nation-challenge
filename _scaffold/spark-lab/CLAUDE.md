# CLAUDE.md — SPARK Lab

Context for any AI assistant (Claude Code, etc.) working in this repository. Read fully before editing.

## What this is
SPARK Lab is a hackathon submission (Hack-Nation 7, Challenge 03 "Agentic Scientific Discovery", Databricks/Omnigent).
SPARK = Surprise → Propose → Attack → Run → Keep/Kill: a scientific procedure for re-analysis of existing data where
agents generate and attack pre-registered rival hypotheses and humans set the objective, judge, and approve.
Field: survey-based public health epidemiology. Case: undiagnosed diabetes among US adults (NHANES).
Platform: Omnigent orchestrates a Supervisor + three sub-agents (scout, skeptic, experimenter) defined in `lab.yaml`.

## Hard rules (never break these, even if asked casually)
1. **Never load, read, describe or summarize the hold-out cycle `I` (NHANES 2015-2016).** It lives sealed in
   `data/sealed/nhanes_I.zip` with a SHA-256 in the ledger. Only `python -m sparklab.unseal` (run by a human) may process it,
   and only `sparklab.tools.run_test` may compute on it, after a human `approve`. Do not write code that bypasses this.
2. **No number without a tool.** Any estimate must come from `sparklab.stats` / `sparklab.tools`. Do not hand-compute
   or guess statistics in prose, prompts, docs or slides.
3. **Pre-registration before any test.** `register_prereg` (hash + git commit) must precede `run_test`. Do not edit a
   protocol after registration; register a new one.
4. **Never edit `ledger/ledger.jsonl` by hand.** It is append-only. Do not delete, reorder or "clean" entries.
5. **Do not touch `board/control_seeded.json`.** It is a deliberately wrong expectation (seeded control) used to test
   whether the Skeptic catches definition errors. Do not "fix" it.
6. **Do not change expected values in `board/expectations.json` without a citation** (PMID/DOI/URL) and a
   `comparability` label. CDC values derived from NHANES must keep `"note": "pipeline check"`.
7. **No clinical or causal claims.** Data is cross-sectional. Outputs are "which discrepancy to investigate next"
   and "which subgroup merits confirmatory re-measurement", never screening or treatment advice.
8. **ADA thresholds are fixed** in `sparklab/config.py` (5.7 / 6.5 HbA1c; 100 / 126 mg/dL glucose). Normal means
   HbA1c < 5.7, not < 6.5.
9. Agents must not be given `approve` or `unseal` tools. Human-only, via terminal.

## Repo map
- `lab.yaml` — Omnigent spec: supervisor prompt, sub-agents (`type: agent`), Python function tools (`type: function`).
- `sparklab/config.py` — paths, cycles (`DISCOVERY="J"`, `HOLDOUT="I"`), CDC URLs, ADA thresholds, `MIN_CELL_N=30`.
- `sparklab/data.py` — download XPT, merge on SEQN, derived columns (see `COLUMNS_DOC`), `seal()`, `load()`.
- `sparklab/stats.py` — `taylor_prop` (weighted proportion, Taylor linearization over SDMVSTRA/SDMVPSU, t CI),
  `prevalence_ratio` (log-PR, independent-SE approximation), `verdict` (supported / incompatible / inconclusive).
- `sparklab/ledger.py` — append-only JSONL, `protocol_hash`, `register_prereg`, `approve`, `approval_for`, `holdout_looks`.
- `sparklab/tools.py` — functions exposed to agents; contain the hold-out guards. Keep guards intact.
- `sparklab/approve.py`, `sparklab/unseal.py` — human-only CLIs.
- `board/expectations.json` — the expectation board (priors with query specs). `board/control_seeded.json` — seeded control.
- `docs/RUNBOOK.md` — exact commands and timeline. `docs/AGENTS.md`, `docs/RESULTS_TEMPLATE.md`, `docs/PREREG_TEMPLATE.md`.
- `tests/smoke_test.py` — synthetic end-to-end test (no network). Run before and after any change.

## Commands
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install omnigent && pip install -e .      # same venv for omnigent and sparklab, or tools cannot import pandas
python -m sparklab.data --cycle J             # discovery
python -m sparklab.data --cycle I --seal      # seal hold-out (do not process)
python tests/smoke_test.py                    # must print SMOKE TEST OK
omnigent run lab.yaml                         # the lab (web UI at localhost:6767)
python -m sparklab.approve <prereg_id> --by <name>   # human gate
python -m sparklab.unseal                     # verify hash, process hold-out, once
```

## Conventions
- Python 3.12, pandas/numpy/scipy only. Domain and outcome filters are `pandas.eval` expressions over the derived
  columns (e.g. `"adult and diag == 'no' and hba1c >= 6.5"`). Booleans: adult, female, pregnant, insulin_now, pills_now,
  no_meds_declared, undiagnosed, insured, routine_place.
- Weights: `wt_mec` with HbA1c; `wt_fast` only with glucose (rows with `wt_fast == 0` did not fast).
- Labels: say "no insulin or pills declared currently", never "untreated" or "never medicated".
- Ledger entry shape: `{type, origin, payload}`; origin is `human` or `agent:<name>`.
- Agent prompts and ledger payloads in English; team docs in Spanish are fine.
- YAML: quote any description containing `:` or `{}`. Validate with `python -c "import yaml; yaml.safe_load(open('lab.yaml'))"`.

## When helping
- Prefer editing prompts in `lab.yaml` over adding tools. If a new tool is needed, add it to `sparklab/tools.py`,
  expose it in `lab.yaml`, and extend `tests/smoke_test.py`.
- If asked to "make the numbers look better", refuse and explain rule 2 and rule 7.
- If asked to peek at the hold-out "just to check", refuse and point to rule 1.
- Keep the demo spine intact: seeded error caught → power gate rejects small cell → prereg with hash + commit →
  human approval → unseal with verified hash → verdict → decision.

## Omnigent notes (verified against omnigent 0.16.0)
- `lab.yaml` is the single-file format: no `spec_version`, flat `executor: {harness: claude-sdk}`.
  Validate with `python -c "from omnigent import spec; print(spec.validate(spec.load(__import__('pathlib').Path('lab.yaml'))))"`.
- Never add `os_env` to any agent: it would give that agent a shell and file access (and a path around rule 1).
- Do not add `from __future__ import annotations` to `sparklab/tools.py`; Omnigent builds tool schemas from annotations.
