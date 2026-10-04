"use client"

import { useState } from "react"
import Link from "next/link"
import {
  Activity,
  ArrowRight,
  ChevronLeft,
  Database,
  Hand,
  Lock,
  Radio,
  RotateCcw,
  Users,
  WifiOff,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { GATES } from "@/lib/spark/meta"
import type { GateId, Study, StageId } from "@/lib/spark/types"
import { useSimulation, type Simulation } from "@/lib/spark/use-simulation"
import { DataSourceProvider } from "@/lib/spark/data-source"
import { DIABETES_SCRIPT, resolveGate } from "@/lib/mock/diabetes-script"
import { useBackendProbe } from "@/lib/live/use-backend-probe"
import { useLiveStudy, type GateInput, type LiveStudy } from "@/lib/live/use-live-study"
import { API_URL } from "@/lib/live/client"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { StageStepper } from "./stage-stepper"
import { StagePanel } from "./stage-panels"
import { AgentTeam } from "./agent-team"
import { ActivityTimeline } from "./activity-timeline"
import { LedgerFeed } from "./ledger-feed"
import { ChatPanel } from "./chat-panel"

// Entry point: decide in the browser whether this study runs against the SPARK Lab API or the
// scripted mock, then mount the matching data hook. Hooks cannot be conditional, so each source
// is its own component around the shared WorkspaceView.
export function Workspace({ study }: { study: Study }) {
  const probe = useBackendProbe(study.source !== "mock")
  if (probe.state === "probing") return <ProbingShell study={study} />
  if (probe.source === "live") return <LiveWorkspace key={study.id} study={study} />
  return <MockWorkspace key={study.id} study={study} />
}

function MockWorkspace({ study }: { study: Study }) {
  const sim = useSimulation(DIABETES_SCRIPT)
  return (
    <DataSourceProvider source="mock">
      <WorkspaceView
        study={study}
        sim={sim}
        live={null}
        badge={null}
        onResolve={(g, input) => sim.resolve(g, resolveGate(g, input))}
      />
    </DataSourceProvider>
  )
}

function LiveWorkspace({ study }: { study: Study }) {
  const live = useLiveStudy(study.id)
  return (
    <DataSourceProvider source="live">
      <WorkspaceView
        study={study}
        sim={live}
        live={live}
        badge={<LiveBadge live={live} />}
        onResolve={(g, input) => void live.resolveLive(g, input)}
      />
    </DataSourceProvider>
  )
}

function ProbingShell({ study }: { study: Study }) {
  return (
    <div className="flex h-dvh flex-col bg-zinc-50/60">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b bg-background px-4">
        <Button asChild variant="ghost" size="sm">
          <Link href="/">
            <ChevronLeft /> Studies
          </Link>
        </Button>
        <div className="h-5 w-px bg-border" />
        <h1 className="truncate text-sm font-semibold">{study.title}</h1>
        <span className="ml-2 inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] text-muted-foreground">
          <Radio className="size-3 animate-pulse" /> Looking for the SPARK Lab API…
        </span>
      </header>
    </div>
  )
}

function LiveBadge({ live }: { live: LiveStudy }) {
  const s = live.snapshot
  const omni = s?.omnigent
  const offline = live.connection === "offline"
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={cn(
            "ml-2 inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-semibold",
            offline ? "border-rose-300 bg-rose-50 text-rose-800" : "border-emerald-300 bg-emerald-50 text-emerald-800",
          )}
        >
          {offline ? <WifiOff className="size-3" /> : <Radio className="size-3" />}
          {offline ? "API OFFLINE" : "LIVE"}
          {s && (
            <span className="font-normal text-current/80">
              · ledger {s.status.ledger.entries} · calcs {s.status.ledger.calcs}
              {omni && ` · Omnigent ${omni.reachable ? (s.session ? s.session.status ?? "connected" : "no spark_lab session") : "down"}`}
            </span>
          )}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-sm">
        {offline ? (
          <>Lost the SPARK Lab API at {API_URL}. Showing the last snapshot; reconnecting…</>
        ) : (
          <>
            Reading {s?.status.root}. Ledger chain {s?.status.ledger.intact ? "intact" : "BROKEN"}. Hold-out{" "}
            {s?.status.holdout.unsealed ? "unsealed" : s?.status.holdout.sealed ? "sealed" : "not sealed"}, looks{" "}
            {s?.status.holdout.looks}/{s?.status.holdout.max_looks}.
            {s?.session && <> Omnigent session {s.session.id.slice(0, 8)}… ({s.session.status}).</>}
            {omni && !omni.reachable && <> Omnigent not reachable at {omni.url}: agent activity will appear once `omnigent run lab.yaml` is up.</>}
          </>
        )}
      </TooltipContent>
    </Tooltip>
  )
}

type SidePanel = "agents" | "activity"
type ActivityTab = "timeline" | "chat" | "ledger"

