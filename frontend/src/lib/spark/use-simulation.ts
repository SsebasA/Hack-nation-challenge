"use client"

import { useEffect, useMemo, useReducer } from "react"
import type { GateId, LoggedEvent, ScriptStep, SparkEvent } from "./types"
import { foldView } from "./view"

// Replays a scripted list of agent events over time.
// A step with a `gate` blocks the run until a human resolves it.

type SimState = {
  stepIndex: number
  clock: number
  log: LoggedEvent[]
  blockedOn: GateId | null
  playing: boolean
  speed: number
}

type SimAction =
  | { type: "step" }
  | { type: "play" }
  | { type: "pause" }
  | { type: "reset" }
  | { type: "speed"; speed: number }
  | { type: "resolve"; gate: GateId; events: SparkEvent[] }
  | { type: "human"; events: SparkEvent[] }

function applyStep(state: SimState, steps: ScriptStep[]): SimState {
  if (state.blockedOn || state.stepIndex >= steps.length) return state
  const step = steps[state.stepIndex]
  const clock = state.clock + step.delay
  return {
    ...state,
    stepIndex: state.stepIndex + 1,
    clock,
    log: [...state.log, ...step.events.map((event) => ({ at: clock, event }))],
    blockedOn: step.gate ?? null,
  }
}

function init(steps: ScriptStep[]): SimState {
  const empty: SimState = { stepIndex: 0, clock: 0, log: [], blockedOn: null, playing: true, speed: 1 }
  return applyStep(empty, steps)
}

export function useSimulation(steps: ScriptStep[]) {
  const [state, dispatch] = useReducer((s: SimState, a: SimAction): SimState => {
    switch (a.type) {
      case "step":
        return applyStep(s, steps)
      case "play":
        return { ...s, playing: true }
      case "pause":
        return { ...s, playing: false }
      case "reset":
        return { ...init(steps), speed: s.speed }
      case "speed":
        return { ...s, speed: a.speed }
      case "resolve":
        if (s.blockedOn !== a.gate) return s
        return { ...s, blockedOn: null, log: [...s.log, ...a.events.map((event) => ({ at: s.clock, event }))] }
      case "human":
        return { ...s, log: [...s.log, ...a.events.map((event) => ({ at: s.clock, event }))] }
    }
  }, steps, init)

  const finished = state.stepIndex >= steps.length && !state.blockedOn
  const nextDelay = steps[state.stepIndex]?.delay

  useEffect(() => {
    if (!state.playing || state.blockedOn || finished || nextDelay === undefined) return
    const t = setTimeout(() => dispatch({ type: "step" }), nextDelay / state.speed)
    return () => clearTimeout(t)
  }, [state.playing, state.blockedOn, state.stepIndex, state.speed, finished, nextDelay])

  const view = useMemo(() => foldView(state.log), [state.log])
  const progress = steps.length ? state.stepIndex / steps.length : 0

  return {
    view,
    blockedOn: state.blockedOn,
    playing: state.playing,
    speed: state.speed,
    finished,
    progress,
    clock: state.clock,
    play: () => dispatch({ type: "play" }),
    pause: () => dispatch({ type: "pause" }),
    step: () => dispatch({ type: "step" }),
    reset: () => dispatch({ type: "reset" }),
    setSpeed: (speed: number) => dispatch({ type: "speed", speed }),
    resolve: (gate: GateId, events: SparkEvent[]) => dispatch({ type: "resolve", gate, events }),
    human: (events: SparkEvent[]) => dispatch({ type: "human", events }),
  }
}

export type Simulation = ReturnType<typeof useSimulation>
