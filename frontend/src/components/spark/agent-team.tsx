import { cn } from "@/lib/utils"
import { ACTORS } from "@/lib/spark/meta"
import type { Actor, AgentId, AgentStatus } from "@/lib/spark/types"
import type { ViewState } from "@/lib/spark/view"
import { ActorAvatar, StatusPill } from "./primitives"

// Org diagram: Human → Supervisor → Scout / Skeptic / Experimenter, with live status.
export function AgentTeam({ agents, humanNeeded }: { agents: ViewState["agents"]; humanNeeded: boolean }) {
  const subs: AgentId[] = ["scout", "skeptic", "experimenter"]
  const supActive = agents.supervisor.status === "working"

  return (
    <div className="flex flex-col items-center">
      <Node actor="human" status={humanNeeded ? "waiting" : "idle"} task={humanNeeded ? "Your input is needed" : "Sets objective, judges, approves"} />
      <Connector active={humanNeeded || supActive} />
      <Node actor="supervisor" status={agents.supervisor.status} task={agents.supervisor.task} />
      {/* fan-out connector */}
      <div className="relative h-4 w-full">
        <span className={cn("absolute top-0 left-1/2 h-2 w-px -translate-x-1/2", lineColor(subs.some((a) => agents[a].status === "working")))} />
        <span className="absolute top-2 right-[16.66%] left-[16.66%] h-px bg-border" />
      </div>
      <div className="grid w-full grid-cols-3 gap-2">
        {subs.map((a) => (
          <div key={a} className="flex flex-col items-center">
            <span className={cn("h-2 w-px", lineColor(agents[a].status === "working"))} />
            <Node actor={a} status={agents[a].status} task={agents[a].task} compact />
          </div>
        ))}
      </div>
    </div>
  )
}

function lineColor(active: boolean) {
  return active ? "bg-blue-500" : "bg-border"
}

function Connector({ active }: { active: boolean }) {
  return <span className={cn("h-3 w-px", lineColor(active))} />
}

function Node({ actor, status, task, compact }: { actor: Actor; status: AgentStatus; task?: string; compact?: boolean }) {
  const meta = ACTORS[actor]
  return (
    <div
      className={cn(
        "flex w-full flex-col rounded-lg border bg-background p-2 transition-shadow",
        !compact && "max-w-[260px]",
        status === "working" && "border-blue-300 shadow-[0_0_0_3px] shadow-blue-100",
        status === "waiting" && "border-amber-300 shadow-[0_0_0_3px] shadow-amber-100",
      )}
    >
      <div className={cn("flex items-center gap-2", compact && "flex-col gap-1 text-center")}>
        <ActorAvatar actor={actor} size="sm" />
        <div className="min-w-0 leading-tight">
          <div className="truncate text-xs font-semibold">{meta.name}</div>
          {!compact && <div className="truncate text-[11px] text-muted-foreground">{meta.role}</div>}
        </div>
        {!compact && (
          <span className="ml-auto">
            <StatusPill status={status} />
          </span>
        )}
      </div>
      {compact && (
        <div className="mt-1 flex justify-center">
          <StatusPill status={status} />
        </div>
      )}
      {task && (
        <p className={cn("mt-1 line-clamp-2 text-[11px] text-muted-foreground", compact && "text-center")}>{task}</p>
      )}
    </div>
  )
}
