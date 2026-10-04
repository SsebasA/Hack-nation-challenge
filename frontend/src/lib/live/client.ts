// Client for the SPARK Lab API (backend: python -m sparklab.api).
// The API never computes statistics. It reads a lab's records (board, ledger, calcs, protocols) and
// its Omnigent session, folds them into SparkEvents, records human gates (objective, pick, approve,
// unseal, decision) as human ledger entries, and drives the study's Omnigent session.

import type { GateId, LoggedEvent, StageId } from "@/lib/spark/types"

export const API_URL = (process.env.NEXT_PUBLIC_SPARK_API_URL ?? "http://127.0.0.1:8787").replace(/\/$/, "")

export type LabStatus = {
  root: string
  discovery: { cycle: string; label: string; processed: boolean }
  holdout: {
    cycle: string
    label: string
    sealed: boolean
    sealed_sha256: string | null
    unsealed: boolean
    looks: number
    max_looks: number
  }
  ledger: { entries: number; intact: boolean; message: string; calcs: number }
  preregs: { prereg_id: string; ledger_id: string; ts: string; approved: boolean }[]
  thresholds: { hba1c: [number, number]; glucose: [number, number]; min_cell_n: number }
}

export type SessionSummary = {
  id: string
  agent_name: string | null
  status: string | null
  title: string | null
  workspace: string | null
  updated_at: number | null
  children: { id: string; agent: string | null; busy: boolean | null; task_status: string | null; name: string | null }[]
}

export type OmnigentInfo = { url: string; reachable: boolean | null; error: string | null; agent_name: string }

export type StudyMeta = {
  id: string
  title: string
  question: string
  dataset: string
  holdout: string
  root: string
  is_default: boolean
  active: boolean
  created_at?: string
  created_by?: string
}

export type StudySummary = StudyMeta & {
  stage: StageId | null
  gate: GateId | null
  finished: boolean | null
  needs_confirmation: boolean | null
  objective: string | null
  ledger_entries: number | null
  calcs: number | null
  // `holdout` (inherited from StudyMeta) is the dataset label; this is the live seal/unseal state.
  holdout_status: LabStatus["holdout"] | null
  session: SessionSummary | null
  version: number
}

export type LiveSnapshot = {
  version?: number
  events: LoggedEvent[]
  gate: GateId | null
  finished: boolean
  prereg_id: string | null
  objective: string | null
  pick: string | null
  needs_confirmation: boolean
  stage?: StageId
  status: LabStatus
  session: SessionSummary | null
  study?: StudyMeta
  omnigent?: OmnigentInfo
  errors?: string[]
}

export type Health = {
  status: string
  root: string
  studies: number
  active_study: string
  omnigent: { url: string; reachable: boolean | null }
}

export type HumanEntryType = "anomaly" | "attack" | "hypothesis" | "decision" | "plan_update" | "note"

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function withTimeout<T>(run: (signal: AbortSignal) => Promise<T>, ms: number): Promise<T> {
  const ctl = new AbortController()
  const t = setTimeout(() => ctl.abort(), ms)
  try {
    return await run(ctl.signal)
  } finally {
    clearTimeout(t)
  }
}

async function json<T>(r: Response): Promise<T> {
  const body = await r.json().catch(() => ({}))
  if (!r.ok) {
    const detail = (body as { detail?: unknown })?.detail
    const msg = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d) => (d as { msg?: string }).msg ?? JSON.stringify(d)).join("; ") : `request failed (${r.status})`
    throw new ApiError(r.status, msg)
  }
  return body as T
}

const post = <T,>(url: string, body: unknown) =>
  fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((r) => json<T>(r))

export const studyUrl = (id: string) => `${API_URL}/studies/${encodeURIComponent(id)}`

export async function fetchHealth(timeoutMs = 1500): Promise<Health> {
  return withTimeout(async (signal) => json<Health>(await fetch(`${API_URL}/health`, { signal, cache: "no-store" })), timeoutMs)
}

export async function fetchStudies(timeoutMs = 2500): Promise<{ studies: StudySummary[]; active: string }> {
  return withTimeout(async (signal) => json(await fetch(`${API_URL}/studies`, { signal, cache: "no-store" })), timeoutMs)
}

export async function fetchStudy(id: string, timeoutMs = 2500): Promise<StudySummary> {
  return withTimeout(async (signal) => json(await fetch(studyUrl(id), { signal, cache: "no-store" })), timeoutMs)
}

export function createStudy(body: { title: string; question?: string; by?: string; copy_board?: boolean }) {
  return post<{ ok: true; study: StudySummary }>(`${API_URL}/studies`, body)
}

export async function fetchState(id: string): Promise<LiveSnapshot> {
  return json(await fetch(`${studyUrl(id)}/state`, { cache: "no-store" }))
}

// HTTP twin of `python -m sparklab.ledger add --type <type> --by <by> ...`.
export function postHumanLedger(id: string, entry: { type: HumanEntryType; payload: Record<string, unknown>; by?: string }) {
  return post<{ ok: true; entry: { id: string; hash: string } }>(`${studyUrl(id)}/human/ledger`, entry)
}

// Which discrepancy to pursue: human note + "Pursue E0x" to the Supervisor when a session exists.
export function postPick(id: string, body: { expectation_id: string; text?: string; by?: string }) {
  return post<{ ok: true; entry: { id: string }; sent: unknown; warning: string | null }>(`${studyUrl(id)}/pick`, body)
}

// Web twins of the terminal gates. Both require typing the first 8 characters of the recorded SHA-256.
export function postApprove(id: string, body: { prereg_id: string; by: string; hash_prefix: string }) {
  return post<{ ok: true; entry: { id: string } }>(`${studyUrl(id)}/approve`, body)
}

export function postUnseal(id: string, body: { by: string; sha256_prefix: string }) {
  return post<{ ok: true; entry: { id: string } }>(`${studyUrl(id)}/unseal`, body)
}

// Omnigent: start (or reuse) the study's spark_lab session from lab.yaml and send the objective.
export type StartSessionResult = {
  ok: true
  created: boolean
  session: { id: string; status: string | null; runner_id?: string | null; host_id?: string | null }
  active_study: string
  sent: unknown
  warning: string | null
  note: string
}

export function startSession(id: string, body: { objective?: string; by?: string }) {
  return post<StartSessionResult>(`${studyUrl(id)}/session`, body)
}

export function sendMessage(id: string, body: { text: string; by?: string; record?: boolean }) {
  return post<{ ok: true }>(`${studyUrl(id)}/session/message`, body)
}

// Server-sent snapshots. The API pushes the whole folded state whenever the lab changes, so the
// client never has to diff: it replaces its log and re-folds. EventSource reconnects on its own.
export function openEvents(
  id: string,
  handlers: {
    onSnapshot: (s: LiveSnapshot) => void
    onOpen?: () => void
    onError?: () => void
  },
): () => void {
  const es = new EventSource(`${studyUrl(id)}/events`)
  es.addEventListener("snapshot", (ev) => {
    try {
      handlers.onSnapshot(JSON.parse((ev as MessageEvent).data) as LiveSnapshot)
    } catch {
      // a malformed frame is ignored; the next snapshot replaces everything anyway
    }
  })
  es.onopen = () => handlers.onOpen?.()
  es.onerror = () => handlers.onError?.()
  return () => es.close()
}
