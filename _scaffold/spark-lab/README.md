# SPARK Lab

**Surprise → Propose → Attack → Run → Keep/Kill.** A scientific procedure for re-analysis of existing data:
agents generate and attack pre-registered rival hypotheses; humans set the objective, judge, and approve.
Hack-Nation 7 · Challenge 03 "Agentic Scientific Discovery" (Databricks / Omnigent).

Case: undiagnosed diabetes among US adults (NHANES 2017–2018 discovery, 2015–2016 sealed hold-out).

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install omnigent && pip install -e .
python tests/smoke_test.py                 # SMOKE TEST OK
python -m sparklab.data --cycle J
python -m sparklab.data --cycle I --seal
omnigent run lab.yaml
```

- `lab.yaml` — Supervisor + Scout, Skeptic, Experimenter (see `docs/AGENTS.md`)
- `sparklab/` — data, design-based stats, hash-chained ledger, agent tools with gates, human CLIs
- `board/` — expectation board and seeded control
- `ledger/ledger.jsonl` — run records (append-only, `python -m sparklab.ledger verify`)
- `prereg/` — frozen, git-committed protocols
- `docs/` — runbook, agents and gates, templates

Outputs are "which discrepancy to investigate next", never screening, treatment or causal claims.
