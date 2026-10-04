import type { Study } from "@/lib/spark/types"

// Static list: the real lab (backend/), the demo study. When the SPARK Lab API is reachable it is
// driven live from the ledger and the Omnigent session; otherwise it replays the scripted mock.
export const STUDIES: Study[] = [
  {
    id: "undiagnosed-diabetes",
    title: "Undiagnosed diabetes among US adults",
    question:
      "Where does the share of adults with diabetes-range HbA1c and no diagnosis differ from what published priors lead us to expect?",
    dataset: "NHANES 2017–2018 (cycle J, discovery)",
    holdout: "NHANES 2015–2016 (cycle I, sealed)",
    interactive: true,
    stage: "surprise",
    needsHuman: "Set the objective",
    updated: "just now",
    source: "live",
  },
]
