"use client"

import { cn } from "@/lib/utils"
import { ACTORS, STAGE_BY_ID } from "@/lib/spark/meta"
import { useDataSource } from "@/lib/spark/data-source"
import type { Actor, AgentStatus, StageId } from "@/lib/spark/types"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

// A statistic, labelled by where it came from. In the scripted replay every number is a placeholder
// (dashed underline; the tooltip says so). In live mode numbers are copied from tool outputs and carry their calc_id
// (ledger/calcs.jsonl), so "no number without a tool" stays visible in the UI.
export function MockValue({ children, className, calcId }: { children: React.ReactNode; className?: string; calcId?: string }) {
  const source = useDataSource()
  if (source === "live") {
    return (
      <span className={cn("inline-flex items-baseline gap-1 tabular-nums", className)}>
        <span>{children}</span>
        {calcId && <CalcChip id={calcId} />}
      </span>
    )
  }
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className={cn("inline-flex items-baseline gap-1 tabular-nums", className)}>
          <span className="underline decoration-dashed decoration-muted-foreground/50 underline-offset-4">{children}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent>Placeholder value. Real values will come from sparklab.stats tools.</TooltipContent>
    </Tooltip>
  )
}

// Provenance chip for a number that came out of a sparklab tool.
export function CalcChip({ id, className }: { id: string; className?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className={cn("rounded-sm bg-emerald-50 px-1 font-mono text-[9px] font-semibold tracking-wide text-emerald-800 ring-1 ring-emerald-200", className)}>
          {id}
        </span>
      </TooltipTrigger>
      <TooltipContent>Computed by a sparklab tool. Record {id} in ledger/calcs.jsonl.</TooltipContent>
    </Tooltip>
  )
}

export function ActorAvatar({ actor, size = "md", className }: { actor: Actor; size?: "sm" | "md" | "lg"; className?: string }) {
  const Icon = ACTORS[actor].icon
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full",
        actor === "human" ? "bg-foreground text-background" : "border bg-background text-foreground",
        size === "sm" && "size-6 [&>svg]:size-3.5",
        size === "md" && "size-8 [&>svg]:size-4",
        size === "lg" && "size-10 [&>svg]:size-5",
        className,
      )}
    >
      <Icon />
    </span>
  )
}

const STATUS_STYLE: Record<AgentStatus, { label: string; dot: string; text: string }> = {
  idle: { label: "Idle", dot: "bg-zinc-300", text: "text-muted-foreground" },
  working: { label: "Working", dot: "bg-blue-500 animate-spark-pulse", text: "text-blue-700" },
  waiting: { label: "Waiting for you", dot: "bg-amber-500 animate-spark-pulse", text: "text-amber-700" },
  done: { label: "Done", dot: "bg-emerald-500", text: "text-emerald-700" },
}

export function StatusPill({ status }: { status: AgentStatus }) {
  const s = STATUS_STYLE[status]
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium", s.text)}>
      <span className={cn("size-1.5 rounded-full", s.dot)} />
      {s.label}
    </span>
  )
}

export function StageTag({ stage, className }: { stage: StageId; className?: string }) {
  const s = STAGE_BY_ID[stage]
  return (
    <span className={cn("inline-flex items-center gap-1 text-[11px] font-medium", s.color.text, className)}>
      <span className={cn("size-1.5 rounded-full", s.color.bg)} />
      {s.name}
    </span>
  )
}

export function Code({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <code className={cn("block overflow-x-auto rounded-md bg-muted px-2 py-1.5 font-mono text-[11px] leading-relaxed text-foreground/80", className)}>
      {children}
    </code>
  )
}

export function EmptyStage({ title, body }: { title: string; body: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed px-6 py-14 text-center">
      <p className="text-sm font-medium">{title}</p>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">{body}</p>
    </div>
  )
}
