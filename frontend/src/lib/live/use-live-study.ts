"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { Decision, GateId, LoggedEvent } from "@/lib/spark/types"
import { foldView } from "@/lib/spark/view"
import type { Simulation } from "@/lib/spark/use-simulation"
import {
  ApiError,
  fetchState,
  openEvents,
  postApprove,
  postHumanLedger,
  postPick,
  postUnseal,
  sendMessage,
  startSession,
  type LiveSnapshot,
} from "./client"

export type Connection = "connecting" | "live" | "offline"

// What a human can hand to a gate. Mock and live share this shape; live uses the extra fields.
export type GateInput = {
  text?: string
  decision?: Decision
  expectationId?: string
  // approve: first 8 characters of the protocol's SHA-256; unseal: of the sealed file's SHA-256.
  hashPrefix?: string
}

export type LiveStudy = Simulation & {
  source: "live"
  studyId: string
  connection: Connection
  snapshot: LiveSnapshot | null
  pending: boolean
  error: string | null
  notice: string | null
  by: string
  setBy: (name: string) => void
  // Resolve a human gate through the API. Resolves when the API has recorded it (and, where it
  // applies, told the Supervisor).
  resolveLive: (gate: GateId, input?: GateInput) => Promise<void>
  // Free-form message to the Supervisor of this study's session.
  send: (text: string) => Promise<void>
  // Start (or reuse) the study's Omnigent session from lab.yaml, re-sending the recorded objective if any.
  startAgents: () => Promise<void>
  // After approve + unseal: tell the Supervisor to run the single hold-out test.
  confirmHoldout: () => Promise<void>
}

const BY_KEY = "spark.by"
const CONFIRM_TEXT = "Approved and unsealed. Run the pre-registered test on the hold-out exactly once and report the verdicts."

function storedBy(): string {
  // LiveWorkspace mounts only after the browser-side probe, so there is no server render to mismatch.
  if (typeof window === "undefined") return ""
  try {
    return window.localStorage.getItem(BY_KEY) ?? ""
  } catch {
    return "" // storage unavailable: the name just won't persist
  }
}

function describe(e: unknown): string {
  return e instanceof Error ? e.message : String(e)
}

