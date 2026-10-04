"use client"

import { useState } from "react"
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Circle,
  Copy,
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
  Terminal,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { ACTORS, STAGE_BY_ID } from "@/lib/spark/meta"
import { useDataSource } from "@/lib/spark/data-source"
import type { Attack, Decision, Expectation, GateId, Hypothesis, Prereg, StageId, Verdict } from "@/lib/spark/types"
import type { ViewState } from "@/lib/spark/view"
import type { GateInput, LiveStudy } from "@/lib/live/use-live-study"
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
import { ActorAvatar, Code, EmptyStage, MockTag, MockValue } from "./primitives"
import { YourTurn } from "./your-turn"

const MIN_CELL_N = 30

type PanelProps = {
  view: ViewState
  blockedOn: GateId | null
  onResolve: (gate: GateId, input?: GateInput) => void
  // Present when the workspace is driven by the SPARK Lab API.
  live: LiveStudy | null
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

// Who is acting, recorded in every human ledger entry (`--by` in the CLI).
function ByField({ live }: { live: LiveStudy }) {
  return (
    <label className="flex items-center gap-2 text-xs">
      <span className="text-muted-foreground">Recorded as</span>
      <input
        value={live.by}
        onChange={(e) => live.setBy(e.target.value)}
        placeholder="your name"
        className="h-7 w-36 rounded-md border bg-background px-2 text-xs outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
      />
    </label>
  )
}

function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false)
  return (
    <Button
      size="sm"
      variant="outline"
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(() => {
          setDone(true)
          setTimeout(() => setDone(false), 1500)
        })
      }}
    >
      {done ? <Check /> : <Copy />} {done ? "Copied" : "Copy"}
    </Button>
  )
}

// A signed human gate with the CLI's friction: the human types the first 8 characters of the recorded
// SHA-256 (protocol hash for approve, sealed-file hash for unseal). The terminal command stays as the
// alternative; either way the bridge closes the gate from the ledger entry.
function HashGate({
  live,
  title,
  why,
  hashLabel,
  hint,
  cta,
  command,
  onConfirm,
}: {
  live: LiveStudy
  title: string
  why: string
  hashLabel: string
  hint?: string
  cta: string
  command: string
  onConfirm: (hashPrefix: string) => void
}) {
  const [prefix, setPrefix] = useState("")
  const [showCli, setShowCli] = useState(false)
  const ok = prefix.trim().length >= 8 && live.by.trim().length > 0
  return (
    <YourTurn title={title}>
      <p className="mb-3 text-xs text-muted-foreground">{why}</p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="block text-xs">
          <span className="text-muted-foreground">{hashLabel}</span>
          <input
            value={prefix}
            onChange={(e) => setPrefix(e.target.value)}
            placeholder="first 8 characters"
            spellCheck={false}
            className="mt-1 block h-8 w-44 rounded-md border bg-background px-2 font-mono text-xs outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          />
        </label>
        <label className="block text-xs">
          <span className="text-muted-foreground">Signed by</span>
          <input
            value={live.by}
            onChange={(e) => live.setBy(e.target.value)}
            placeholder="your name"
            className="mt-1 block h-8 w-36 rounded-md border bg-background px-2 text-xs outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          />
        </label>
        <Button onClick={() => onConfirm(prefix)} disabled={!ok || live.pending} className="ml-auto">
          {live.pending ? <Loader2 className="animate-spin" /> : <KeyRound />} {cta}
        </Button>
      </div>
      {hint && <p className="mt-2 text-[11px] text-muted-foreground">{hint}</p>}
      <button type="button" onClick={() => setShowCli((v) => !v)} className="mt-3 inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground">
        <Terminal className="size-3" /> {showCli ? "Hide" : "Prefer the terminal?"}
      </button>
      {showCli && (
        <div className="mt-1.5 flex items-center gap-2">
          <Code className="flex-1">{command}</Code>
          <CopyButton text={command} />
        </div>
      )}
    </YourTurn>
  )
}

// ── Surprise ──────────────────────────────────────────────────

