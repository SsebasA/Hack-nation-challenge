import type {
  Actor,
  ActivityType,
  AgentId,
  AgentStatus,
  Decision,
  Expectation,
  Hypothesis,
  LoggedEvent,
  Origin,
  Prereg,
  StageId,
  Verdict,
} from "./types"
import { STAGE_INDEX } from "./meta"

export type ActivityItem = {
  id: number
  at: number
  actor: Actor
  stage: StageId
  type: ActivityType
  title: string
  detail?: string
  code?: string
}

export type LedgerItem = { seq: number; at: number; type: string; origin: Origin; summary: string; hash: string; id?: string }
export type ChatItem = { id: number; at: number; from: Actor; text: string }

export type ViewState = {
  stage: StageId
  maxStageIndex: number
  agents: Record<AgentId, { status: AgentStatus; task?: string }>
  objective?: string
  expectations: Expectation[]
  hypotheses: Hypothesis[]
  prereg?: Prereg
  // One verdict per pre-registered test (the mock has one; a real protocol has two or three).
  verdicts: Verdict[]
  decision?: { decision: Decision; note?: string }
  activity: ActivityItem[]
  ledger: LedgerItem[]
  chat: ChatItem[]
}

function upsert<T extends { id: string }>(list: T[], item: Partial<T> & { id: string }, defaults: T): T[] {
  const i = list.findIndex((x) => x.id === item.id)
  if (i === -1) return [...list, { ...defaults, ...item } as T]
  const next = list.slice()
  next[i] = { ...next[i], ...item }
  return next
}

export function initialView(): ViewState {
  return {
    stage: "surprise",
    maxStageIndex: 0,
    agents: {
      supervisor: { status: "idle" },
      scout: { status: "idle" },
      skeptic: { status: "idle" },
      experimenter: { status: "idle" },
    },
    expectations: [],
    hypotheses: [],
    verdicts: [],
    activity: [],
    ledger: [],
    chat: [],
  }
}

export function foldView(log: LoggedEvent[]): ViewState {
  const v = initialView()
  log.forEach(({ at, event: e }, idx) => {
    switch (e.kind) {
      case "stage":
        v.stage = e.stage
        v.maxStageIndex = Math.max(v.maxStageIndex, STAGE_INDEX[e.stage])
        break
      case "agent":
        v.agents = { ...v.agents, [e.agent]: { status: e.status, task: e.task } }
        break
      case "activity":
        v.activity.push({ id: idx, at, actor: e.actor, stage: e.stage, type: e.type, title: e.title, detail: e.detail, code: e.code })
        break
      case "chat":
        v.chat.push({ id: idx, at, from: e.from, text: e.text })
        break
      case "ledger":
        v.ledger.push({ seq: v.ledger.length + 1, at, type: e.type, origin: e.origin, summary: e.summary, hash: e.hash, id: e.id })
        break
      case "objective":
        v.objective = e.text
        break
      case "expectation":
        v.expectations = upsert(v.expectations, e.item, {
          id: e.item.id,
          label: "",
          domain: "",
          outcome: "",
          weight: "wt_mec",
          source: "",
          status: "pending",
        })
        break
      case "hypothesis":
        v.hypotheses = upsert(v.hypotheses, e.item, {
          id: e.item.id,
          kind: "substantive",
          title: "",
          statement: "",
          prediction: "",
          status: "proposed",
          attacks: [],
        })
        break
      case "attack":
        v.hypotheses = v.hypotheses.map((h) =>
          h.id === e.hypothesisId ? { ...h, attacks: [...h.attacks, e.attack] } : h,
        )
        break
      case "prereg": {
        // A patch may omit the id; the first patch must carry it (the mock and the bridge both do).
        const merged = { ...(v.prereg ?? { id: "", status: "draft" as const }), ...e.patch } as Prereg
        v.prereg = merged
        break
      }
      case "verdict": {
        const key = e.item.hypothesisId ?? e.item.preregId
        const i = v.verdicts.findIndex((x) => (x.hypothesisId ?? x.preregId) === key)
        if (i === -1) v.verdicts = [...v.verdicts, e.item]
        else {
          const next = v.verdicts.slice()
          next[i] = e.item
          v.verdicts = next
        }
        break
      }
      case "decision":
        v.decision = { decision: e.decision, note: e.note }
        break
    }
  })
  return v
}

export function formatClock(ms: number) {
  const s = Math.floor(ms / 1000)
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`
}
