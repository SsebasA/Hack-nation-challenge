import Link from "next/link"
import { ArrowRight, Database, Hand, Lock } from "lucide-react"
import { cn } from "@/lib/utils"
import { ACTORS, STAGES, STAGE_BY_ID, STAGE_INDEX } from "@/lib/spark/meta"
import type { Study } from "@/lib/spark/types"
import { STUDIES } from "@/lib/mock/studies"
import { ActorAvatar } from "@/components/spark/primitives"
import { NewStudyDialog } from "@/components/spark/new-study-dialog"

export default function Home() {
  return (
    <div className="min-h-dvh bg-zinc-50/60">
      <main className="mx-auto max-w-5xl space-y-10 px-4 py-10">
        {/* Method explainer */}
        <section>
          <h1 className="text-4xl font-bold tracking-tight">SPARK</h1>
          <p className="mt-1 text-lg text-muted-foreground">Re-analysis science, done by humans and agents together</p>
          <ol className="mt-6 grid gap-2 sm:grid-cols-5">
            {STAGES.map((s, i) => {
              const Icon = s.icon
              return (
                <li key={s.id} className="relative rounded-xl border bg-background p-3">
                  <div className="flex items-center gap-2">
                    <span className={cn("inline-flex size-7 items-center justify-center rounded-lg text-white", s.color.bg)}>
                      <Icon className="size-3.5" />
                    </span>
                    <span className="text-sm font-semibold">
                      <span className={s.color.text}>{s.letter}</span> {s.name}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">{s.tagline}</p>
                  <div className="mt-3 flex items-center gap-1">
                    {s.agents.map((a) => (
                      <ActorAvatar key={a} actor={a} size="sm" className="size-5 [&>svg]:size-3" />
                    ))}
                    <ActorAvatar actor="human" size="sm" className="size-5 [&>svg]:size-3" />
                  </div>
                  {i < STAGES.length - 1 && (
                    <ArrowRight className="absolute top-1/2 -right-2.5 z-10 hidden size-4 -translate-y-1/2 rounded-full bg-zinc-50 text-muted-foreground sm:block" />
                  )}
                </li>
              )
            })}
          </ol>
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground">
            {(["supervisor", "scout", "skeptic", "experimenter", "human"] as const).map((a) => (
              <span key={a} className="inline-flex items-center gap-1.5">
                <ActorAvatar actor={a} size="sm" className="size-5 [&>svg]:size-3" />
                <b className="font-medium text-foreground">{ACTORS[a].name}</b> {ACTORS[a].role.toLowerCase()}
              </span>
            ))}
          </div>
        </section>

        {/* Studies */}
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Studies</h2>
            <NewStudyDialog />
          </div>
          <div className="space-y-3">
            {STUDIES.map((s) => (
              <StudyCard key={s.id} study={s} />
            ))}
          </div>
        </section>
      </main>
    </div>
  )
}

function StudyCard({ study }: { study: Study }) {
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
        </div>
        <p className="mt-1 text-sm text-muted-foreground">{study.question}</p>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <Database className="size-3" /> {study.dataset}
          </span>
          <span className="inline-flex items-center gap-1">
            <Lock className="size-3" /> {study.holdout}
          </span>
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
