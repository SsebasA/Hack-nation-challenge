"use client"

import { useState } from "react"
import { ArrowRightLeft, Brain, CheckCircle2, Flag, Hand, Terminal, User } from "lucide-react"
import { cn } from "@/lib/utils"
import { ACTORS } from "@/lib/spark/meta"
import type { Actor, ActivityType } from "@/lib/spark/types"
import { formatClock, type ActivityItem } from "@/lib/spark/view"
import { ActorAvatar, Code, StageTag } from "./primitives"
import { useStickToBottom } from "./use-stick-to-bottom"

const TYPE_META: Record<ActivityType, { label: string; icon: typeof Brain; className: string }> = {
  thought: { label: "Reasoning", icon: Brain, className: "text-muted-foreground" },
  tool_call: { label: "Tool call", icon: Terminal, className: "text-blue-700" },
  tool_result: { label: "Result", icon: CheckCircle2, className: "text-emerald-700" },
  handoff: { label: "Handoff", icon: ArrowRightLeft, className: "text-violet-700" },
  flag: { label: "Flag", icon: Flag, className: "text-rose-700" },
  gate: { label: "Human gate", icon: Hand, className: "text-amber-700" },
  human: { label: "Human action", icon: User, className: "text-foreground" },
}

const FILTERS: (Actor | "all")[] = ["all", "supervisor", "scout", "skeptic", "experimenter", "human"]

export function ActivityTimeline({ items }: { items: ActivityItem[] }) {
  const [filter, setFilter] = useState<Actor | "all">("all")
  const shown = filter === "all" ? items : items.filter((i) => i.actor === filter)
  const ref = useStickToBottom<HTMLDivElement>(shown.length)

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap gap-1 border-b px-3 py-2">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={cn(
              "rounded-full border px-2 py-0.5 text-[11px] font-medium transition",
              filter === f ? "border-foreground bg-foreground text-background" : "text-muted-foreground hover:bg-muted",
            )}
          >
            {f === "all" ? "All" : ACTORS[f].name}
          </button>
        ))}
      </div>
      <div ref={ref} className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
        {shown.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">No activity yet.</p>
        ) : (
          <ol className="relative space-y-3 before:absolute before:top-2 before:bottom-2 before:left-[11px] before:w-px before:bg-border">
            {shown.map((item) => (
              <TimelineItem key={item.id} item={item} />
            ))}
          </ol>
        )}
      </div>
    </div>
  )
}

function TimelineItem({ item }: { item: ActivityItem }) {
  const t = TYPE_META[item.type]
  const TypeIcon = t.icon
  return (
    <li className="relative flex gap-3 animate-in fade-in slide-in-from-bottom-1 duration-300">
      <ActorAvatar actor={item.actor} size="sm" className="relative z-10" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px]">
          <span className="font-semibold text-foreground">{ACTORS[item.actor].name}</span>
          <span className={cn("inline-flex items-center gap-1", t.className)}>
            <TypeIcon className="size-3" />
            {t.label}
          </span>
          <StageTag stage={item.stage} />
          <span className="ml-auto font-mono text-muted-foreground tabular-nums">{formatClock(item.at)}</span>
        </div>
        <p className={cn("mt-0.5 text-sm leading-snug", item.type === "gate" && "font-medium text-amber-800")}>{item.title}</p>
        {item.code && <Code className="mt-1.5">{item.code}</Code>}
        {item.detail && <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{item.detail}</p>}
      </div>
    </li>
  )
}
