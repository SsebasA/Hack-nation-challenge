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
  RotateCcw,
  Users,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { GATES } from "@/lib/spark/meta"
import type { Study, StageId } from "@/lib/spark/types"
import { useSimulation } from "@/lib/spark/use-simulation"
import { DIABETES_SCRIPT, resolveGate } from "@/lib/mock/diabetes-script"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { StageStepper } from "./stage-stepper"
import { StagePanel } from "./stage-panels"
import { AgentTeam } from "./agent-team"
import { ActivityTimeline } from "./activity-timeline"

export function Workspace({ study }: { study: Study }) {
  const sim = useSimulation(DIABETES_SCRIPT)
  const { view, blockedOn } = sim

  // The selected stage follows the live stage until the user picks another one.
  const [pinnedStage, setPinnedStage] = useState<StageId | null>(null)
  const selected = pinnedStage ?? view.stage
  const gate = blockedOn ? GATES[blockedOn] : null
  // Only one side panel is open at a time.
  const [panel, setPanel] = useState<SidePanel | null>("agents")
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
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="ml-2 rounded-md border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
              MOCK DATA
            </span>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">
            No backend yet. Agent activity is scripted and every number is a placeholder, not a real result.
          </TooltipContent>
        </Tooltip>

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
                <span className="text-muted-foreground">Every step is recorded in the ledger.</span>
                <Button size="sm" variant="outline" className="ml-auto" onClick={() => { sim.reset(); setPinnedStage(null) }}>
                  <RotateCcw /> Replay
                </Button>
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
            <StagePanel
              stage={selected}
              view={view}
              blockedOn={blockedOn}
              onResolve={(g, input) => sim.resolve(g, resolveGate(g, input))}
            />
          </div>
        </main>

        {/* Agents panel: team tree only */}
        {panel === "agents" && (
          <SidePanelFrame title="Agent team" aside="Omnigent · lab.yaml" onClose={() => setPanel(null)} className="lg:w-[340px]">
            <div className="min-h-0 flex-1 overflow-y-auto p-3">
              <AgentTeam agents={view.agents} humanNeeded={!!blockedOn} />
            </div>
          </SidePanelFrame>
        )}

        {/* Activity panel: timeline, chat, ledger */}
        {panel === "activity" && (
          <SidePanelFrame title="Activity" onClose={() => setPanel(null)} className="lg:w-[420px]">
            <ActivityTimeline items={view.activity} />
          </SidePanelFrame>
        )}
      </div>
    </div>
  )
}

type SidePanel = "agents" | "activity"

function SidePanelFrame({
  title,
  aside,
  onClose,
  className,
  children,
}: {
  title: string
  aside?: string
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
