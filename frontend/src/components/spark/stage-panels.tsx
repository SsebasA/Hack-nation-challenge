"use client"

import { useState } from "react"
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Circle,
  GitCommitHorizontal,
  KeyRound,
  Loader2,
  Lock,
  LockOpen,
  Merge,
  ShieldCheck,
  ShieldX,
  Skull,
  Sparkles,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { ACTORS, STAGE_BY_ID } from "@/lib/spark/meta"
import type { Attack, Decision, Expectation, GateId, Hypothesis, Prereg, StageId } from "@/lib/spark/types"
import type { ViewState } from "@/lib/spark/view"
import { DEFAULT_OBJECTIVE } from "@/lib/mock/diabetes-script"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ActorAvatar, Code, EmptyStage, MockValue } from "./primitives"
import { YourTurn } from "./your-turn"

const MIN_CELL_N = 30

type PanelProps = {
  view: ViewState
  blockedOn: GateId | null
  onResolve: (gate: GateId, input?: { text?: string; decision?: Decision }) => void
}

export function StagePanel({ stage, ...props }: PanelProps & { stage: StageId }) {
  return (
    <div className="space-y-5">
      <StageHeader stage={stage} />
      {stage === "surprise" && <SurprisePanel {...props} />}
      {stage === "propose" && <ProposePanel {...props} />}
      {stage === "attack" && <AttackPanel {...props} />}
      {stage === "run" && <RunPanel {...props} />}
      {stage === "keepkill" && <KeepKillPanel {...props} />}
    </div>
  )
}

