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

export type LedgerItem = { seq: number; at: number; type: string; origin: Origin; summary: string; hash: string }
export type ChatItem = { id: number; at: number; from: Actor; text: string }

export type ViewState = {
  stage: StageId
  maxStageIndex: number
  agents: Record<AgentId, { status: AgentStatus; task?: string }>
  objective?: string
  expectations: Expectation[]
  hypotheses: Hypothesis[]
  prereg?: Prereg
  verdict?: Verdict
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
        v.ledger.push({ seq: v.ledger.length + 1, at, type: e.type, origin: e.origin, summary: e.summary, hash: e.hash })
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
      case "prereg":
        v.prereg = { ...(v.prereg as Prereg), ...e.patch }
        break
      case "verdict":
        v.verdict = e.item
        break
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