function WorkspaceView({
  study,
  sim,
  live,
  badge,
  onResolve,
}: {
  study: Study
  sim: Simulation
  live: LiveStudy | null
  badge: React.ReactNode
  onResolve: (gate: GateId, input?: GateInput) => void
}) {
  const { view, blockedOn } = sim

  // The selected stage follows the live stage until the user picks another one.
  const [pinnedStage, setPinnedStage] = useState<StageId | null>(null)
  const selected = pinnedStage ?? view.stage
  const gate = blockedOn ? GATES[blockedOn] : null
  // Only one side panel is open at a time.
  const [panel, setPanel] = useState<SidePanel | null>("agents")
  const [activityTab, setActivityTab] = useState<ActivityTab>("timeline")
  const toggle = (p: SidePanel) => setPanel((cur) => (cur === p ? null : p))
  const agentsWorking = Object.values(view.agents).some((a) => a.status === "working")

  const goToGate = () => gate && setPinnedStage(gate.stage === view.stage ? null : gate.stage)

  return (
    <div className="flex h-dvh flex-col bg-zinc-50/60">
      {/* Header */}
      <header className="flex h-14 shrink-0 items-center gap-3 border-b bg-background px-4">
        <Button asChild variant="ghost" size="sm">
          <Link href="/">
            <ChevronLeft /> Studies
          </Link>
        </Button>
        <div className="h-5 w-px bg-border" />
        <div className="min-w-0">
          <h1 className="truncate text-sm font-semibold">{study.title}</h1>
          <p className="hidden truncate text-[11px] text-muted-foreground sm:flex sm:items-center sm:gap-3">
            <span className="inline-flex items-center gap-1">
              <Database className="size-3" /> {study.dataset}
            </span>
            <span className="inline-flex items-center gap-1">
              <Lock className="size-3" /> {study.holdout}
            </span>
          </p>
        </div>
        {badge}

        <div className="ml-auto flex items-center gap-1">
          <PanelToggle
            label="Agents"
            icon={Users}
            open={panel === "agents"}
            onToggle={() => toggle("agents")}
            dot={blockedOn ? "amber" : agentsWorking ? "blue" : null}
          />
          <PanelToggle
            label="Activity"
            icon={Activity}
            open={panel === "activity"}
            onToggle={() => toggle("activity")}
            dot={null}
          />
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {/* Phases sidebar */}
        <nav className="shrink-0 border-b bg-background px-3 py-2 lg:w-52 lg:border-r lg:border-b-0 lg:py-4">
          <StageStepper
            current={view.stage}
            maxReached={view.maxStageIndex}
            selected={selected}
            blockedOn={blockedOn}
            finished={sim.finished}
            onSelect={(s) => setPinnedStage(s === view.stage ? null : s)}
          />
        </nav>

        {/* Main */}
        <main className="min-h-0 flex-1 overflow-y-auto p-4 lg:p-6">
          <div className="mx-auto max-w-4xl space-y-3">
            {gate && (
              <div className="flex items-center gap-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 animate-in fade-in duration-300">
                <span className="inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-amber-400 text-amber-950">
                  <Hand className="size-3.5" />
                </span>
                <p className="text-sm">
                  <span className="font-semibold">The agents are waiting for you:</span> {gate.title}.
                </p>
                {selected !== gate.stage && (
                  <Button size="sm" variant="outline" className="ml-auto" onClick={goToGate}>
                    {gate.cta} <ArrowRight />
                  </Button>
                )}
              </div>
            )}
            {sim.finished && (
              <div className="flex items-center gap-3 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm">
                <span className="font-semibold">SPARK cycle complete.</span>
                <span className="text-muted-foreground">
                  {live ? `Every step is recorded in the ledger (${view.ledger.length} entries, chain ${live.snapshot?.status.ledger.intact ? "intact" : "broken"}).` : "Every step is recorded in the ledger."}
                </span>
                {!live && (
                  <Button size="sm" variant="outline" className="ml-auto" onClick={() => { sim.reset(); setPinnedStage(null) }}>
                    <RotateCcw /> Replay
                  </Button>
                )}
              </div>
            )}
            {live?.error && (
              <div className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-900">{live.error}</div>
            )}
            {live?.notice && (
              <div className="rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">{live.notice}</div>
            )}
            {live && live.connection === "live" && !live.snapshot?.omnigent?.reachable && (
              <div className="rounded-lg border bg-background px-3 py-2 text-xs text-muted-foreground">
                Omnigent is not reachable at {live.snapshot?.omnigent?.url}. The board and the ledger are live; the agents need{" "}
                <code className="font-mono">omnigent start</code> (same venv as sparklab) before a session can be started from here.
              </div>
            )}
            {live && live.connection === "live" && live.snapshot?.omnigent?.reachable && !live.snapshot?.session && blockedOn !== "objective" && (
              <div className="rounded-lg border bg-background px-3 py-2 text-xs text-muted-foreground">
                Omnigent is up but this study has no <code className="font-mono">spark_lab</code> session yet. Set the objective to
                start one from <code className="font-mono">lab.yaml</code>, or run <code className="font-mono">omnigent run lab.yaml</code> in the
                study folder.
              </div>
            )}
            {live?.snapshot?.study && !live.snapshot.study.active && live.snapshot.session && (
              <div className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                This study is not the active lab for the shared Omnigent runner: the agents&apos; tools currently write to another
                study. Starting this study&apos;s session (or <code className="font-mono">python -m sparklab.studies use {live.studyId}</code>) makes it active.
              </div>
            )}
            {pinnedStage && pinnedStage !== view.stage && (
              <button
                type="button"
                onClick={() => setPinnedStage(null)}
                className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
              >
                Viewing an earlier stage · Back to live stage <ArrowRight className="size-3" />
              </button>
            )}
            <StagePanel stage={selected} view={view} blockedOn={blockedOn} onResolve={onResolve} live={live} />
          </div>
        </main>

        {/* Agents panel: team tree only */}
        {panel === "agents" && (
          <SidePanelFrame
            title="Agent team"
            aside={live?.snapshot?.session ? `Omnigent · ${live.snapshot.session.id.slice(0, 8)}…` : "Omnigent · lab.yaml"}
            onClose={() => setPanel(null)}
            className="lg:w-[340px]"
          >
            <div className="min-h-0 flex-1 overflow-y-auto p-3">
              <AgentTeam agents={view.agents} humanNeeded={!!blockedOn} />
            </div>
          </SidePanelFrame>
        )}

        {/* Activity panel: timeline, chat with the Supervisor, or ledger */}
        {panel === "activity" && (
          <SidePanelFrame
            title="Activity"
            aside={
              <span className="inline-flex rounded-md border p-0.5">
                {(["timeline", "chat", "ledger"] as ActivityTab[]).map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setActivityTab(t)}
                    className={cn(
                      "rounded px-2 py-0.5 text-[11px] font-medium capitalize",
                      activityTab === t ? "bg-foreground text-background" : "text-muted-foreground hover:bg-muted",
                    )}
                  >
                    {t === "ledger" ? `Ledger (${view.ledger.length})` : t === "chat" ? `Chat (${view.chat.length})` : "Timeline"}
                  </button>
                ))}
              </span>
            }
            onClose={() => setPanel(null)}
            className="lg:w-[420px]"
          >
            {activityTab === "timeline" ? (
              <ActivityTimeline items={view.activity} />
            ) : activityTab === "chat" ? (
              <ChatPanel
                items={view.chat}
                onSend={live ? live.send : undefined}
                onStart={live && live.snapshot?.omnigent?.reachable && !live.snapshot?.session ? live.startAgents : undefined}
                pending={live?.pending}
                disabledReason={
                  live && !live.snapshot?.omnigent?.reachable
                    ? "Omnigent is not reachable."
                    : live && !live.snapshot?.session
                      ? "No Supervisor session yet: start the agents first."
                      : undefined
                }
              />
            ) : (
              <LedgerFeed items={view.ledger} />
            )}
          </SidePanelFrame>
        )}
      </div>
    </div>
  )
}

