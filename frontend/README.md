This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Running against the SPARK Lab backend

The workspace for the real study is driven by the SPARK Lab API (`backend/sparklab/api.py`) when it is
reachable, and falls back to a scripted walkthrough of the same flow when it is not.

```bash
# backend (from the repo root, same venv as omnigent)
pip install -e "backend/[api]"
cd backend && python -m sparklab.api        # http://127.0.0.1:8787

# frontend
cd frontend && npm install && npm run dev   # http://localhost:3000
```

- `NEXT_PUBLIC_SPARK_API_URL` overrides the API location (default `http://127.0.0.1:8787`).
- `?mode=mock` forces the scripted replay; `?mode=live` forces the API even if it is down.
- The UI never computes a statistic: every number carries its `calc_id`. What it can do, all recorded in the
  ledger with `origin: human` and your name:
  - start the lab (uploads `lab.yaml` to Omnigent as the agent team and sends the objective), message the Supervisor;
  - pick which discrepancy to pursue after the Scout/Skeptic pass;
  - approve the pre-registration and unseal the hold-out with the same friction as the CLIs (type the first 8
    characters of the recorded SHA-256, sign with your name); tell the Supervisor to run the single hold-out test;
  - record the keep / kill / revise decision;
  - create studies (`New study`): a new lab folder under `backend/studies/` served by the same API.
- Omnigent must run from the same venv as `sparklab` (`omnigent stop && source .venv/bin/activate && omnigent start`),
  otherwise it cannot resolve the `callable:` tools of `lab.yaml` when the UI starts a session.
- Live code lives in `src/lib/live/` (API client, probe, `useLiveStudy`); the mock stays in `src/lib/mock/`.

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

