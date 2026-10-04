import { ArrowRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { ACTORS, STAGES } from "@/lib/spark/meta"
import { STUDIES } from "@/lib/mock/studies"
import { ActorAvatar } from "@/components/spark/primitives"
import { NewStudyDialog } from "@/components/spark/new-study-dialog"
import { StudyList } from "@/components/spark/study-list"

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
          <StudyList studies={STUDIES} />
        </section>
      </main>
    </div>
  )
}
