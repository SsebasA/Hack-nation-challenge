"use client"

import { cn } from "@/lib/utils"
import { GATES, STAGES, STAGE_INDEX } from "@/lib/spark/meta"
import type { GateId, StageId } from "@/lib/spark/types"

export function StageStepper({
  current,
  maxReached,
  selected,
  blockedOn,
  finished,
  onSelect,
}: {
  current: StageId
  maxReached: number
  selected: StageId
  blockedOn: GateId | null
  finished: boolean
  onSelect: (s: StageId) => void
}) {
  const currentIdx = STAGE_INDEX[current]
  const gateStage = blockedOn ? GATES[blockedOn].stage : null

  return (
    <ol className="flex flex-row gap-1 overflow-x-auto lg:flex-col lg:gap-0 lg:overflow-visible">
      {STAGES.map((s, i) => {
        const done = i < currentIdx || (finished && i === currentIdx)
        const active = i === currentIdx && !finished
        const reachable = i <= maxReached
        const needsYou = gateStage === s.id
        const isSelected = selected === s.id
        const Icon = s.icon

        return (
          <li key={s.id} className="relative">
            {/* vertical connector to the next phase */}
            {i < STAGES.length - 1 && (
              <span
                aria-hidden
                className={cn(
                  "absolute top-9 left-[23px] hidden h-[calc(100%-1.75rem)] w-px lg:block",
                  i < currentIdx ? "bg-foreground/40" : "bg-border",
                )}
              />
            )}
            <button
              type="button"
              disabled={!reachable}
              onClick={() => onSelect(s.id)}
              title={needsYou ? `${s.name}: needs you` : s.name}
              className={cn(
                "relative flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm whitespace-nowrap transition lg:mb-2",
                reachable ? "hover:bg-muted" : "cursor-not-allowed opacity-40",
                isSelected && "bg-muted",
              )}
            >
              <span
                className={cn(
                  "relative z-10 inline-flex size-6 shrink-0 items-center justify-center rounded-full",
                  active ? cn(s.color.bg, "text-white") : done ? "bg-foreground text-background" : "bg-muted text-muted-foreground ring-4 ring-background",
                )}
              >
                <Icon className="size-3.5" />
              </span>
              <span className={cn("font-medium", active ? s.color.text : !done && "text-muted-foreground")}>{s.name}</span>
              {needsYou && <span className="ml-auto size-2 shrink-0 rounded-full bg-amber-500 animate-spark-pulse" />}
            </button>
          </li>
        )
      })}
    </ol>
  )
}
