"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { ArrowRight, Database, Hand, Lock, Radio } from "lucide-react"
import { cn } from "@/lib/utils"
import { GATES, STAGES, STAGE_BY_ID, STAGE_INDEX } from "@/lib/spark/meta"
import type { Study } from "@/lib/spark/types"
import { fetchStudies, type StudySummary } from "@/lib/live/client"

type Card = {
  study: Study
  live: "probing" | "offline" | StudySummary
}

function summaryToStudy(s: StudySummary): Study {
  return {
    id: s.id,
    title: s.title,
    question: s.question,
    dataset: s.dataset,
    holdout: s.holdout,
    interactive: true,
    stage: s.stage ?? "surprise",
    needsHuman: s.finished ? undefined : s.gate ? GATES[s.gate].title : s.needs_confirmation ? "Tell the Supervisor to run the hold-out" : undefined,
    updated: s.session?.updated_at ? new Date(s.session.updated_at * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "live",
    source: "live",
  }
}

// Studies list. Real studies come from the SPARK Lab API (the root lab plus backend/studies/*);
// the scripted examples stay as the fallback so the page always renders. The default study's
// card is the mock's first study when the API is down.
export function StudyList({ studies: fallback }: { studies: Study[] }) {
  const [cards, setCards] = useState<Card[]>(() =>
    fallback.map((s) => ({ study: s, live: s.source === "live" ? "probing" : "offline" })),
  )
  const [active, setActive] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchStudies()
      .then(({ studies, active }) => {
        if (cancelled) return
        const apiCards: Card[] = studies.map((s) => ({ study: summaryToStudy(s), live: s }))
        const examples = fallback.filter((s) => s.source !== "live" && !studies.some((x) => x.id === s.id))
        setCards([...apiCards, ...examples.map((s) => ({ study: s, live: "offline" as const }))])
        setActive(active)
      })
      .catch(() => !cancelled && setCards((cur) => cur.map((c) => (c.live === "probing" ? { ...c, live: "offline" } : c))))
    return () => {
      cancelled = true
    }
  }, [fallback])

  return (
    <div className="space-y-3">
      {cards.map((c) => (
        <StudyCard key={c.study.id} card={c} active={active === c.study.id} />
      ))}
    </div>
  )
}

function StudyCard({ card, active }: { card: Card; active: boolean }) {
  const { study, live } = card
  const wantsLive = study.source === "live"
  const summary = typeof live === "object" ? live : null
  const stage = STAGE_BY_ID[study.stage]
  const idx = STAGE_INDEX[study.stage]

  const body = (
    <div
      className={cn(
        "group flex flex-col gap-4 rounded-xl border bg-background p-4 transition md:flex-row md:items-center",
        study.interactive ? "hover:border-foreground/30 hover:shadow-sm" : "opacity-60",
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-semibold">{study.title}</h3>
          {!study.interactive && (
            <span className="rounded border px-1.5 py-0.5 text-[10px] text-muted-foreground">Example · no simulated run</span>
          )}
          {wantsLive && live === "probing" && (
            <span className="inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] text-muted-foreground">
              <Radio className="size-2.5 animate-pulse" /> checking API…
            </span>
          )}
          {summary && (
            <span className="inline-flex items-center gap-1 rounded border border-emerald-300 bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800">
              <Radio className="size-2.5" /> LIVE
            </span>
          )}
          {summary && active && (
            <span className="rounded border px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground" title="The shared Omnigent runner's tools write to this study">
              active lab
            </span>
          )}
          {wantsLive && live === "offline" && (
            <p></p>
          )}
        </div>
        <p className="mt-1 text-sm text-muted-foreground">{study.question || "No question recorded yet."}</p>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <Database className="size-3" /> {study.dataset}
          </span>
          <span className="inline-flex items-center gap-1">
            <Lock className="size-3" /> {study.holdout}
          </span>
          {summary && (
            <span>
              {summary.ledger_entries ?? 0} ledger entries · {summary.calcs ?? 0} calcs · hold-out{" "}
              {summary.holdout_status?.unsealed ? "unsealed" : summary.holdout_status?.sealed ? "sealed" : "not sealed"}
              {summary.holdout_status && ` · looks ${summary.holdout_status.looks}/${summary.holdout_status.max_looks}`}
              {summary.session ? ` · Omnigent ${summary.session.status ?? "connected"}` : " · no session"}
            </span>
          )}
        </div>
      </div>

      <div className="flex shrink-0 flex-col gap-2 md:w-56">
        <div className="flex items-center justify-between text-xs">
          <span className={cn("font-medium", stage.color.text)}>{stage.name}</span>
          <span className="text-muted-foreground">
            {idx + 1} / {STAGES.length}
          </span>
        </div>
        <div className="flex gap-1">
          {STAGES.map((s, i) => (
            <span key={s.id} className={cn("h-1.5 flex-1 rounded-full", i < idx ? "bg-foreground" : i === idx ? s.color.bg : "bg-muted")} />
          ))}
        </div>
        {study.needsHuman ? (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-700">
            <Hand className="size-3" /> Needs you: {study.needsHuman}
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">Updated {study.updated}</span>
        )}
      </div>

      {study.interactive && (
        <ArrowRight className="hidden size-4 shrink-0 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-foreground md:block" />
      )}
    </div>
  )

  return study.interactive ? <Link href={`/studies/${study.id}`}>{body}</Link> : body
}
