"use client"

import { Plus } from "lucide-react"
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

// UX prototype of study creation. Nothing is saved until a backend exists.
export function NewStudyDialog() {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button>
          <Plus /> New study
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New study</DialogTitle>
          <DialogDescription>
            You set the objective. Agents scan the discovery data against the expectation board and report surprises
            back to you.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Field label="Title">
            <input className="h-9 w-full rounded-lg border bg-background px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50" placeholder="e.g. Undiagnosed diabetes among US adults" />
          </Field>
          <Field label="Objective">
            <Textarea rows={3} placeholder="What discrepancy are you looking for, and what output do you want?" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Discovery data">
              <select className="h-9 w-full rounded-lg border bg-background px-2 text-sm">
                <option>NHANES 2017–2018 (J)</option>
              </select>
            </Field>
            <Field label="Sealed hold-out">
              <select className="h-9 w-full rounded-lg border bg-background px-2 text-sm">
                <option>NHANES 2015–2016 (I)</option>
              </select>
            </Field>
          </div>
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">Cancel</Button>
          </DialogClose>
          <Button disabled title="Needs the backend">
            Create (needs backend)
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
