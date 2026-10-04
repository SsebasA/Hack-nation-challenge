"use client"

import { useState } from "react"
import { Loader2, Play, SendHorizontal } from "lucide-react"
import { cn } from "@/lib/utils"
import { ACTORS } from "@/lib/spark/meta"
import { formatClock, type ChatItem } from "@/lib/spark/view"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { ActorAvatar } from "./primitives"
import { useStickToBottom } from "./use-stick-to-bottom"

// The conversation with the Supervisor (and what the sub-agents said). In live mode the input posts
// to the study's Omnigent session; the mock has no one to talk to.
export function ChatPanel({
  items,
  onSend,
  onStart,
  pending,
  disabledReason,
}: {
  items: ChatItem[]
  onSend?: (text: string) => Promise<void>
  // Offered when the study has no Supervisor session yet (Omnigent reachable).
  onStart?: () => Promise<void>
  pending?: boolean
  disabledReason?: string
}) {
  const [text, setText] = useState("")
  const ref = useStickToBottom<HTMLDivElement>(items.length)
  const canSend = !!onSend && !disabledReason

  const submit = async () => {
    if (!onSend || !text.trim()) return
    const t = text
    setText("")
    await onSend(t)
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div ref={ref} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-3 py-3">
        {items.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">No messages yet.</p>
        ) : (
          items.map((m) => {
            const human = m.from === "human"
            return (
              <div key={m.id} className={cn("flex gap-2", human && "flex-row-reverse")}>
                <ActorAvatar actor={m.from} size="sm" className="mt-0.5" />
                <div className={cn("max-w-[85%] rounded-xl border px-3 py-2 text-sm leading-relaxed", human ? "bg-foreground text-background" : "bg-background")}>
                  <div className={cn("mb-0.5 flex items-center gap-2 text-[10px]", human ? "text-background/70" : "text-muted-foreground")}>
                    <span className="font-semibold">{ACTORS[m.from].name}</span>
                    <span className="font-mono tabular-nums">{formatClock(m.at)}</span>
                  </div>
                  <p className="whitespace-pre-wrap">{m.text}</p>
                </div>
              </div>
            )
          })
        )}
      </div>
      {onSend && (
        <div className="shrink-0 border-t p-2">
          {onStart && (
            <div className="mb-2 flex items-center justify-between gap-2 rounded-lg border bg-muted/40 px-2.5 py-2 text-xs">
              <span className="text-muted-foreground">No Supervisor session for this study yet.</span>
              <Button size="sm" variant="outline" onClick={() => void onStart()} disabled={pending}>
                {pending ? <Loader2 className="animate-spin" /> : <Play />} Start the agents (lab.yaml)
              </Button>
            </div>
          )}
          <div className="flex items-end gap-2">
            <Textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void submit()
              }}
              rows={2}
              placeholder={disabledReason ?? "Message the Supervisor… (⌘/Ctrl+Enter to send)"}
              disabled={!canSend || pending}
              className="bg-background text-sm"
            />
            <Button size="icon-sm" onClick={() => void submit()} disabled={!canSend || pending || !text.trim()} aria-label="Send">
              {pending ? <Loader2 className="animate-spin" /> : <SendHorizontal />}
            </Button>
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground">
            Messages go to the Supervisor of this study&apos;s Omnigent session. Numbers it quotes carry calc_ids.
          </p>
        </div>
      )}
    </div>
  )
}