function SurprisePanel({ view, blockedOn, onResolve, live }: PanelProps) {
  const source = useDataSource()
  const [objective, setObjective] = useState(source === "live" ? "" : DEFAULT_OBJECTIVE)

  return (
    <>
      {blockedOn === "objective" ? (
        <YourTurn title="Set the objective for this study. Agents start working once you confirm.">
          <Textarea
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
            rows={3}
            className="bg-background"
            placeholder={live ? "Objective: find which discrepancy between self-reported diagnosis and HbA1c to investigate next…" : undefined}
          />
          <p className="mt-2 text-xs text-muted-foreground">
            Outputs are framed as &ldquo;which discrepancy to investigate next&rdquo; and &ldquo;which subgroup merits
            confirmatory re-measurement&rdquo;. Never screening, treatment or causal claims.
          </p>
          {live && (
            <div className="mt-3 rounded-lg border bg-background p-3 text-xs text-muted-foreground">
              {live.snapshot?.omnigent?.reachable ? (
                <>
                  <p className="mb-1 inline-flex items-center gap-1.5 font-medium text-foreground">
                    <Sparkles className="size-3.5" /> Starting the lab uploads <code className="font-mono">lab.yaml</code> as the agent team
                    {live.snapshot?.session ? " (reusing this study's session)" : ""}, sends this objective to the Supervisor and
                    records it in the ledger.
                  </p>
                  <p>
                    The shared runner then works on this study (<code className="font-mono">studies/ACTIVE</code>). Terminal equivalent:{" "}
                    <code className="font-mono">omnigent run lab.yaml -p &quot;…&quot;</code> from the study folder.
                  </p>
                </>
              ) : (
                <>
                  <p className="mb-1.5 inline-flex items-center gap-1.5 font-medium text-foreground">
                    <Terminal className="size-3.5" /> Omnigent is not reachable; the objective will be recorded and you start the agents by hand:
                  </p>
                  <Code>{`omnigent run lab.yaml -p "${(objective || "<objective>").replace(/"/g, "'")}"`}</Code>
                </>
              )}
            </div>
          )}
          <div className="mt-3 flex items-center justify-between gap-3">
            {live ? <ByField live={live} /> : <span />}
            <Button onClick={() => onResolve("objective", { text: objective })} disabled={live?.pending}>
              {live?.pending ? <Loader2 className="animate-spin" /> : <Sparkles />} Start the lab
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

      {blockedOn === "pick-surprise" &&
        (live ? (
          <PickSurprise view={view} live={live} onResolve={onResolve} />
        ) : (
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
        ))}
    </>
  )
}

// Live: the board has been evaluated and the Supervisor is idle; the humans choose the discrepancy.
function PickSurprise({ view, live, onResolve }: { view: ViewState; live: LiveStudy; onResolve: PanelProps["onResolve"] }) {
  const candidates = view.expectations.filter((e) => e.status !== "definition_error")
  const order: Expectation["status"][] = ["discrepancy", "consistent", "pending"]
  const sorted = [...candidates].sort((a, b) => order.indexOf(a.status) - order.indexOf(b.status))
  const [choice, setChoice] = useState<string>(sorted.find((e) => e.status === "discrepancy")?.id ?? sorted[0]?.id ?? "")
  const [why, setWhy] = useState("")
  return (
    <YourTurn title="Choose which discrepancy the team pursues. Definition errors are not candidates.">
      <div className="space-y-1.5">
        {sorted.map((e) => (
          <label
            key={e.id}
            className={cn(
              "flex cursor-pointer items-start gap-3 rounded-lg border bg-background p-2.5 text-sm transition hover:border-foreground/40",
              choice === e.id && "border-foreground",
            )}
          >
            <input type="radio" name="pick" value={e.id} checked={choice === e.id} onChange={() => setChoice(e.id)} className="mt-1" />
            <span className="min-w-0 flex-1">
              <span className="font-mono text-xs text-muted-foreground">{e.id}</span> <span className="font-medium">{e.label}</span>
              <span className="mt-0.5 block text-xs text-muted-foreground">
                expected {e.expected ?? "—"} · observed {e.observed ?? "—"}
                {e.observedCi?.[0] && ` (95% CI ${e.observedCi[0]}–${e.observedCi[1]})`} ·{" "}
                <span className={e.status === "discrepancy" ? "text-amber-700" : ""}>{e.status}</span>
              </span>
            </span>
          </label>
        ))}
      </div>
      <Textarea value={why} onChange={(e) => setWhy(e.target.value)} rows={2} placeholder="Why this one (optional, goes to the ledger and the Supervisor)…" className="mt-3 bg-background" />
      <div className="mt-3 flex items-center justify-between gap-3">
        <ByField live={live} />
        <Button onClick={() => onResolve("pick-surprise", { expectationId: choice, text: why })} disabled={!choice || live.pending}>
          {live.pending ? <Loader2 className="animate-spin" /> : <Check />} Pursue {choice || "…"}
        </Button>
      </div>
    </YourTurn>
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
            {e.comparability && <p className="text-[11px] text-muted-foreground/80">Comparability: {e.comparability}</p>}
            {e.note && (
              <p className="mt-1 inline-flex items-center gap-1 rounded bg-rose-100 px-1.5 py-0.5 text-[11px] font-medium text-rose-800">
                <ShieldX className="size-3" /> {e.note}
              </p>
            )}
          </div>
        </div>
      </td>
      <td className="px-3 py-2.5 text-right whitespace-nowrap">
        {e.expected ? <MockValue>{e.expected}</MockValue> : <span className="text-muted-foreground">no cited value</span>}
      </td>
      <td className="px-3 py-2.5 text-right whitespace-nowrap">
        {e.observed ? (
          <div>
            <MockValue className="font-medium" calcId={e.calcId}>
              {e.observed}
            </MockValue>
            {e.observedCi && e.observedCi[0] && (
              <div className="text-[11px] text-muted-foreground tabular-nums">
                95% CI {e.observedCi[0]}–{e.observedCi[1]}
              </div>
            )}
          </div>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
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

function ProposePanel({ view, live }: PanelProps) {
  if (view.hypotheses.length === 0)
    return <EmptyStage title="No hypotheses yet" body={live ? "The Experimenter's hypothesis entries and the registered protocol appear here." : "The Scout will propose rival explanations for the chosen discrepancy."} />
  return (
    <Section
      title={live ? "Rival hypotheses" : "Rival hypotheses for E3"}
      aside={<span className="text-xs text-muted-foreground">{live ? "From the ledger and the registered protocol" : "Proposed by the Scout"}</span>}
    >
      <div className="grid gap-3 md:grid-cols-2">
        {view.hypotheses.map((h) => (
          <div key={h.id} className="rounded-xl border bg-background p-4 animate-in fade-in slide-in-from-bottom-1 duration-300">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs font-semibold">{h.id}</span>
              <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-medium", KIND_LABEL[h.kind].className)}>
                {KIND_LABEL[h.kind].label}
              </span>
              {h.origin && <span className="rounded border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">{h.origin}</span>}
              {h.status !== "proposed" && (
                <span className="ml-auto">
                  <HypothesisStatusBadge status={h.status} />
                </span>
              )}
            </div>
            <p className="font-medium">{h.title}</p>
            {h.statement && h.statement !== h.title && <p className="mt-1 text-sm text-muted-foreground">{h.statement}</p>}
            {h.prediction && (
              <div className="mt-3 rounded-lg bg-muted/60 p-2 text-xs">
                <span className="font-semibold">Predicts: </span>
                {h.prediction}
              </div>
            )}
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
    return <EmptyStage title="Attacks haven't started" body="The Skeptic attacks each hypothesis once they have been proposed." />
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

function RunPanel({ view, blockedOn, onResolve, live }: PanelProps) {
  const p = view.prereg
  if (!p) return <EmptyStage title="No protocol yet" body="The Experimenter drafts a pre-registration for the surviving hypothesis." />
  const reached = (s: Prereg["status"]) => PREREG_ORDER.indexOf(p.status) >= PREREG_ORDER.indexOf(s)
  const by = live?.by || "<name>"

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
          <span className="inline-flex items-center gap-1 break-all">
            <KeyRound className="size-3 shrink-0" /> {p.hash}
          </span>
          <span className="inline-flex items-center gap-1">
            <GitCommitHorizontal className="size-3" /> {p.commit}
          </span>
          {p.ledgerId && <span className="rounded bg-muted px-1 text-[9px] font-semibold">ledger {p.ledgerId}</span>}
          <MockTag />
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
          live ? (
            <HashGate
              live={live}
              title={`Review ${p.id} below and approve it. The protocol can't be edited after approval.`}
              why="Approval is human-only and signed. Read the protocol's SHA-256 above and type its first 8 characters, exactly as the terminal CLI asks."
              hashLabel="Protocol SHA-256 prefix"
              hint={p.hash ? `The hash shown above starts with ${p.hash.replace(/^sha256:/, "").slice(0, 3)}…` : undefined}
              cta={`Approve ${p.id}`}
              command={`python -m sparklab.approve ${p.id} --by ${by}`}
              onConfirm={(hashPrefix) => onResolve("approve", { hashPrefix })}
            />
          ) : (
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
          )
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
          live ? (
            <HashGate
              live={live}
              title="Unseal the hold-out so the approved test can run. This happens once and can't be undone."
              why="The sealed file's SHA-256 is checked against the seal entry in the ledger before processing; only run_test can compute on it afterwards. Type the first 8 characters of the recorded hash."
              hashLabel="Sealed-file SHA-256 prefix"
              hint={
                live.snapshot?.status.holdout.sealed_sha256
                  ? `Recorded at seal time (ledger): ${live.snapshot.status.holdout.sealed_sha256}`
                  : "No seal entry in this study's ledger yet."
              }
              cta="Verify hash and unseal"
              command="python -m sparklab.unseal"
              onConfirm={(hashPrefix) => onResolve("unseal", { hashPrefix })}
            />
          ) : (
            <UnsealGate onConfirm={() => onResolve("unseal")} />
          )
        ) : p.holdoutHash ? (
          <p className="inline-flex items-center gap-1 font-mono text-[11px] text-emerald-700 break-all">
            <LockOpen className="size-3 shrink-0" /> {p.holdoutHash}
            <MockTag className="ml-1" />
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
      body:
        p.status === "unsealed" && live ? (
          <div className="rounded-lg border bg-background p-3">
            <p className="text-xs text-muted-foreground">
              The Supervisor waits for your word. Once told, the Experimenter runs{" "}
              <code className="font-mono">run_test({p.id}, cycle=&quot;I&quot;)</code> exactly once; the look budget is{" "}
              {live.snapshot?.status.holdout.max_looks ?? 1}.
            </p>
            <div className="mt-2 flex items-center justify-between gap-3">
              <ByField live={live} />
              <Button size="sm" onClick={() => void live.confirmHoldout()} disabled={live.pending || !live.snapshot?.session}>
                {live.pending ? <Loader2 className="animate-spin" /> : <LockOpen />} Tell the Supervisor: approved and unsealed
              </Button>
            </div>
            {!live.snapshot?.session && <p className="mt-1 text-[11px] text-amber-700">No Supervisor session to notify.</p>}
          </div>
        ) : undefined,
    },
  ]

  const rows: [string, React.ReactNode][] = [
    ["Hypothesis", p.hypothesisId ? `${p.hypothesisId}${p.rivalId ? ` vs. rival ${p.rivalId}` : ""}` : "—"],
    ["Domain", p.domain ? <code key="d" className="font-mono text-xs">{p.domain}</code> : "—"],
    ["Outcome", p.outcome ? <code key="o" className="font-mono text-xs">{p.outcome}</code> : "—"],
    ["Comparison", p.comparison ?? "—"],
    ["Weights", p.weight ? <code key="w" className="font-mono text-xs">{p.weight}</code> : "—"],
    ["Estimator", p.estimator ?? "—"],
    ["Decision rule", p.decisionRule ?? "—"],
  ]

  return (
    <>
      <Section title={`Pre-registration ${p.id}`} aside={p.title && <span className="text-xs text-muted-foreground">{p.title}</span>}>
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
        {p.question && <p className="mb-2 text-sm text-muted-foreground">{p.question}</p>}
        <dl className="divide-y rounded-xl border bg-background text-sm">
          {rows.map(([k, v]) => (
            <div key={k} className="grid grid-cols-[120px_1fr] gap-3 px-3 py-2">
              <dt className="text-muted-foreground">{k}</dt>
              <dd className="min-w-0 break-words">{v}</dd>
            </div>
          ))}
        </dl>
        {p.tests && p.tests.length > 0 && (
          <div className="mt-3 overflow-hidden rounded-xl border bg-background">
            <table className="w-full text-xs">
              <thead className="bg-muted/50 text-left text-muted-foreground">
                <tr>
                  <th className="px-3 py-1.5 font-medium">Test</th>
                  <th className="px-3 py-1.5 font-medium">Kind</th>
                  <th className="px-3 py-1.5 font-medium">Domain → outcome (group)</th>
                  <th className="px-3 py-1.5 text-right font-medium">Prediction / null</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {p.tests.map((t) => (
                  <tr key={t.id} className="align-top">
                    <td className="px-3 py-1.5 font-mono font-semibold whitespace-nowrap">
                      {t.id}
                      {t.origin && <div className="font-normal text-[10px] text-muted-foreground">{t.origin}</div>}
                    </td>
                    <td className="px-3 py-1.5 whitespace-nowrap">{t.kind}</td>
                    <td className="px-3 py-1.5 font-mono">
                      {t.domain || "True"} → {t.outcome}
                      {t.group && <span className="text-muted-foreground"> ({t.group})</span>}
                    </td>
                    <td className="px-3 py-1.5 text-right whitespace-nowrap tabular-nums">
                      {t.prediction}
                      {t.null != null && <span className="text-muted-foreground"> · null {t.null}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {p.rivals && p.rivals.length > 0 && (
          <ul className="mt-3 space-y-1.5 text-xs">
            {p.rivals.map((r) => (
              <li key={r.id} className="rounded-lg border bg-background p-2.5">
                <span className="font-mono font-semibold">{r.id}</span>
                {r.statement && <span className="text-muted-foreground"> — {r.statement}</span>}
                {r.floor && (
                  <p className="mt-1 text-muted-foreground">
                    <span className="font-medium text-foreground">Declared floor: </span>
                    {r.floor}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
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

function KeepKillPanel({ view, blockedOn, onResolve, live }: PanelProps) {
  const [note, setNote] = useState("")
  const verdicts = view.verdicts
  if (verdicts.length === 0)
    return <EmptyStage title="No verdict yet" body="The verdict appears after the pre-registered test runs on the hold-out." />
  const looks = live?.snapshot?.status.holdout
  const preregId = verdicts[0].preregId

  return (
    <>
      <Section
        title={`Verdict${verdicts.length > 1 ? "s" : ""} for ${preregId}`}
        aside={
          <span className="text-xs text-muted-foreground">
            Hold-out look {looks ? `${looks.looks} of ${looks.max_looks}` : "1 of 1"}
          </span>
        }
      >
        <div className="space-y-3">
          {verdicts.map((v) => (
            <VerdictCard key={v.hypothesisId ?? v.preregId} v={v} />
          ))}
          <p className="flex items-start gap-2 rounded-lg bg-muted/60 p-2.5 text-xs text-muted-foreground">
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
                  disabled={live?.pending}
                  onClick={() => onResolve("decision", { decision: d.id, text: note })}
                  className="flex flex-col items-start gap-1 rounded-lg border bg-background p-3 text-left transition hover:border-foreground disabled:opacity-60"
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
          {live && (
            <div className="mt-3 flex items-center justify-between gap-3">
              <ByField live={live} />
              <span className="text-xs text-muted-foreground">
                Writes a human <code className="font-mono">decision</code> entry (same as <code className="font-mono">python -m sparklab.ledger add --type decision</code>).
              </span>
            </div>
          )}
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

function VerdictCard({ v }: { v: Verdict }) {
  const vs = VERDICT_STYLE[v.label]
  const isPr = v.raw?.kind === "prevalence_ratio" || (!v.raw && v.estimate && !v.estimate.includes("%"))
  const plot = v.plot ?? plotFromRaw(v)
  return (
    <div className="rounded-xl border bg-background p-4">
      <div className="flex flex-wrap items-center gap-3">
        {v.hypothesisId && <span className="font-mono text-xs font-semibold">{v.hypothesisId}</span>}
        <span className={cn("rounded-lg border px-3 py-1 text-lg font-semibold", vs.className)}>{vs.label}</span>
        <MockTag className="rounded-sm text-[10px]" />
        <div className="ml-auto text-sm">
          {isPr ? "Prevalence ratio" : "Weighted share"}{" "}
          <MockValue className="font-semibold" calcId={v.calcId}>
            {v.estimate}
          </MockValue>{" "}
          <span className="text-muted-foreground">
            95% CI <MockValue>{v.ci[0]}</MockValue>–<MockValue>{v.ci[1]}</MockValue>
          </span>
        </div>
      </div>
      {v.prediction && (
        <p className="mt-2 text-xs text-muted-foreground">
          Pre-registered prediction <span className="font-mono text-foreground">{v.prediction}</span>
          {v.null != null && (
            <>
              {" "}
              · null <span className="font-mono text-foreground">{v.null}</span>
            </>
          )}
          {v.ledgerId && <span className="ml-2 rounded bg-muted px-1 text-[9px] font-semibold">ledger {v.ledgerId}</span>}
        </p>
      )}
      {plot && (
        <IntervalPlot
          {...plot}
          lo_label={v.ci[0]}
          hi_label={v.ci[1]}
          null_label={isPr ? `${v.raw?.null ?? 1}` : v.raw?.null != null ? `${Math.round(v.raw.null * 1000) / 10}%` : "null"}
        />
      )}
      <p className="mt-3 text-sm leading-relaxed">{v.interpretation}</p>
    </div>
  )
}

// Display geometry only: place the tool's estimate, CI and null on a 0–1 axis. Ratios go on a log axis
// (PR = 1 is the natural centre), proportions on a linear one. No statistic is computed here.
function plotFromRaw(v: Verdict): Verdict["plot"] | undefined {
  const r = v.raw
  if (!r || r.estimate == null || r.ci[0] == null || r.ci[1] == null) return undefined
  const isPr = r.kind === "prevalence_ratio"
  const f = isPr ? Math.log : (x: number) => x
  const pts = [r.ci[0], r.ci[1], r.estimate, r.null ?? (isPr ? 1 : 0.5), r.prediction?.value ?? null]
    .filter((x): x is number => x != null && (!isPr || x > 0))
    .map(f)
  const min = Math.min(...pts)
  const max = Math.max(...pts)
  const span = max - min || 1
  const pos = (x: number) => 0.08 + 0.84 * ((f(x) - min) / span)
  return {
    lo: pos(r.ci[0]),
    hi: pos(r.ci[1]),
    point: pos(r.estimate),
    nullAt: pos(r.null ?? (isPr ? 1 : 0.5)),
    predictedAt: r.prediction?.value != null && (!isPr || r.prediction.value > 0) ? pos(r.prediction.value) : undefined,
  }
}

function IntervalPlot({
  lo,
  point,
  hi,
  nullAt,
  predictedAt,
  lo_label,
  hi_label,
  null_label = "PR = 1",
}: {
  lo: number
  point: number
  hi: number
  nullAt: number
  predictedAt?: number
  lo_label: string
  hi_label: string
  null_label?: string
}) {
  const pct = (x: number) => `${x * 100}%`
  return (
    <div className="mt-5 mb-1 px-2">
      <div className="relative h-10">
        {/* axis */}
        <div className="absolute top-1/2 right-0 left-0 h-px bg-border" />
        {/* null reference */}
        <div className="absolute top-0 bottom-0 w-px border-l border-dashed border-muted-foreground" style={{ left: pct(nullAt) }} />
        <span className="absolute -top-4 -translate-x-1/2 text-[10px] text-muted-foreground whitespace-nowrap" style={{ left: pct(nullAt) }}>
          null {null_label}
        </span>
        {/* pre-registered prediction */}
        {predictedAt != null && (
          <>
            <div className="absolute top-1 bottom-1 w-px border-l border-dotted border-violet-500" style={{ left: pct(predictedAt) }} />
            <span className="absolute -top-4 -translate-x-1/2 text-[10px] text-violet-700 whitespace-nowrap" style={{ left: pct(predictedAt) }}>
              predicted
            </span>
          </>
        )}
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