"use client"

import { useEffect, useState } from "react"
import type { DataSource } from "@/lib/spark/types"
import { fetchHealth, type Health } from "./client"

export type Probe =
  | { state: "probing" }
  | { state: "ready"; source: DataSource; health: Health | null; forced: boolean }

type Ready = Extract<Probe, { state: "ready" }>

// Decides, in the browser, whether a workspace runs against the SPARK Lab API or the scripted mock.
// `?mode=mock` forces the replay (demo without a backend); `?mode=live` forces the API even when
// the probe fails (the workspace then shows its offline state instead of silently falling back).
async function probeSource(wantsLive: boolean): Promise<Ready> {
  const mode = new URLSearchParams(window.location.search).get("mode")
  if (mode === "mock" || (!wantsLive && mode !== "live")) {
    return { state: "ready", source: "mock", health: null, forced: mode === "mock" }
  }
  try {
    const health = await fetchHealth()
    return { state: "ready", source: "live", health, forced: mode === "live" }
  } catch {
    if (mode === "live") return { state: "ready", source: "live", health: null, forced: true }
    return { state: "ready", source: "mock", health: null, forced: false }
  }
}

export function useBackendProbe(wantsLive: boolean): Probe {
  const [probe, setProbe] = useState<Probe>({ state: "probing" })

  useEffect(() => {
    let cancelled = false
    void probeSource(wantsLive).then((result) => {
      if (!cancelled) setProbe(result)
    })
    return () => {
      cancelled = true
    }
  }, [wantsLive])

  return probe
}