function StageHeader({ stage }: { stage: StageId }) {
  const s = STAGE_BY_ID[stage]
  const Icon = s.icon
  return (
    <div className={cn("rounded-xl border p-4", s.color.soft, s.color.border)}>
      <div className="flex items-start gap-3">
        <span className={cn("inline-flex size-9 shrink-0 items-center justify-center rounded-lg text-white", s.color.bg)}>
          <Icon className="size-4.5" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-semibold">
            <span className={s.color.text}>{s.letter}</span> · {s.name}
          </h2>
          <p className="text-sm font-medium text-foreground/80">{s.tagline}</p>
          <p className="mt-1 text-sm text-muted-foreground">{s.description}</p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-black/5 pt-3 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Agents</span>
          {s.agents.map((a) => (
            <span key={a} className="inline-flex items-center gap-1 font-medium">
              <ActorAvatar actor={a} size="sm" className="size-5 [&>svg]:size-3" />
              {ACTORS[a].name}
            </span>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <ActorAvatar actor="human" size="sm" className="size-5 [&>svg]:size-3" />
          <span className="text-muted-foreground">You:</span>
          <span className="font-medium">{s.humanRole}</span>
        </div>
      </div>
    </div>
  )
}

function Section({ title, aside, children }: { title: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section>
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        {aside}
      </div>
      {children}
    </section>
  )
}

// ── Surprise ──────────────────────────────────────────────────

function SurprisePanel({ view, blockedOn, onResolve }: PanelProps) {
  const [objective, setObjective] = useState(DEFAULT_OBJECTIVE)

  return (
    <>
      {blockedOn === "objective" ? (
        <YourTurn title="Set the objective for this study. Agents start working once you confirm.">
          <Textarea value={objective} onChange={(e) => setObjective(e.target.value)} rows={3} className="bg-background" />
          <p className="mt-2 text-xs text-muted-foreground">
            Outputs are framed as &ldquo;which discrepancy to investigate next&rdquo; and &ldquo;which subgroup merits
            confirmatory re-measurement&rdquo;. Never screening, treatment or causal claims.
          </p>
          <div className="mt-3 flex justify-end">
            <Button onClick={() => onResolve("objective", { text: objective })}>
              <Sparkles /> Start the lab
            </Button>
          </div>
        </YourTurn>
      ) : (
        view.objective && (
          <Section title="Objective" aside={<span className="text-xs text-muted-foreground">Set by you</span>}>
            <p className="rounded-xl border bg-background p-3 text-sm leading-relaxed">{view.objective}</p>
          </Section>
        )
      )}

      <Section
        title="Expectation board"
        aside={<span className="text-xs text-muted-foreground">Priors vs. discovery cycle J</span>}
      >
        {view.expectations.length === 0 ? (
          <EmptyStage
            title="The Scout hasn't loaded the board yet"
            body="Once the objective is set, the Scout estimates every prior on the board and flags where the data disagrees."
          />
        ) : (
          <div className="overflow-hidden rounded-xl border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Expectation</th>
                  <th className="px-3 py-2 text-right font-medium">Expected</th>
                  <th className="px-3 py-2 text-right font-medium">Observed (J)</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {view.expectations.map((e) => (
                  <ExpectationRow key={e.id} e={e} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {blockedOn === "pick-surprise" && (
        <YourTurn title="E3 survived the Skeptic's definition check. Should the team pursue it?">
          <p className="mb-3 text-sm text-muted-foreground">
            E4 was flagged as a definition error, so it is not a candidate. Pursuing E3 moves the study to{" "}
            <b>Propose</b>, where the Scout writes rival explanations.
          </p>
          <div className="flex justify-end">
            <Button onClick={() => onResolve("pick-surprise")}>
              <Check /> Pursue E3
            </Button>
          </div>
        </YourTurn>
      )}
    </>
  )
}

const EXP_STATUS: Record<Expectation["status"], { label: string; className: string; icon: typeof Check }> = {
  pending: { label: "Estimating…", className: "text-muted-foreground", icon: Loader2 },
  consistent: { label: "Consistent", className: "text-emerald-700", icon: CheckCircle2 },
  discrepancy: { label: "Discrepancy", className: "text-amber-700", icon: AlertTriangle },
  definition_error: { label: "Definition error", className: "text-rose-700", icon: ShieldX },
}

function ExpectationRow({ e }: { e: Expectation }) {
  const st = EXP_STATUS[e.status]
  const Icon = st.icon
  return (
    <tr className={cn("align-top", e.status === "discrepancy" && "bg-amber-50/50", e.status === "definition_error" && "bg-rose-50/40")}>
      <td className="px-3 py-2.5">
        <div className="flex items-start gap-2">
          <span className="mt-0.5 font-mono text-xs text-muted-foreground">{e.id}</span>
          <div className="min-w-0">
            <p className={cn("font-medium", e.status === "definition_error" && "line-through decoration-rose-400")}>{e.label}</p>
            <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">
              {e.domain} → {e.outcome} · {e.weight}
            </p>
            <p className="text-[11px] text-muted-foreground">{e.source}</p>
            {e.note && (
              <p className="mt-1 inline-flex items-center gap-1 rounded bg-rose-100 px-1.5 py-0.5 text-[11px] font-medium text-rose-800">
                <ShieldX className="size-3" /> {e.note}
              </p>
            )}
          </div>
        </div>
      </td>
      <td className="px-3 py-2.5 text-right whitespace-nowrap">{e.expected && <MockValue>{e.expected}</MockValue>}</td>
      <td className="px-3 py-2.5 text-right whitespace-nowrap">
        {e.observed ? <MockValue className="font-medium">{e.observed}</MockValue> : <span className="text-muted-foreground">—</span>}
      </td>
      <td className="px-3 py-2.5 whitespace-nowrap">
        <span className={cn("inline-flex items-center gap-1 text-xs font-medium", st.className)}>
          <Icon className={cn("size-3.5", e.status === "pending" && "animate-spin")} />
          {st.label}
        </span>
      </td>
    </tr>
  )
}

// ── Propose ───────────────────────────────────────────────────

const KIND_LABEL: Record<Hypothesis["kind"], { label: string; className: string }> = {
  null: { label: "Null", className: "bg-zinc-100 text-zinc-700" },
  artifact: { label: "Artifact", className: "bg-orange-100 text-orange-800" },
  substantive: { label: "Substantive", className: "bg-sky-100 text-sky-800" },
}

function ProposePanel({ view }: PanelProps) {
  if (view.hypotheses.length === 0)
    return <EmptyStage title="No hypotheses yet" body="The Scout will propose rival explanations for the chosen discrepancy." />
  return (
    <Section title="Rival hypotheses for E3" aside={<span className="text-xs text-muted-foreground">Proposed by the Scout</span>}>
      <div className="grid gap-3 md:grid-cols-2">
        {view.hypotheses.map((h) => (
          <div key={h.id} className="rounded-xl border bg-background p-4 animate-in fade-in slide-in-from-bottom-1 duration-300">
            <div className="mb-2 flex items-center gap-2">
              <span className="font-mono text-xs font-semibold">{h.id}</span>
              <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-medium", KIND_LABEL[h.kind].className)}>
                {KIND_LABEL[h.kind].label}
              </span>
              {h.status !== "proposed" && (
                <span className="ml-auto">
                  <HypothesisStatusBadge status={h.status} />
                </span>
              )}
            </div>
            <p className="font-medium">{h.title}</p>
            <p className="mt-1 text-sm text-muted-foreground">{h.statement}</p>
            <div className="mt-3 rounded-lg bg-muted/60 p-2 text-xs">
              <span className="font-semibold">Predicts: </span>
              {h.prediction}
            </div>
          </div>
        ))}
      </div>
    </Section>
  )
}

// ── Attack ────────────────────────────────────────────────────

const H_STATUS: Record<Hypothesis["status"], { label: string; className: string; icon: typeof Check }> = {
  proposed: { label: "Waiting", className: "bg-muted text-muted-foreground", icon: Circle },
  under_attack: { label: "Under attack", className: "bg-rose-100 text-rose-800", icon: Loader2 },
  survives: { label: "Survives", className: "bg-emerald-100 text-emerald-800", icon: ShieldCheck },
  rival: { label: "Kept as rival", className: "bg-zinc-200 text-zinc-800", icon: ShieldCheck },
  killed: { label: "Killed", className: "bg-zinc-800 text-white", icon: Skull },
  blocked: { label: "Power gate", className: "bg-amber-100 text-amber-800", icon: Lock },
  merged: { label: "Merged", className: "bg-violet-100 text-violet-800", icon: Merge },
}

function HypothesisStatusBadge({ status }: { status: Hypothesis["status"] }) {
  const s = H_STATUS[status]
  const Icon = s.icon
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium", s.className)}>
      <Icon className={cn("size-3", status === "under_attack" && "animate-spin")} />
      {s.label}
    </span>
  )
}

const ATTACK_LABEL: Record<Attack["kind"], string> = {
  definition: "Definition check",
  power: "Power gate",
  confound: "Confounding",
  alternative: "Alternative explanation",
}

function AttackPanel({ view }: PanelProps) {
  if (view.maxStageIndex < 2)
    return <EmptyStage title="Attacks haven't started" body="The Skeptic attacks each hypothesis once the Scout has proposed them." />
  const order: Hypothesis["status"][] = ["survives", "rival", "under_attack", "proposed", "merged", "blocked", "killed"]
  const sorted = [...view.hypotheses].sort((a, b) => order.indexOf(a.status) - order.indexOf(b.status))
  const counts = {
    survives: view.hypotheses.filter((h) => h.status === "survives").length,
    out: view.hypotheses.filter((h) => ["killed", "blocked", "merged"].includes(h.status)).length,
  }
  return (
    <>
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Proposed" value={view.hypotheses.length} />
        <Stat label="Survived" value={counts.survives} className="text-emerald-700" />
        <Stat label="Killed / blocked / merged" value={counts.out} className="text-rose-700" />
      </div>
      <Section title="Hypotheses under attack">
        <div className="space-y-3">
          {sorted.map((h) => (
            <div
              key={h.id}
              className={cn(
                "rounded-xl border bg-background p-4 transition",
                h.status === "survives" && "border-emerald-300",
                ["killed", "blocked", "merged"].includes(h.status) && "opacity-75",
              )}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs font-semibold">{h.id}</span>
                <span className={cn("font-medium", h.status === "killed" && "line-through decoration-zinc-400")}>{h.title}</span>
                <span className="ml-auto">
                  <HypothesisStatusBadge status={h.status} />
                </span>
              </div>
              {h.outcomeNote && <p className="mt-1 text-sm text-muted-foreground">{h.outcomeNote}</p>}
              {h.attacks.length > 0 && (
                <ul className="mt-3 space-y-1.5">
                  {h.attacks.map((a, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      {a.passed ? (
                        <Check className="mt-0.5 size-4 shrink-0 text-emerald-600" />
                      ) : (
                        <X className="mt-0.5 size-4 shrink-0 text-rose-600" />
                      )}
                      <span>
                        <span className="font-medium">{ATTACK_LABEL[a.kind]}: </span>
                        <span className="text-muted-foreground">{a.text}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {h.cellN && <PowerGate n={Number(h.cellN)} />}
            </div>
          ))}
        </div>
      </Section>
    </>
  )
}

function Stat({ label, value, className }: { label: string; value: number; className?: string }) {
  return (
    <div className="rounded-xl border bg-background p-3">
      <div className={cn("text-2xl font-semibold tabular-nums", className)}>{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  )
}

function PowerGate({ n }: { n: number }) {
  const pass = n >= MIN_CELL_N
  // Scale so the threshold sits at 30% of the bar; cap large n.
  const pct = Math.min(100, (n / MIN_CELL_N) * 30)
  return (
    <div className="mt-3 rounded-lg bg-muted/50 p-2.5">
      <div className="mb-1.5 flex items-center justify-between text-xs">
        <span className="font-medium">Power gate (unweighted cell n)</span>
        <span className={cn("font-medium", pass ? "text-emerald-700" : "text-amber-700")}>
          n = <MockValue>{n}</MockValue> {pass ? "≥" : "<"} {MIN_CELL_N}
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-background">
        <div className={cn("h-full rounded-full", pass ? "bg-emerald-500" : "bg-amber-500")} style={{ width: `${pct}%` }} />
        <div className="absolute -top-1 h-4 w-px bg-foreground" style={{ left: "30%" }} />
      </div>
      <div className="mt-1 text-[10px] text-muted-foreground" style={{ paddingLeft: "calc(30% - 2.5rem)" }}>
        MIN_CELL_N = {MIN_CELL_N}
      </div>
    </div>
  )
}

// ── Run ───────────────────────────────────────────────────────

const PREREG_ORDER: Prereg["status"][] = ["draft", "registered", "approved", "unsealed", "tested"]

function RunPanel({ view, blockedOn, onResolve }: PanelProps) {
  const p = view.prereg
  if (!p) return <EmptyStage title="No protocol yet" body="The Experimenter drafts a pre-registration for the surviving hypothesis." />
  const reached = (s: Prereg["status"]) => PREREG_ORDER.indexOf(p.status) >= PREREG_ORDER.indexOf(s)

  const steps: { key: string; title: string; who: string; done: boolean; active: boolean; body?: React.ReactNode }[] = [
    {
      key: "draft",
      title: "Draft protocol",
      who: "Experimenter",
      done: reached("registered"),
      active: p.status === "draft",
    },
    {
      key: "register",
      title: "Register: hash + git commit",
      who: "Experimenter",
      done: reached("registered"),
      active: false,
      body: p.hash && (
        <div className="flex flex-wrap gap-3 font-mono text-[11px] text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <KeyRound className="size-3" /> {p.hash}
          </span>
          <span className="inline-flex items-center gap-1">
            <GitCommitHorizontal className="size-3" /> {p.commit}
          </span>
          <span className="rounded bg-amber-100 px-1 text-[9px] font-semibold text-amber-800">MOCK</span>
        </div>
      ),
    },
    {
      key: "approve",
      title: "Human approval",
      who: "You",
      done: reached("approved"),
      active: blockedOn === "approve",
      body:
        blockedOn === "approve" ? (
          <YourTurn title={`Review ${p.id} below and approve it. The protocol can't be edited after approval.`}>
            <p className="mb-3 text-xs text-muted-foreground">
              Terminal equivalent today: <code className="font-mono">python -m sparklab.approve {p.id} --by &lt;name&gt;</code>
            </p>
            <div className="flex justify-end">
              <Button onClick={() => onResolve("approve")}>
                <Check /> Approve {p.id}
              </Button>
            </div>
          </YourTurn>
        ) : p.approvedBy ? (
          <p className="text-xs text-muted-foreground">Approved by {p.approvedBy}</p>
        ) : null,
    },
    {
      key: "unseal",
      title: "Unseal hold-out (cycle I)",
      who: "You",
      done: reached("unsealed"),
      active: blockedOn === "unseal",
      body:
        blockedOn === "unseal" ? (
          <UnsealGate onConfirm={() => onResolve("unseal")} />
        ) : p.holdoutHash ? (
          <p className="inline-flex items-center gap-1 font-mono text-[11px] text-emerald-700">
            <LockOpen className="size-3" /> {p.holdoutHash}
            <span className="ml-1 rounded bg-amber-100 px-1 text-[9px] font-semibold text-amber-800">MOCK</span>
          </p>
        ) : (
          <p className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Lock className="size-3" /> Sealed. Agents cannot read it.
          </p>
        ),
    },
    {
      key: "test",
      title: "Run test once",
      who: "Experimenter",
      done: reached("tested"),
      active: p.status === "unsealed",
    },
  ]

  return (
    <>
      <Section title={`Pre-registration ${p.id}`}>
        <ol className="space-y-0">
          {steps.map((s, i) => (
            <li key={s.key} className="relative flex gap-3 pb-4 last:pb-0">
              {i < steps.length - 1 && <span className="absolute top-7 bottom-0 left-[13px] w-px bg-border" />}
              <span
                className={cn(
                  "relative z-10 inline-flex size-7 shrink-0 items-center justify-center rounded-full border text-xs",
                  s.done && "border-foreground bg-foreground text-background",
                  s.active && !s.done && "border-violet-400 bg-violet-50 text-violet-700",
                )}
              >
                {s.done ? <Check className="size-3.5" /> : s.active ? <Loader2 className="size-3.5 animate-spin" /> : i + 1}
              </span>
              <div className="min-w-0 flex-1 pt-1">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium">{s.title}</span>
                  <span className="text-xs text-muted-foreground">· {s.who}</span>
                </div>
                {s.body && <div className="mt-2">{s.body}</div>}
              </div>
            </li>
          ))}
        </ol>
      </Section>

      <Section title="Protocol" aside={<Badge variant="outline">Locked after registration</Badge>}>
        <dl className="divide-y rounded-xl border bg-background text-sm">
          {[
            ["Hypothesis", `${p.hypothesisId} vs. rival ${p.rivalId}`],
            ["Domain", <code key="d" className="font-mono text-xs">{p.domain}</code>],
            ["Outcome", <code key="o" className="font-mono text-xs">{p.outcome}</code>],
            ["Comparison", p.comparison],
            ["Weights", <code key="w" className="font-mono text-xs">{p.weight}</code>],
            ["Estimator", p.estimator],
            ["Decision rule", p.decisionRule],
          ].map(([k, v]) => (
            <div key={k as string} className="grid grid-cols-[120px_1fr] gap-3 px-3 py-2">
              <dt className="text-muted-foreground">{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      </Section>
    </>
  )
}

function UnsealGate({ onConfirm }: { onConfirm: () => void }) {
  const [open, setOpen] = useState(false)
  return (
    <YourTurn title="Unseal the hold-out so the approved test can run. This happens once.">
      <div className="flex justify-end">
        <Button onClick={() => setOpen(true)}>
          <LockOpen /> Unseal hold-out…
        </Button>
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Unseal hold-out cycle I?</DialogTitle>
            <DialogDescription>
              The SHA-256 of the sealed file is checked against the ledger before processing. The pre-registered test then
              runs exactly once. This can&apos;t be undone.
            </DialogDescription>
          </DialogHeader>
          <Code>python -m sparklab.unseal</Code>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              onClick={() => {
                setOpen(false)
                onConfirm()
              }}
            >
              Verify hash and unseal
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </YourTurn>
  )
}

// ── Keep / Kill ───────────────────────────────────────────────

const VERDICT_STYLE = {
  supported: { label: "Supported", className: "bg-emerald-100 text-emerald-800 border-emerald-300" },
  incompatible: { label: "Incompatible", className: "bg-rose-100 text-rose-800 border-rose-300" },
  inconclusive: { label: "Inconclusive", className: "bg-zinc-100 text-zinc-800 border-zinc-300" },
}

const DECISIONS: { id: Decision; label: string; body: string; icon: typeof Check }[] = [
  { id: "keep", label: "Keep", body: "Flag this subgroup for confirmatory re-measurement.", icon: ShieldCheck },
  { id: "revise", label: "Revise", body: "Register a new protocol. The current one stays as is.", icon: Merge },
  { id: "kill", label: "Kill", body: "Close this line of inquiry. The result stays in the ledger.", icon: Skull },
]

function KeepKillPanel({ view, blockedOn, onResolve }: PanelProps) {
  const v = view.verdict
  const [note, setNote] = useState("")
  if (!v) return <EmptyStage title="No verdict yet" body="The verdict appears after the pre-registered test runs on the hold-out." />
  const vs = VERDICT_STYLE[v.label]

  return (
    <>
      <Section title={`Verdict for ${v.preregId}`} aside={<span className="text-xs text-muted-foreground">Hold-out look 1 of 1</span>}>
        <div className="rounded-xl border bg-background p-4">
          <div className="flex flex-wrap items-center gap-3">
            <span className={cn("rounded-lg border px-3 py-1 text-lg font-semibold", vs.className)}>{vs.label}</span>
            <span className="rounded-sm bg-amber-100 px-1 text-[10px] font-semibold text-amber-800">MOCK</span>
            <div className="ml-auto text-sm">
              Prevalence ratio <MockValue className="font-semibold">{v.estimate}</MockValue>{" "}
              <span className="text-muted-foreground">
                95% CI <MockValue>{v.ci[0]}</MockValue>–<MockValue>{v.ci[1]}</MockValue>
              </span>
            </div>
          </div>
          <IntervalPlot {...v.plot} lo_label={v.ci[0]} hi_label={v.ci[1]} />
          <p className="mt-3 text-sm leading-relaxed">{v.interpretation}</p>
          <p className="mt-3 flex items-start gap-2 rounded-lg bg-muted/60 p-2.5 text-xs text-muted-foreground">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
            Cross-sectional survey data. This output says which subgroup merits confirmatory re-measurement. It is not
            screening advice, treatment advice, or a causal claim.
          </p>
        </div>
      </Section>

      {blockedOn === "decision" && (
        <YourTurn title="What should happen with this line of inquiry?">
          <div className="grid gap-2 md:grid-cols-3">
            {DECISIONS.map((d) => {
              const Icon = d.icon
              return (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => onResolve("decision", { decision: d.id, text: note })}
                  className="flex flex-col items-start gap-1 rounded-lg border bg-background p-3 text-left transition hover:border-foreground"
                >
                  <span className="inline-flex items-center gap-1.5 text-sm font-semibold">
                    <Icon className="size-4" /> {d.label}
                  </span>
                  <span className="text-xs text-muted-foreground">{d.body}</span>
                </button>
              )
            })}
          </div>
          <Textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Optional note for the ledger…"
            rows={2}
            className="mt-3 bg-background"
          />
        </YourTurn>
      )}

      {view.decision && (
        <div className="flex items-center gap-3 rounded-xl border border-emerald-300 bg-emerald-50 p-4">
          <CheckCircle2 className="size-5 text-emerald-700" />
          <div className="text-sm">
            <p className="font-semibold">
              Decision recorded: {DECISIONS.find((d) => d.id === view.decision!.decision)?.label}
            </p>
            <p className="text-muted-foreground">
              {view.decision.note || DECISIONS.find((d) => d.id === view.decision!.decision)?.body} Written to the ledger.
            </p>
          </div>
        </div>
      )}
    </>
  )
}

function IntervalPlot({ lo, point, hi, nullAt, lo_label, hi_label }: { lo: number; point: number; hi: number; nullAt: number; lo_label: string; hi_label: string }) {
  const pct = (x: number) => `${x * 100}%`
  return (
    <div className="mt-5 mb-1 px-2">
      <div className="relative h-10">
        {/* axis */}
        <div className="absolute top-1/2 right-0 left-0 h-px bg-border" />
        {/* null reference (PR = 1) */}
        <div className="absolute top-0 bottom-0 w-px border-l border-dashed border-muted-foreground" style={{ left: pct(nullAt) }} />
        <span className="absolute -top-4 -translate-x-1/2 text-[10px] text-muted-foreground" style={{ left: pct(nullAt) }}>
          PR = 1
        </span>
        {/* interval */}
        <div className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-emerald-500" style={{ left: pct(lo), width: pct(hi - lo) }} />
        <div className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background bg-emerald-700" style={{ left: pct(point) }} />
        <span className="absolute top-7 -translate-x-1/2 text-[10px] text-muted-foreground tabular-nums" style={{ left: pct(lo) }}>
          {lo_label}
        </span>
        <span className="absolute top-7 -translate-x-1/2 text-[10px] text-muted-foreground tabular-nums" style={{ left: pct(hi) }}>
          {hi_label}
        </span>
      </div>
    </div>
  )
}
