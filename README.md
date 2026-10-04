# SPARK Lab

**Agents that re-analyse public health data under a scientific procedure, with humans in charge of the judgment calls.**

Hack-Nation 7 · Challenge 03 "Agentic Scientific Discovery" (Databricks / Omnigent).

SPARK = **S**urprise → **P**ropose → **A**ttack → **R**un → **K**eep/Kill. Agents look for results in existing data
that contradict published expectations, write pre-registered rival hypotheses, try to break them, and test the
survivor once on data they have never seen. Humans set the objective, choose what to pursue, approve the test and
decide what it means.

- **Field:** survey-based public health epidemiology.
- **Case:** undiagnosed diabetes among US adults (NHANES).
- **Discovery data:** NHANES 2017–2018 (cycle J). **Hold-out:** NHANES 2015–2016 (cycle I), sealed until a human
  unseals it for one confirmatory run.

---

## Contents

- [SPARK Lab](#spark-lab)
  - [Contents](#contents)
  - [How it works](#how-it-works)
  - [Architecture](#architecture)
  - [Repository layout](#repository-layout)
  - [Run it locally](#run-it-locally)
  - [Using the app](#using-the-app)
  - [Faster runs and testing](#faster-runs-and-testing)
  - [Configuration](#configuration)
  - [Deployment: Vercel + Railway](#deployment-vercel--railway)
  - [Ground rules](#ground-rules)
  - [Troubleshooting](#troubleshooting)
  - [More documentation](#more-documentation)

---

## How it works

| Step | Who | What happens |
|---|---|---|
| **S · Surprise** | Scout | Compares every expectation on the board (published priors with citations) with the discovery data and looks for contradictions between self-report, HbA1c and fasting glucose. **You choose which discrepancy to pursue.** |
| **P · Propose** | Experimenter | Writes 2–3 rival hypotheses with non-overlapping numeric predictions, always including `H_measurement_error` with a declared floor. |
| **A · Attack** | Skeptic | Checks every board definition against the ADA thresholds (one item is wrong on purpose), then attacks the draft: definitions, power, confounding, threshold sensitivity, measurement error. One debate round per point; the Supervisor rules. |
| **R · Run** | Experimenter + you | The protocol is frozen (SHA-256 + git commit) and run on the discovery data. **You approve it and unseal the hold-out**; the test then runs exactly once on cycle I. |
| **K · Keep / Kill** | Supervisor + you | The Supervisor summarises the verdicts (`supported` / `incompatible` / `inconclusive`). **You decide: keep, kill or revise.** |

What the system guarantees, in code rather than in prompts:

- **No number without a tool.** Every statistic comes from `sparklab.tools` and carries a `calc_id` recorded in
  `ledger/calcs.jsonl`; the UI shows it next to the value.
- **Pre-registration before any test.** `register_prereg` validates the protocol, runs the definition and power gates,
  writes `prereg/<id>.json`, git-commits it and records its hash. Edited protocols are refused.
- **Power gate.** Cells with an unweighted n below 30 never enter confirmatory testing.
- **Seeded control.** `board/control_seeded.json` holds a deliberately wrong expectation, to check that the Skeptic catches
  definition errors.
- **Sealed hold-out.** Cycle I is stored as a zip whose SHA-256 is in the ledger. Only a human can unseal it, and only
  `run_test` can compute on it, once.
- **Append-only, hash-chained ledger.** `ledger/ledger.jsonl` is the lab notebook; any hand edit breaks
  `python -m sparklab.ledger verify`.
- **No clinical or causal claims.** The data are cross-sectional; outputs say which discrepancy to investigate next and
  which subgroup merits confirmatory re-measurement.

## Architecture

```
 Browser ──HTTP + SSE──▶ sparklab.api (FastAPI, :8787) ──HTTP──▶ Omnigent (:6767)
 (Next.js, frontend/)          │  reads the lab, records                │  runs the Supervisor + Scout,
                               │  human gates, starts sessions          │  Skeptic and Experimenter (lab.yaml)
                               ▼                                        ▼
                  lab files: board/  ledger/  prereg/  data/  ◀──── sparklab.tools (the only way agents compute)
```

- **`frontend/`** — Next.js 16 UI. Talks only to `sparklab.api`. When the API is not reachable it plays a scripted
  walkthrough of the same flow (`?mode=mock` forces it, `?mode=live` forces the API).
- **`backend/sparklab/api.py`** — HTTP API: reads the board, ledger, calcs and protocols, streams them to the UI as
  events (SSE), records the human gates, and starts / messages the study's Omnigent session. It never computes a
  statistic.
- **Omnigent** — orchestrates the four agents defined in `backend/lab.yaml`. Agents have no shell, network or file
  access: they can only call the functions in `sparklab/tools.py`.
- **Studies** — several labs under one backend (`backend/studies/<id>/`, created with **New study**). Each has its own
  ledger and protocols; the discovery data and the sealed hold-out are linked from the root lab.

## Repository layout

```
backend/
  lab.yaml                 Omnigent spec: Supervisor prompt, sub-agents, the tools each may call
  sparklab/
    config.py              paths, cycles, ADA thresholds (5.7 / 6.5 HbA1c; 100 / 126 mg/dL), MIN_CELL_N = 30
    data.py                NHANES download, merge on SEQN, derived columns, sealing of the hold-out
    stats.py               design-based weighted proportions and prevalence ratios, verdict rule
    tools.py               the functions agents can call, with the hold-out and power guards
    ledger.py              append-only hash-chained ledger, pre-registration, approval
    approve.py, unseal.py  human-only CLIs
    api.py, bridge.py      HTTP API for the UI; bridge folds the lab into UI events (never computes)
    studies.py             several labs under one backend
    fastlab.py             "fast mode" spec derived from lab.yaml
  board/                   expectation board (cited priors) + the seeded control
  ledger/, prereg/         the lab's records (append-only)
  tests/                   smoke test, unit tests, UI rehearsal
  docs/                    RUNBOOK (team, Spanish), AGENTS, PREREG/RESULTS templates
  Dockerfile, railway.json, deploy/start.sh   Railway deployment
frontend/                  Next.js UI (src/components/spark, src/lib/live = API client, src/lib/mock = scripted replay)
CLAUDE.md                  project rules for AI assistants working in this repo
```

## Run it locally

**Prerequisites:** Python 3.12+, Node.js 20.9+, git, and credentials for Omnigent's Claude harness (a Claude login on
this machine, or `ANTHROPIC_API_KEY`).

```bash
# 1. One virtualenv for Omnigent AND sparklab (Omnigent imports sparklab.tools from its own environment)
python3 -m venv .venv && source .venv/bin/activate
pip install omnigent
pip install -e "backend/[api]"
omnigent setup                                   # model credentials

# 2. Data (from backend/)
cd backend
python -m sparklab.data --cycle J                # discovery: download + derived columns
python -m sparklab.data --cycle I --seal         # hold-out: download, zip, SHA-256 into the ledger (not processed)
python tests/smoke_test.py                       # must print SMOKE TEST OK

# 3. Start the three processes (three terminals, venv active)
omnigent stop; omnigent start                    # Omnigent, from this venv
python -m sparklab.api                           # API on http://127.0.0.1:8787 (docs at /docs)
cd frontend && npm install && npm run dev        # UI on http://localhost:3000
```

Open <http://localhost:3000/?mode=live>, click **New study**, then **Start the lab**.

> If the CDC download fails with an SSL error on macOS, run
> `open "/Applications/Python 3.13/Install Certificates.command"` (adjust the version) and retry.

## Using the app

1. **New study** — give it a title and a question. A study needs the discovery data and the sealed hold-out (step 2
   above); otherwise creation is refused with the command to run.
2. **Objective → Start the lab.** For example:
   > Objective: find which discrepancy between self-reported diagnosis and HbA1c to investigate next among US adults
   > (NHANES 2017-2018 discovery). Every number must carry its calc_id. Stop and ask us before anything touches the
   > hold-out.
3. **Pick** — after the Scout's survey the Supervisor stops and you choose a discrepancy (E02 works well: the default
   hypotheses are built around it). If the Skeptic later finds that your pick is a definition error, the UI asks you
   to pick again.
4. **Propose / Attack** — watch the Experimenter draft rivals and the Skeptic attack them; the stage bar follows the
   agents. Use **Activity → Chat** to message the Supervisor if a run stalls.
5. **Approve** — type the first 8 characters of the **protocol's** SHA-256 (shown on the protocol card) and sign.
6. **Unseal** — type the first 8 characters of the **sealed file's** SHA-256 (shown in the panel's hint) and sign. This
   happens once per study.
7. **Tell the Supervisor: approved and unsealed** — the Experimenter runs the single hold-out test.
8. **Decision** — keep, kill or revise, with a note.

The same gates exist as terminal commands: `python -m sparklab.approve <prereg_id> --by <name>` and
`python -m sparklab.unseal`.

## Faster runs and testing

| What | Command (from `backend/`) | Notes |
|---|---|---|
| Unit + integration tests | `for t in tests/test_*.py; do python "$t"; done` | Synthetic data in temp folders; never touch the real ledger. |
| Smoke test | `python tests/smoke_test.py` | The whole demo spine on synthetic data. Must print `SMOKE TEST OK`. |
| UI rehearsal, no LLM | `python tests/rehearsal.py` | Builds a throwaway lab in `/tmp/spark-ui-rehearsal`, serves it on :8787 and plays the agents with the real tools; you click the gates. `--auto-gates` runs unattended, `--delay 0.5` speeds it up. |
| Fast mode, real agents | `SPARK_LAB_MODE=fast python -m sparklab.api` | Same gates and rules; at most 3 anomalies, 3 attacks and one debate round. `SPARK_FAST_MODEL=<model id>` pins a faster model. Start a **New study** so the session uses the fast spec. |

**Resetting a test:** start a **New study** (or `python -m sparklab.studies create "<title>"` and
`python -m sparklab.studies use <id>`). Never edit or truncate a ledger: it is append-only by design.

## Configuration

**Backend** (`sparklab.api` and the Omnigent host):

| Variable | Default | Purpose |
|---|---|---|
| `SPARK_API_HOST` / `SPARK_API_PORT` | `127.0.0.1` / `8787` | Where the API listens. |
| `SPARK_UI_ORIGIN` | — | Extra allowed CORS origin(s) for the UI, comma-separated (localhost:3000 is always allowed). |
| `SPARK_OMNIGENT_URL` | `http://127.0.0.1:6767` | Local Omnigent server. |
| `SPARK_OMNIGENT_SESSION` | — | Pin the default study to one Omnigent session id. |
| `SPARK_LAB_MODE` / `SPARK_FAST_MODEL` | `full` / — | `fast` to start new sessions with the fast spec; optional model pin. |
| `SPARKLAB_HOME` | `backend/` | Where the root lab's records live (board, ledger, prereg, data, studies). Set to a volume in deployments. |
| `SPARKLAB_ROOT` | — | Force every process onto one lab (tests, rehearsals). Overrides the active study. |
| `SPARKLAB_STUDIES_DIR` | `$SPARKLAB_HOME/studies` | Where additional studies live. |
| `ANTHROPIC_API_KEY` | — | API key for the Claude agents on a server (required for the hosted deployment; locally, your Claude login set up with `omnigent setup` is used). |
| `OMNIGENT_DATA_DIR` | Omnigent's default | Where Omnigent keeps sessions and history. |

**Frontend:**

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_SPARK_API_URL` | `http://127.0.0.1:8787` | Base URL of `sparklab.api`. Inlined at build time: redeploy after changing it. |

## Deployment: Vercel + Railway

The UI is a standard Next.js app and fits Vercel. The backend needs a process that keeps running (Omnigent and its
agents), long-lived connections (SSE) and a persistent disk (ledger, protocols, git commits), so it runs as one
Docker service with a volume on Railway.

```
Vercel (frontend/)  ──HTTPS──▶  Railway service (backend/Dockerfile)
                                  ├─ sparklab.api on $PORT (public)
                                  ├─ Omnigent on 127.0.0.1:6767 (internal only)
                                  └─ volume /data: lab records, NHANES data, Omnigent history
```



## Ground rules

These are enforced in code and described in full in [`CLAUDE.md`](CLAUDE.md):

1. Never read the hold-out outside the human unseal and `run_test`.
2. No number without a tool.
3. Pre-register before any test; never edit a registered protocol.
4. Never edit `ledger/ledger.jsonl` by hand.
5. Do not touch `board/control_seeded.json` (the seeded control).
6. Expected values on the board need a citation and a comparability label.
7. No clinical or causal claims.
8. ADA thresholds are fixed: normal HbA1c is < 5.7, not < 6.5.
9. Agents never get approve, unseal, shell or network tools.

## Troubleshooting

| Symptom | Fix |
|---|---|
| **New study** is refused: "the root lab is not ready" | Run the data commands it prints (`--cycle J`, `--cycle I --seal`) from `backend/`. |
| Unseal says "No seal entry in this study's ledger" | The study was created before the hold-out was sealed. Seal it, then create a new study. |
| Unseal says "Hash mismatch" | You typed the protocol's hash. Use the sealed file's hash from the panel's hint. |
| Starting the lab fails with "could not be imported" / tools not found | Omnigent is running from another environment: `omnigent stop`, activate `.venv`, `omnigent start`. |
| Agents write to the wrong study | The shared Omnigent runner follows `backend/studies/ACTIVE`: `python -m sparklab.studies use <id>` (or `--default`). |
| The UI shows the scripted walkthrough instead of your lab | The API is not reachable: start `python -m sparklab.api`, then open `/?mode=live`. |
| `tests/test_config.py` fails on the root path | An active study is set: `python -m sparklab.studies use --default`. |

## More documentation

- [`backend/docs/RUNBOOK.md`](backend/docs/RUNBOOK.md) — the team's run sheet for the live demo (Spanish).
- [`backend/docs/AGENTS.md`](backend/docs/AGENTS.md) — agents, tools and gates.
- [`backend/docs/PREREG_TEMPLATE.md`](backend/docs/PREREG_TEMPLATE.md) — protocol shape for `register_prereg`.
- [`backend/docs/RESULTS_TEMPLATE.md`](backend/docs/RESULTS_TEMPLATE.md) — how to write up results citing ledger ids and calc_ids.
- [`frontend/README.md`](frontend/README.md) — UI notes.
