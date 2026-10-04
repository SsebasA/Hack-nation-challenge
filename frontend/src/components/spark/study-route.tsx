"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { ChevronLeft, Radio } from "lucide-react"
import type { Study } from "@/lib/spark/types"
import { STUDIES } from "@/lib/mock/studies"
import { fetchStudy } from "@/lib/live/client"
import { Button } from "@/components/ui/button"
import { Workspace } from "./workspace"

type Resolved = { state: "loading" } | { state: "ok"; study: Study } | { state: "missing"; reason: string }

// Resolves which study a URL refers to: one of the built-in entries (the real lab, which can also
// replay the mock) or a study created through the API (always live).
export function StudyRoute({ studyId }: { studyId: string }) {
  const [res, setRes] = useState<Resolved>(() => {
    const builtin = STUDIES.find((s) => s.id === studyId && s.interactive)
    return builtin ? { state: "ok", study: builtin } : { state: "loading" }
  })

  useEffect(() => {
    if (res.state !== "loading") return
    let cancelled = false
    fetchStudy(studyId)
      .then((s) => {
        if (cancelled) return
        setRes({
          state: "ok",
          study: {
            id: s.id,
            title: s.title,
            question: s.question,
            dataset: s.dataset,
            holdout: s.holdout,
            interactive: true,
            stage: s.stage ?? "surprise",
            updated: "live",
            source: "live",
          },
        })
      })
      .catch((e) => {
        if (cancelled) return
        const status = (e as { status?: number }).status
        setRes({
          state: "missing",
          reason: status === 404 ? `No study named "${studyId}" in this lab.` : "The SPARK Lab API is not reachable, and this study is not one of the built-in ones.",
        })
      })
    return () => {
      cancelled = true
    }
  }, [res.state, studyId])

  if (res.state === "ok") return <Workspace study={res.study} />

  return (
    <div className="flex h-dvh flex-col bg-zinc-50/60">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b bg-background px-4">
        <Button asChild variant="ghost" size="sm">
          <Link href="/">
            <ChevronLeft /> Studies
          </Link>
        </Button>
        <div className="h-5 w-px bg-border" />
        <h1 className="truncate font-mono text-sm">{studyId}</h1>
      </header>
      <main className="flex flex-1 items-center justify-center p-6">
        {res.state === "loading" ? (
          <p className="inline-flex items-center gap-2 text-sm text-muted-foreground">
            <Radio className="size-4 animate-pulse" /> Looking up this study…
          </p>
        ) : (
          <div className="max-w-md rounded-xl border bg-background p-6 text-center">
            <p className="font-medium">Study not found</p>
            <p className="mt-1 text-sm text-muted-foreground">{res.reason}</p>
          </div>
        )}
      </main>
    </div>
  )
}
