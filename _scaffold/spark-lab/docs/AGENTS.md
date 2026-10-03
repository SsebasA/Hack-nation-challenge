# Agents and gates

SPARK Lab runs on Omnigent as one Supervisor and three sub-agents, defined in `lab.yaml`.
Sub-agents are roles; tool guards and human CLIs are gates; the ledger is the lab notebook.

## Roles (least privilege)

| Agent | SPARK step | Tools |
|---|---|---|
| Supervisor | orchestrates, records decisions | read_board, ledger_read, ledger_append + the three sub-agents |
| Scout | **S**urprise | read_board, compute_surprise, estimate, check_power, ledger_append, ledger_read |
| Skeptic | **A**ttack | read_board, check_definitions, check_power, estimate, ledger_append, ledger_read |
| Experimenter | **P**ropose, **R**un | check_power, estimate, register_prereg, run_test, ledger_append, ledger_read |
| Humans | objective, judgment, **K**eep/Kill gate | `sparklab.approve`, `sparklab.unseal`, `sparklab.ledger add` (terminal only) |

No agent declares `os_env`, so no agent has a shell or file access: they can only call the
functions above. Sub-agents run with `pass_history: false` so each starts independent.

## Gates (in code)

| Gate | Where | What it blocks |
|---|---|---|
| Hold-out seal | `data.load`, `data.load_holdout`, `ledger.holdout_gate` | any read of cycle I without prereg + matching human approval + verified unseal |
| Look budget | `tools.run_test` | more than `MAX_HOLDOUT_LOOKS` (1) hold-out runs; each attempt past the gates is counted |
| Pre-registration | `ledger.register_prereg`, `ledger.load_protocol` | running a test without a frozen, git-committed protocol; edits after registration |
| Power | `tools.register_prereg`, `tools.run_test` | cells with unweighted n < 30 entering confirmatory testing |
| Definitions | `tools.check_definitions` | non-ADA category thresholds, wrong weights, banned labels; flags causal wording and race/ethnicity |
| Mandatory rival | `tools.register_prereg` | protocols without `H_measurement_error` and a declared floor |
| Human-only actions | `approve.py`, `unseal.py` (TTY + typed hash prefix) | agents approving or unsealing |
| Ledger integrity | `ledger.verify` (hash chain) | hand edits, deletions, reordering |
| Number provenance | `ledger/calcs.jsonl` | numbers without a `calc_id` (warned on `ledger_append`) |

## Seeded control
`board/control_seeded.json` holds one expectation with a wrong definition. `read_board` strips the
`seeded` flag so agents cannot tell it apart. The Skeptic is instructed to check every item. Metric: caught yes/no.
Limitation: `check_definitions` detects this error class deterministically, so the control tests the
Skeptic's diligence, not its judgment. v2: a control the checker cannot see (e.g. population mismatch).
