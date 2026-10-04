"use client"

import { cn } from "@/lib/utils"
import { formatClock, type LedgerItem } from "@/lib/spark/view"
import { ActorAvatar } from "./primitives"
import { useStickToBottom } from "./use-stick-to-bottom"

// The lab notebook as the UI sees it: one row per ledger entry, with its id, origin and hash prefix.
// In live mode these are the real entries of ledger/ledger.jsonl (append-only, hash-chained).
export function LedgerFeed({ items }: { items: LedgerItem[] }) {
  const ref = useStickToBottom<HTMLDivElement>(items.length)
  return (
    <div ref={ref} className="min-h-0 flex-1 overflow-y-auto">
      {items.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">Nothing in the ledger yet.</p>
      ) : (
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-muted/70 text-left text-[11px] text-muted-foreground backdrop-blur">
            <tr>
              <th className="px-3 py-1.5 font-medium">#</th>
              <th className="px-3 py-1.5 font-medium">Entry</th>
              <th className="px-3 py-1.5 text-right font-medium">Hash</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {items.map((it) => {
              const actor = it.origin === "human" ? "human" : it.origin.replace("agent:", "")
              return (
                <tr key={it.seq} className="align-top animate-in fade-in duration-300">
                  <td className="px-3 py-2 font-mono text-[11px] text-muted-foreground whitespace-nowrap">
                    {it.id ?? `#${it.seq}`}
                    <div className="text-[10px]">{formatClock(it.at)}</div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1.5">
                      <ActorAvatar actor={actor as "human" | "supervisor" | "scout" | "skeptic" | "experimenter"} size="sm" className="size-4 [&>svg]:size-2.5" />
                      <span className={cn("rounded px-1 py-px font-mono text-[10px] font-semibold", typeClass(it.type))}>{it.type}</span>
                      <span className="text-[10px] text-muted-foreground">{it.origin}</span>
                    </div>
                    <p className="mt-0.5 leading-snug">{it.summary}</p>
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-[10px] text-muted-foreground whitespace-nowrap">{it.hash}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

function typeClass(type: string) {
  switch (type) {
    case "prereg":
    case "approval":
    case "unseal":
    case "seal":
    case "holdout_look":
      return "bg-violet-100 text-violet-800"
    case "result":
    case "decision":
      return "bg-emerald-100 text-emerald-800"
    case "attack":
    case "gate":
    case "flag":
    case "power_gate":
      return "bg-rose-100 text-rose-800"
    case "anomaly":
    case "hypothesis":
    case "hypotheses":
      return "bg-sky-100 text-sky-800"
    default:
      return "bg-muted text-muted-foreground"
  }
}
