import type { Study } from "@/lib/spark/types"

// MOCK: static list until a backend exists. Only the first study has a simulated run.
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
  },
  {
    id: "hypertension-awareness",
    title: "Hypertension awareness gap",
    question: "Which subgroups show lower awareness of measured hypertension than expected?",
    dataset: "NHANES (discovery cycle TBD)",
    holdout: "Not sealed yet",
    interactive: false,
    stage: "attack",
    updated: "example",
  },
  {
    id: "ckd-detection",
    title: "Chronic kidney disease detection",
    question: "Where does lab-defined CKD diverge from self-reported diagnosis?",
    dataset: "NHANES (discovery cycle TBD)",
    holdout: "Not sealed yet",
    interactive: false,
    stage: "propose",
    updated: "example",
  },
]
