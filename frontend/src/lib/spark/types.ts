// Domain types for the SPARK Lab UI.
// The event shapes are designed so a future backend (Omnigent stream + ledger)
// can replace the mock script without changing the components.

export type StageId = "surprise" | "propose" | "attack" | "run" | "keepkill"
export type AgentId = "supervisor" | "scout" | "skeptic" | "experimenter"
export type Actor = AgentId | "human"
export type AgentStatus = "idle" | "working" | "waiting" | "done"
export type GateId = "objective" | "pick-surprise" | "approve" | "unseal" | "decision"
export type Origin = "human" | `agent:${AgentId}`

export type Expectation = {
  id: string
  label: string
  domain: string
  outcome: string
  weight: "wt_mec" | "wt_fast"
  source: string
  expected?: string
  observed?: string
  status: "pending" | "consistent" | "discrepancy" | "definition_error"
  note?: string
}

export type AttackKind = "definition" | "power" | "confound" | "alternative"

export type Attack = {
  kind: AttackKind
  text: string
  passed: boolean
}

export type HypothesisStatus =
  | "proposed"
  | "under_attack"
  | "survives"
  | "rival"
  | "killed"
  | "blocked"
  | "merged"

export type Hypothesis = {
  id: string
  kind: "artifact" | "substantive" | "null"
  title: string
  statement: string
  prediction: string
  status: HypothesisStatus
  attacks: Attack[]
  cellN?: string
  outcomeNote?: string
}

export type PreregStatus = "draft" | "registered" | "approved" | "unsealed" | "tested"

export type Prereg = {
  id: string
  hypothesisId: string
  rivalId: string
  domain: string
  outcome: string
  comparison: string
  weight: string
  estimator: string
  decisionRule: string
  status: PreregStatus
  hash?: string
  commit?: string
  approvedBy?: string
  holdoutHash?: string
}

export type Verdict = {
  preregId: string
  label: "supported" | "incompatible" | "inconclusive"
  estimate: string
  ci: [string, string]
  // Positions on a 0–1 axis for the interval plot (mock only).
  plot: { lo: number; point: number; hi: number; nullAt: number }
  interpretation: string
}

export type Decision = "keep" | "kill" | "revise"

export type ActivityType = "thought" | "tool_call" | "tool_result" | "handoff" | "flag" | "gate" | "human"

export type SparkEvent =
  | { kind: "stage"; stage: StageId }
  | { kind: "agent"; agent: AgentId; status: AgentStatus; task?: string }
  | {
      kind: "activity"
      actor: Actor
      stage: StageId
      type: ActivityType
      title: string
      detail?: string
      code?: string
    }
  | { kind: "chat"; from: Actor; text: string }
  | { kind: "ledger"; type: string; origin: Origin; summary: string; hash: string }
  | { kind: "objective"; text: string }
  | { kind: "expectation"; item: Partial<Expectation> & { id: string } }
  | { kind: "hypothesis"; item: Partial<Hypothesis> & { id: string } }
  | { kind: "attack"; hypothesisId: string; attack: Attack }
  | { kind: "prereg"; patch: Partial<Prereg> }
  | { kind: "verdict"; item: Verdict }
  | { kind: "decision"; decision: Decision; note?: string }

export type ScriptStep = {
  delay: number
  events: SparkEvent[]
  gate?: GateId
}

export type LoggedEvent = { at: number; event: SparkEvent }

export type Study = {
  id: string
  title: string
  question: string
  dataset: string
  holdout: string
  interactive: boolean
  // Static summary for the studies list.
  stage: StageId
  needsHuman?: string
  updated: string
}