function SidePanelFrame({
  title,
  aside,
  onClose,
  className,
  children,
}: {
  title: string
  aside?: React.ReactNode
  onClose: () => void
  className?: string
  children: React.ReactNode
}) {
  return (
    <aside
      className={cn(
        "flex min-h-[420px] w-full shrink-0 flex-col border-t bg-background animate-in fade-in slide-in-from-right-4 duration-200 lg:min-h-0 lg:border-t-0 lg:border-l",
        className,
      )}
    >
      <div className="flex h-10 shrink-0 items-center justify-between border-b px-3">
        <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{title}</h2>
        <div className="flex items-center gap-2">
          {aside && <span className="text-[11px] text-muted-foreground">{aside}</span>}
          <Button variant="ghost" size="icon-xs" onClick={onClose} aria-label={`Close ${title}`}>
            <X />
          </Button>
        </div>
      </div>
      {children}
    </aside>
  )
}

// Header button for a side panel. While closed, a dot can signal agents working (blue) or waiting on you (amber).
function PanelToggle({
  label,
  icon: Icon,
  open,
  onToggle,
  dot,
}: {
  label: string
  icon: typeof Users
  open: boolean
  onToggle: () => void
  dot: "amber" | "blue" | null
}) {
  return (
    <Button variant={open ? "secondary" : "outline"} size="sm" onClick={onToggle} aria-pressed={open} className="relative">
      <Icon />
      {label}
      {!open && dot && (
        <span
          className={cn(
            "absolute -top-1 -right-1 size-2.5 rounded-full ring-2 ring-background animate-spark-pulse",
            dot === "amber" ? "bg-amber-500" : "bg-blue-500",
          )}
        />
      )}
    </Button>
  )
}
