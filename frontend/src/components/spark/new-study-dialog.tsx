"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Loader2, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { createStudy, fetchHealth } from "@/lib/live/client"

// Creates a study through the SPARK Lab API: a new lab directory (backend/studies/<id>/) with its own
// ledger, board and prereg folder. The discovery data and the sealed hold-out are linked from the root
// lab, so the agents' tools can run on it. Needs the API; disabled otherwise.
export function NewStudyDialog() {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [apiUp, setApiUp] = useState<boolean | null>(null)
  const [title, setTitle] = useState("")
  const [question, setQuestion] = useState("")
  const [by, setBy] = useState("")
  const [copyBoard, setCopyBoard] = useState(true)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchHealth()
      .then(() => !cancelled && setApiUp(true))
      .catch(() => !cancelled && setApiUp(false))
    return () => {
      cancelled = true
    }
  }, [open])

  const submit = async () => {
    setError(null)
    setPending(true)
    try {
      const r = await createStudy({ title, question, by: by || undefined, copy_board: copyBoard })
      setOpen(false)
      router.push(`/studies/${r.study.id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setPending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus /> New study
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New study</DialogTitle>
          <DialogDescription>
            A new lab folder with its own ledger, expectation board and pre-registrations. You set the objective once it
            exists; the agents scan the discovery data against the board and report surprises back to you.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Field label="Title">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="h-9 w-full rounded-lg border bg-background px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
              placeholder="e.g. Undiagnosed diabetes among uninsured adults"
            />
          </Field>
          <Field label="Question">
            <Textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={3} placeholder="What discrepancy are you looking for, and what output do you want?" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Discovery data">
              <select className="h-9 w-full rounded-lg border bg-background px-2 text-sm" disabled>
                <option>NHANES 2017–2018 (J)</option>
              </select>
            </Field>
            <Field label="Sealed hold-out">
              <select className="h-9 w-full rounded-lg border bg-background px-2 text-sm" disabled>
                <option>NHANES 2015–2016 (I)</option>
              </select>
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Created by">
              <input
                value={by}
                onChange={(e) => setBy(e.target.value)}
                className="h-9 w-full rounded-lg border bg-background px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
                placeholder="your name"
              />
            </Field>
            <label className="flex items-center gap-2 self-end pb-2 text-xs">
              <input type="checkbox" checked={copyBoard} onChange={(e) => setCopyBoard(e.target.checked)} />
              Start from the cited expectation board
            </label>
          </div>
          <p className="text-[11px] text-muted-foreground">
            Both NHANES cycles are linked from the root lab (the sealed zip keeps its SHA-256 and gets its own seal entry).
            Only the derived diabetes columns exist, so new studies are re-analyses of the same data.
          </p>
          {apiUp === false && (
            <p className="rounded-md border border-amber-300 bg-amber-50 px-2 py-1.5 text-xs text-amber-900">
              The SPARK Lab API is not reachable; start it with <code className="font-mono">python -m sparklab.api</code>.
            </p>
          )}
          {error && <p className="rounded-md border border-rose-300 bg-rose-50 px-2 py-1.5 text-xs text-rose-900">{error}</p>}
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">Cancel</Button>
          </DialogClose>
          <Button onClick={() => void submit()} disabled={!title.trim() || pending || apiUp === false}>
            {pending ? <Loader2 className="animate-spin" /> : <Plus />} Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium">{label}</span>
      {children}
    </label>
  )
}
