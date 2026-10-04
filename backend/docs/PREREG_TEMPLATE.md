# Pre-registration template

Pass this JSON (as a string) to `register_prereg`. It is frozen with SHA-256, written to
`prereg/<id>.json` and git-committed. To change anything, register a new protocol.

```json
{
  "title": "Undiagnosed diabetes: access vs recent onset vs measurement error",
  "question": "Among US adults reporting no diabetes diagnosis, who has HbA1c >= 6.5% and why?",
  "rivals": [
    {"id": "H_measurement_error", "origin": "human",
     "statement": "A single HbA1c misclassifies part of the cell",
     "floor": "TODO: declared floor and how it is estimated (e.g. glucose agreement, wt_fast sensitivity)"}
  ],
  "hypotheses": [
    {"id": "H_access", "origin": "agent:experimenter",
     "statement": "Uninsured adults have a higher prevalence of HbA1c >= 6.5 without a reported diagnosis",
     "test": {"kind": "prevalence_ratio", "domain": "diag == 'no'", "outcome": "hba1c >= 6.5", "group": "not insured"},
     "prediction": {"op": ">=", "value": 1.5}, "null": 1.0},
    {"id": "H_recent_onset", "origin": "agent:experimenter",
     "statement": "Most of the undiagnosed cell sits just above the threshold",
     "test": {"kind": "proportion", "domain": "undiagnosed", "outcome": "hba1c < 7.0"},
     "prediction": {"op": ">=", "value": 0.60}, "null": 0.5}
  ],
  "attacks_addressed": ["L00xx"],
  "power_checks": ["calc_000xx"],
  "decision_rule": "sparklab.stats.verdict: incompatible if CI excludes the predicted region; supported if the estimate is in the predicted region and the CI excludes the null; otherwise inconclusive"
}
```
Base domain `adult and not pregnant` is always applied. Weights are chosen automatically
(`wt_fast` only when glucose is referenced).
