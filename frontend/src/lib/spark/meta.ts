import {
  FlaskConical,
  Lightbulb,
  Network,
  Scale,
  ShieldAlert,
  Sparkles,
  Swords,
  Telescope,
  User,
  Zap,
  type LucideIcon,
} from "lucide-react"
import type { Actor, GateId, StageId } from "./types"

export type StageMeta = {
  id: StageId
  letter: string
  name: string
  tagline: string
  description: string
  agents: Actor[]
  humanRole: string
  icon: LucideIcon
  // Full class strings so Tailwind can detect them.
  color: {
    text: string
    bg: string
    soft: string
    border: string
    ring: string
  }
}

export const STAGES: StageMeta[] = [
  {
    id: "surprise",
    letter: "S",
    name: "Surprise",
    tagline: "Where does the data disagree with what we expected?",
    description:
      "The Scout compares the discovery data against the expectation board. The Skeptic checks definitions so an error isn't mistaken for a finding.",
    agents: ["scout", "skeptic"],
    humanRole: "Set the objective and choose which discrepancy to pursue.",
    icon: Zap,
    color: {
      text: "text-amber-700",
      bg: "bg-amber-500",
      soft: "bg-amber-50",
      border: "border-amber-300",
      ring: "ring-amber-400",
    },
  },
  {
    id: "propose",
    letter: "P",
    name: "Propose",
    tagline: "Write rival explanations before testing any of them.",
    description:
      "The Scout writes competing hypotheses for the surprise, including a null and an artifact explanation, each with a testable prediction.",
    agents: ["scout", "supervisor"],
    humanRole: "Review the rival hypotheses.",
    icon: Lightbulb,
    color: {
      text: "text-sky-700",
      bg: "bg-sky-500",
      soft: "bg-sky-50",
      border: "border-sky-300",
      ring: "ring-sky-400",
    },
  },
  {
    id: "attack",
    letter: "A",
    name: "Attack",
    tagline: "Try to break each hypothesis before spending data on it.",
    description:
      "The Skeptic attacks every hypothesis: definition checks, confounding, alternatives, and the power gate, which rejects cells smaller than the minimum size.",
    agents: ["skeptic"],
    humanRole: "Watch the attacks. Nothing to approve yet.",
    icon: Swords,
    color: {
      text: "text-rose-700",
      bg: "bg-rose-500",
      soft: "bg-rose-50",
      border: "border-rose-300",
      ring: "ring-rose-400",
    },
  },
  {
    id: "run",
    letter: "R",
    name: "Run",
    tagline: "Pre-register, get approval, then test once on the sealed hold-out.",
    description:
      "The Experimenter drafts and registers the protocol (hash + commit). A human approves it and unseals the hold-out, then the test runs exactly once.",
    agents: ["experimenter"],
    humanRole: "Approve the pre-registration and unseal the hold-out.",
    icon: FlaskConical,
    color: {
      text: "text-violet-700",
      bg: "bg-violet-500",
      soft: "bg-violet-50",
      border: "border-violet-300",
      ring: "ring-violet-400",
    },
  },
  {
    id: "keepkill",
    letter: "K",
    name: "Keep / Kill",
    tagline: "Read the verdict and decide what to investigate next.",
    description:
      "The Supervisor summarizes the verdict. You decide whether to keep the line of inquiry, kill it, or revise it with a new pre-registration.",
    agents: ["supervisor"],
    humanRole: "Make the keep / kill / revise decision.",
    icon: Scale,
    color: {
      text: "text-emerald-700",
      bg: "bg-emerald-500",
      soft: "bg-emerald-50",
      border: "border-emerald-300",
      ring: "ring-emerald-400",
    },
  },
]

export const STAGE_BY_ID = Object.fromEntries(STAGES.map((s) => [s.id, s])) as Record<StageId, StageMeta>
export const STAGE_INDEX = Object.fromEntries(STAGES.map((s, i) => [s.id, i])) as Record<StageId, number>

export type ActorMeta = { name: string; role: string; icon: LucideIcon }

export const ACTORS: Record<Actor, ActorMeta> = {
  human: { name: "You", role: "Principal investigator", icon: User },
  supervisor: { name: "Supervisor", role: "Plans and delegates", icon: Network },
  scout: { name: "Scout", role: "Finds surprises, proposes", icon: Telescope },
  skeptic: { name: "Skeptic", role: "Attacks hypotheses", icon: ShieldAlert },
  experimenter: { name: "Experimenter", role: "Pre-registers and tests", icon: FlaskConical },
}

export const GATES: Record<GateId, { stage: StageId; title: string; cta: string }> = {
  objective: { stage: "surprise", title: "Set the study objective", cta: "Set objective" },
  "pick-surprise": { stage: "surprise", title: "Choose which discrepancy to pursue", cta: "Review discrepancy" },
  approve: { stage: "run", title: "Approve the pre-registration", cta: "Review protocol" },
  unseal: { stage: "run", title: "Unseal the hold-out", cta: "Go to unseal" },
  decision: { stage: "keepkill", title: "Decide: keep, kill or revise", cta: "Review verdict" },
}

export const SPARK_ICON = Sparkles