export function useLiveStudy(studyId: string): LiveStudy {
  const [snapshot, setSnapshot] = useState<LiveSnapshot | null>(null)
  const [connection, setConnection] = useState<Connection>("connecting")
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [by, setByState] = useState(storedBy)
  const versionRef = useRef(-1)

  const setBy = useCallback((name: string) => {
    setByState(name)
    try {
      window.localStorage.setItem(BY_KEY, name)
    } catch {
      // ignore
    }
  }, [])

  // Initial snapshot, then live-tail. The API sends full snapshots, so a stale frame can be dropped by
  // version. The hook is mounted per study (LiveWorkspace is keyed by study id), so no reset is needed here.
  useEffect(() => {
    let cancelled = false
    versionRef.current = -1
    const accept = (s: LiveSnapshot) => {
      const v = s.version ?? 0
      if (v < versionRef.current) return
      versionRef.current = v
      setSnapshot(s)
    }
    fetchState(studyId)
      .then((s) => {
        if (cancelled) return
        accept(s)
        setConnection("live")
      })
      .catch(() => !cancelled && setConnection("offline"))
    const close = openEvents(studyId, {
      onSnapshot: (s) => {
        if (cancelled) return
        accept(s)
        setConnection("live")
      },
      onOpen: () => !cancelled && setConnection("live"),
      onError: () => !cancelled && setConnection("offline"),
    })
    return () => {
      cancelled = true
      close()
    }
  }, [studyId])

  // Fold with timestamps relative to the first record, so the timeline clock reads as elapsed lab time.
  const log = useMemo<LoggedEvent[]>(() => {
    const events = snapshot?.events ?? []
    if (events.length === 0) return []
    const t0 = events.reduce((m, e) => Math.min(m, e.at), Number.POSITIVE_INFINITY)
    return events.map((e) => ({ at: e.at - t0, event: e.event }))
  }, [snapshot])

  const view = useMemo(() => foldView(log), [log])
  const blockedOn = snapshot?.gate ?? null
  const finished = snapshot?.finished ?? false

  const run = useCallback(async (work: () => Promise<string | null | void>) => {
    setError(null)
    setNotice(null)
    setPending(true)
    try {
      const msg = await work()
      if (msg) setNotice(msg)
    } catch (e) {
      setError(describe(e))
    } finally {
      setPending(false)
    }
  }, [])

  const resolveLive = useCallback(
    async (gate: GateId, input: GateInput = {}) => {
      await run(async () => {
        const who = by.trim() || undefined
        switch (gate) {
          case "objective": {
            const text = input.text?.trim()
            if (!text) throw new Error("Write an objective first.")
            try {
              const r = await startSession(studyId, { objective: text, by: who })
              if (r.warning) return `Session ${r.session.id.slice(0, 8)}… ${r.created ? "started from lab.yaml" : "reused"}; ${r.warning}`
              return r.created
                ? `Session ${r.session.id.slice(0, 8)}… started from lab.yaml and the objective was sent to the Supervisor. ${r.note}`
                : `Objective sent to the Supervisor (session ${r.session.id.slice(0, 8)}…).`
            } catch (e) {
              if (e instanceof ApiError && (e.status === 503 || e.status === 502)) {
                // Omnigent is down or misconfigured: keep the human record, say how to start the agents.
                await postHumanLedger(studyId, { type: "plan_update", payload: { action: "objective", text }, by: who })
                throw new Error(
                  `${e.message} The objective was recorded in the ledger; once Omnigent is up you can retry from the chat, or start the agents with \`omnigent run lab.yaml -p "…"\` from the study folder.`,
                )
              }
              throw e
            }
          }
          case "pick-surprise": {
            if (!input.expectationId) throw new Error("Choose an expectation first.")
            const r = await postPick(studyId, { expectation_id: input.expectationId, text: input.text?.trim() || undefined, by: who })
            if (r.warning) return `Pursue ${input.expectationId}: ${r.warning}`
            return r.sent ? `Recorded and sent to the Supervisor: pursue ${input.expectationId}.` : `Recorded: pursue ${input.expectationId} (no Supervisor session to notify).`
          }
          case "approve": {
            const pid = snapshot?.prereg_id
            if (!pid) throw new Error("No registered protocol to approve.")
            if (!who) throw new Error("Type your name: approvals are signed.")
            if (!input.hashPrefix || input.hashPrefix.trim().length < 8) throw new Error("Type the first 8 characters of the protocol's SHA-256.")
            await postApprove(studyId, { prereg_id: pid, by: who, hash_prefix: input.hashPrefix.trim() })
            return `${pid} approved by ${who}.`
          }
          case "unseal": {
            // One click: the UI passes the hash recorded at seal time; the API still hashes the sealed file and
            // refuses (nothing written) if it does not match the ledger, and allows a single unseal.
            const sealed = snapshot?.status.holdout.sealed_sha256
            if (!sealed) throw new Error("This study has no sealed test data (no seal entry in its ledger).")
            await postUnseal(studyId, { by: who || "reviewer", sha256_prefix: sealed.slice(0, 8) })
            return "Test data opened: its fingerprint matches the one recorded when it was sealed."
          }
          case "decision": {
            const decision = input.decision ?? "keep"
            const payload: Record<string, unknown> = { decision }
            if (input.text?.trim()) payload.note = input.text.trim()
            await postHumanLedger(studyId, { type: "decision", payload, by: who })
            return null
          }
        }
      })
    },
    [by, run, snapshot?.prereg_id, studyId],
  )

  const send = useCallback(
    async (text: string) => {
      await run(async () => {
        if (!text.trim()) throw new Error("Write a message first.")
        await sendMessage(studyId, { text: text.trim(), by: by.trim() || undefined })
        return null
      })
    },
    [by, run, studyId],
  )

  const startAgents = useCallback(async () => {
    await run(async () => {
      const r = await startSession(studyId, { objective: snapshot?.objective ?? undefined, by: by.trim() || undefined })
      if (r.warning) return `Session ${r.session.id.slice(0, 8)}… ${r.created ? "started from lab.yaml" : "reused"}; ${r.warning}`
      return r.created
        ? `Session ${r.session.id.slice(0, 8)}… started from lab.yaml${snapshot?.objective ? " and the recorded objective was sent to the Supervisor" : ""}. ${r.note}`
        : `Attached to session ${r.session.id.slice(0, 8)}….`
    })
  }, [by, run, snapshot?.objective, studyId])

  const confirmHoldout = useCallback(async () => {
    await run(async () => {
      await sendMessage(studyId, { text: CONFIRM_TEXT, by: by.trim() || undefined, record: true })
      return "Told the Supervisor the hold-out can be run once."
    })
  }, [by, run, studyId])

  const noop = useCallback(() => {}, [])

  return {
    source: "live",
    studyId,
    view,
    blockedOn,
    playing: connection === "live",
    speed: 1,
    finished,
    progress: finished ? 1 : (view.maxStageIndex + (blockedOn ? 0.5 : 0)) / 5,
    clock: log.length ? log[log.length - 1].at : 0,
    // Replay controls have no meaning for a live lab.
    play: noop,
    pause: noop,
    step: noop,
    reset: noop,
    setSpeed: noop,
    // Simulation-compatible signature: live gates go through resolveLive; the ledger is the only source of truth.
    resolve: (gate: GateId) => void resolveLive(gate),
    human: noop,
    connection,
    snapshot,
    pending,
    error,
    notice,
    by,
    setBy,
    resolveLive,
    send,
    startAgents,
    confirmHoldout,
  }
}
