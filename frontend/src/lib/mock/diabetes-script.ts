import type { Decision, GateId, ScriptStep, SparkEvent, StageId } from "@/lib/spark/types"

// MOCK: scripted run of the SPARK loop for the undiagnosed-diabetes study.
// Every number, hash and commit below is a placeholder. Real values must come from
// sparklab.stats / sparklab.tools once the backend exists (CLAUDE.md rule 2).

const act = (
  actor: Extract<SparkEvent, { kind: "activity" }>["actor"],
  stage: StageId,
  type: Extract<SparkEvent, { kind: "activity" }>["type"],
  title: string,
  extra: { detail?: string; code?: string } = {},
): SparkEvent => ({ kind: "activity", actor, stage, type, title, ...extra })

const agent = (
  a: Extract<SparkEvent, { kind: "agent" }>["agent"],
  status: Extract<SparkEvent, { kind: "agent" }>["status"],
  task?: string,
): SparkEvent => ({ kind: "agent", agent: a, status, task })

export const DEFAULT_OBJECTIVE =
  "Find where the share of US adults with HbA1c ≥ 6.5% and no diabetes diagnosis departs from published expectations, and identify which subgroup merits confirmatory re-measurement."

export const PREREG_ID = "P-001"

export const DIABETES_SCRIPT: ScriptStep[] = [
  // ── Surprise ────────────────────────────────────────────────
  {
    delay: 0,
    gate: "objective",
    events: [
      { kind: "stage", stage: "surprise" },
      agent("supervisor", "waiting", "Waiting for the study objective"),
      {
        kind: "chat",
        from: "supervisor",
        text: "Hi, I'm the Supervisor. Set the objective for this study and I'll brief the Scout, Skeptic and Experimenter.",
      },
      act("supervisor", "surprise", "gate", "Waiting for a human to set the objective"),
    ],
  },
  {
    delay: 1400,
    events: [
      agent("supervisor", "working", "Planning the Surprise stage"),
      act("supervisor", "surprise", "thought", "Plan: compare discovery cycle J against every prior on the expectation board", {
        detail: "The hold-out cycle I stays sealed. Discovery work uses cycle J only.",
      }),
    ],
  },
  {
    delay: 1600,
    events: [
      act("supervisor", "surprise", "handoff", "Delegated to Scout: scan the expectation board for discrepancies"),
      agent("supervisor", "idle"),
      agent("scout", "working", "Loading the expectation board"),
    ],
  },
  {
    delay: 1500,
    events: [
      act("scout", "surprise", "tool_call", "Load expectation board", { code: "load_board('board/expectations.json')" }),
    ],
  },
  {
    delay: 1300,
    events: [
      act("scout", "surprise", "tool_result", "4 expectations loaded with query specs"),
      { kind: "expectation", item: { id: "E1", label: "Diagnosed diabetes, adults", domain: "adult", outcome: "diag == 'yes'", weight: "wt_mec", source: "CDC National Diabetes Statistics Report · pipeline check", expected: "11.0%" } },
      { kind: "expectation", item: { id: "E2", label: "Undiagnosed, HbA1c ≥ 6.5, adults", domain: "adult", outcome: "diag == 'no' and hba1c >= 6.5", weight: "wt_mec", source: "CDC National Diabetes Statistics Report · pipeline check", expected: "3.0%" } },
      { kind: "expectation", item: { id: "E3", label: "Undiagnosed, HbA1c ≥ 6.5, adults without a routine place of care", domain: "adult and not routine_place", outcome: "diag == 'no' and hba1c >= 6.5", weight: "wt_mec", source: "Literature prior (citation placeholder)", expected: "3.5%" } },
      { kind: "expectation", item: { id: "E4", label: "Normal HbA1c, adults", domain: "adult", outcome: "hba1c < 6.5", weight: "wt_mec", source: "board/control_seeded.json", expected: "75.0%" } },
      agent("scout", "working", "Estimating E1–E4 on cycle J"),
    ],
  },
  {
    delay: 1600,
    events: [
      act("scout", "surprise", "tool_call", "Estimate E1 (weighted proportion)", {
        code: "taylor_prop(cycle='J', domain=\"adult\", outcome=\"diag == 'yes'\", weight='wt_mec')",
      }),
    ],
  },
  {
    delay: 1200,
    events: [
      act("scout", "surprise", "tool_result", "E1 consistent with prior"),
      { kind: "expectation", item: { id: "E1", observed: "10.8%", status: "consistent" } },
      act("scout", "surprise", "tool_call", "Estimate E2", {
        code: "taylor_prop(cycle='J', domain=\"adult\", outcome=\"diag == 'no' and hba1c >= 6.5\", weight='wt_mec')",
      }),
    ],
  },
  {
    delay: 1300,
    events: [
      act("scout", "surprise", "tool_result", "E2 consistent with prior"),
      { kind: "expectation", item: { id: "E2", observed: "3.2%", status: "consistent" } },
      act("scout", "surprise", "tool_call", "Estimate E3", {
        code: "taylor_prop(cycle='J', domain=\"adult and not routine_place\", outcome=\"diag == 'no' and hba1c >= 6.5\", weight='wt_mec')",
      }),
    ],
  },
  {
    delay: 1400,
    events: [
      act("scout", "surprise", "flag", "E3 departs from its prior: CI excludes the expected value", {
        detail: "Observed share is higher than the prior among adults without a routine place of care.",
      }),
      { kind: "expectation", item: { id: "E3", observed: "6.1%", status: "discrepancy" } },
      act("scout", "surprise", "tool_call", "Estimate E4", {
        code: "taylor_prop(cycle='J', domain=\"adult\", outcome=\"hba1c < 6.5\", weight='wt_mec')",
      }),
    ],
  },
  {
    delay: 1300,
    events: [
      act("scout", "surprise", "flag", "E4 departs from its prior"),
      { kind: "expectation", item: { id: "E4", observed: "88.9%", status: "discrepancy" } },
      agent("scout", "done", "2 discrepancies found"),
      agent("supervisor", "working", "Routing discrepancies"),
      act("supervisor", "surprise", "handoff", "Delegated to Skeptic: check definitions of E3 and E4 before anyone builds on them"),
    ],
  },
  {
    delay: 1500,
    events: [
      agent("supervisor", "idle"),
      agent("skeptic", "working", "Checking definitions of E3 and E4"),
      act("skeptic", "surprise", "thought", "E4 defines 'normal' as HbA1c < 6.5", {
        detail: "ADA thresholds in sparklab/config.py: normal is HbA1c < 5.7. Values from 5.7 to 6.4 are prediabetes. E4 mixes normal and prediabetes, so it measures a different quantity than its prior.",
      }),
    ],
  },
  {
    delay: 1700,
    events: [
      act("skeptic", "surprise", "flag", "E4 rejected: definition error, not a finding"),
      { kind: "expectation", item: { id: "E4", status: "definition_error", note: "Normal must be HbA1c < 5.7 (ADA). Caught by the Skeptic." } },
      { kind: "ledger", type: "flag", origin: "agent:skeptic", summary: "E4 rejected: definition error (normal = HbA1c < 5.7)", hash: "3f9a…c21e" },
    ],
  },
  {
    delay: 1500,
    events: [
      act("skeptic", "surprise", "thought", "E3 domain and outcome match the board spec; weights correct (wt_mec with HbA1c)", {
        detail: "No definition problem found. The discrepancy stands.",
      }),
      agent("skeptic", "done", "Definitions checked"),
      agent("supervisor", "waiting", "Waiting for you to pick a discrepancy"),
      {
        kind: "chat",
        from: "supervisor",
        text: "One discrepancy survived the definition check: E3 (adults without a routine place of care). E4 was a seeded definition error and the Skeptic caught it. Should the team pursue E3?",
      },
      act("supervisor", "surprise", "gate", "Waiting for a human to choose which discrepancy to pursue"),
    ],
    gate: "pick-surprise",
  },

  // ── Propose ─────────────────────────────────────────────────
  {
    delay: 1400,
    events: [
      { kind: "stage", stage: "propose" },
      agent("supervisor", "working", "Briefing the Scout"),
      act("supervisor", "propose", "handoff", "Delegated to Scout: write rival hypotheses for E3, including a null and an artifact explanation"),
    ],
  },
  {
    delay: 1500,
    events: [
      agent("supervisor", "idle"),
      agent("scout", "working", "Writing rival hypotheses"),
      act("scout", "propose", "thought", "A good set of rivals must include: a definition artifact, a null, and substantive subgroup patterns that predict different things"),
    ],
  },
  {
    delay: 1500,
    events: [
      act("scout", "propose", "tool_result", "H0 proposed: null"),
      { kind: "hypothesis", item: { id: "H0", kind: "null", title: "Sampling noise", statement: "E3 is a chance departure. No subgroup within it differs from the overall undiagnosed share.", prediction: "In the hold-out, the prevalence ratio for any pre-specified subgroup is compatible with 1." } },
    ],
  },
  {
    delay: 1300,
    events: [
      act("scout", "propose", "tool_result", "H1 proposed: definition artifact"),
      { kind: "hypothesis", item: { id: "H1", kind: "artifact", title: "Case definition mismatch", statement: "The prior counts HbA1c ≥ 6.5 OR fasting glucose ≥ 126. We count HbA1c only, so the comparison is not like-for-like.", prediction: "Aligning the definition (adding fasting glucose with wt_fast) closes most of the gap." } },
    ],
  },
  {
    delay: 1300,
    events: [
      act("scout", "propose", "tool_result", "H2 proposed: insurance"),
      { kind: "hypothesis", item: { id: "H2", kind: "substantive", title: "Concentrated among uninsured adults", statement: "Within adults without a routine place of care, the excess undiagnosed share concentrates in those without health insurance.", prediction: "Prevalence ratio (uninsured vs insured) > 1 in the hold-out." } },
    ],
  },
  {
    delay: 1300,
    events: [
      act("scout", "propose", "tool_result", "H3 proposed: age"),
      { kind: "hypothesis", item: { id: "H3", kind: "substantive", title: "Concentrated among adults aged 20–44", statement: "The excess concentrates among younger adults without a routine place of care.", prediction: "Prevalence ratio (20–44 vs 45+) > 1 in the hold-out." } },
    ],
  },
  {
    delay: 1300,
    events: [
      act("scout", "propose", "tool_result", "H4 proposed: narrow subgroup"),
      { kind: "hypothesis", item: { id: "H4", kind: "substantive", title: "Uninsured adults aged 20–34", statement: "The excess is driven by uninsured adults aged 20–34 without a routine place of care.", prediction: "This cell shows the highest undiagnosed share of any subgroup." } },
      agent("scout", "done", "5 rival hypotheses proposed"),
      { kind: "ledger", type: "hypotheses", origin: "agent:scout", summary: "5 rival hypotheses proposed for E3 (H0–H4)", hash: "a71b…0e94" },
    ],
  },
  {
    delay: 1500,
    events: [
      agent("supervisor", "working", "Routing hypotheses to the Skeptic"),
      { kind: "chat", from: "supervisor", text: "The Scout proposed 5 rival hypotheses for E3, including a null (H0) and a definition artifact (H1). Sending them to the Skeptic." },
      act("supervisor", "propose", "handoff", "Delegated to Skeptic: attack H0–H4"),
    ],
  },

  // ── Attack ──────────────────────────────────────────────────
  {
    delay: 1400,
    events: [
      { kind: "stage", stage: "attack" },
      agent("supervisor", "idle"),
      agent("skeptic", "working", "Attacking H1"),
      { kind: "hypothesis", item: { id: "H1", status: "under_attack" } },
      act("skeptic", "attack", "tool_call", "Re-estimate E3 with the prior's case definition", {
        code: "taylor_prop(cycle='J', domain=\"adult and not routine_place and wt_fast > 0\", outcome=\"diag == 'no' and (hba1c >= 6.5 or glucose >= 126)\", weight='wt_fast')",
      }),
    ],
  },
  {
    delay: 1600,
    events: [
      act("skeptic", "attack", "tool_result", "Aligned definition leaves the gap open"),
      { kind: "attack", hypothesisId: "H1", attack: { kind: "definition", text: "Aligning the case definition moves the estimate but the departure from the prior remains.", passed: false } },
      { kind: "hypothesis", item: { id: "H1", status: "killed", outcomeNote: "Definition alignment does not close the gap." } },
      agent("skeptic", "working", "Attacking H4"),
      { kind: "hypothesis", item: { id: "H4", status: "under_attack" } },
      act("skeptic", "attack", "tool_call", "Power gate: count respondents in the H4 cell", {
        code: "cell_n(cycle='J', domain=\"adult and not routine_place and not insured and age >= 20 and age <= 34\")",
      }),
    ],
  },
  {
    delay: 1500,
    events: [
      act("skeptic", "attack", "flag", "Power gate rejects H4: cell below MIN_CELL_N = 30"),
      { kind: "attack", hypothesisId: "H4", attack: { kind: "power", text: "Unweighted cell size is below MIN_CELL_N = 30. Any estimate would be unstable.", passed: false } },
      { kind: "hypothesis", item: { id: "H4", status: "blocked", cellN: "18", outcomeNote: "Too few respondents to test." } },
      { kind: "ledger", type: "power_gate", origin: "agent:skeptic", summary: "H4 rejected by power gate (n below 30)", hash: "c08d…77a2" },
      agent("skeptic", "working", "Attacking H3"),
      { kind: "hypothesis", item: { id: "H3", status: "under_attack" } },
    ],
  },
  {
    delay: 1600,
    events: [
      act("skeptic", "attack", "thought", "Age and insurance overlap heavily in this domain", {
        detail: "Testing H3 and H2 separately would double-count the same respondents. H3 is merged into H2 as an age-stratified secondary check.",
      }),
      { kind: "attack", hypothesisId: "H3", attack: { kind: "confound", text: "Age and insurance status overlap heavily. Not separable as an independent test.", passed: false } },
      { kind: "hypothesis", item: { id: "H3", status: "merged", outcomeNote: "Merged into H2 as a stratified check." } },
      agent("skeptic", "working", "Attacking H2"),
      { kind: "hypothesis", item: { id: "H2", status: "under_attack" } },
    ],
  },
  {
    delay: 1500,
    events: [
      act("skeptic", "attack", "tool_call", "Power gate: count respondents in H2 cells", {
        code: "cell_n(cycle='J', domain=\"adult and not routine_place and not insured\")",
      }),
    ],
  },
  {
    delay: 1400,
    events: [
      act("skeptic", "attack", "tool_result", "H2 cells pass the power gate"),
      { kind: "attack", hypothesisId: "H2", attack: { kind: "power", text: "Both comparison cells are above MIN_CELL_N = 30.", passed: true } },
      act("skeptic", "attack", "thought", "Could pregnancy exclusions explain H2?", {
        detail: "Checked: excluding pregnant respondents does not change the pattern. Using the label 'no insulin or pills declared currently' for the treatment column.",
      }),
      { kind: "attack", hypothesisId: "H2", attack: { kind: "alternative", text: "Excluding pregnant respondents does not remove the pattern.", passed: true } },
    ],
  },
  {
    delay: 1500,
    events: [
      { kind: "hypothesis", item: { id: "H2", status: "survives", cellN: "412", outcomeNote: "Survived definition, power and alternative checks." } },
      { kind: "hypothesis", item: { id: "H0", status: "rival", outcomeNote: "Kept as the rival H2 is tested against." } },
      agent("skeptic", "done", "Attacks complete"),
      { kind: "ledger", type: "attack_summary", origin: "agent:skeptic", summary: "H2 survives; H0 kept as rival; H1 killed; H3 merged; H4 power-gated", hash: "5e12…b3f0" },
      { kind: "chat", from: "supervisor", text: "H2 (uninsured adults) survived the Skeptic's attacks and will be tested against the null H0. The Experimenter is drafting a pre-registration." },
    ],
  },

  // ── Run ─────────────────────────────────────────────────────
  {
    delay: 1400,
    events: [
      { kind: "stage", stage: "run" },
      agent("experimenter", "working", "Drafting pre-registration P-001"),
      act("supervisor", "run", "handoff", "Delegated to Experimenter: pre-register H2 vs H0"),
      {
        kind: "prereg",
        patch: {
          id: PREREG_ID,
          hypothesisId: "H2",
          rivalId: "H0",
          domain: "adult and not routine_place",
          outcome: "diag == 'no' and hba1c >= 6.5",
          comparison: "not insured  vs  insured",
          weight: "wt_mec",
          estimator: "prevalence_ratio (log-PR, Taylor linearization over SDMVSTRA/SDMVPSU)",
          decisionRule:
            "verdict(): supported if the 95% CI lies entirely above 1; incompatible if it lies entirely below 1; otherwise inconclusive.",
          status: "draft",
        },
      },
    ],
  },
  {
    delay: 1800,
    events: [
      act("experimenter", "run", "tool_call", "Register the protocol", { code: "register_prereg('P-001')" }),
    ],
  },
  {
    delay: 1400,
    events: [
      act("experimenter", "run", "tool_result", "P-001 registered with protocol hash and git commit"),
      { kind: "prereg", patch: { status: "registered", hash: "sha256:9c4e1f…a7d2", commit: "4b7e2a1" } },
      { kind: "ledger", type: "prereg", origin: "agent:experimenter", summary: "P-001 registered (H2 vs H0)", hash: "9c4e…a7d2" },
      agent("experimenter", "waiting", "Waiting for human approval of P-001"),
      { kind: "chat", from: "supervisor", text: "P-001 is registered. Nothing touches the hold-out until a human approves it. Please review the protocol." },
      act("experimenter", "run", "gate", "Waiting for a human to approve P-001"),
    ],
    gate: "approve",
  },
  {
    delay: 1000,
    events: [
      agent("experimenter", "waiting", "Waiting for the hold-out to be unsealed"),
      { kind: "chat", from: "supervisor", text: "P-001 approved. The hold-out (cycle I) is still sealed. Unsealing is a one-time human action, after which the test runs exactly once." },
      act("experimenter", "run", "gate", "Waiting for a human to unseal the hold-out"),
    ],
    gate: "unseal",
  },
  {
    delay: 1400,
    events: [
      agent("experimenter", "working", "Running P-001 on the hold-out"),
      act("experimenter", "run", "tool_call", "Run the pre-registered test (single look)", { code: "run_test('P-001')" }),
    ],
  },
  {
    delay: 2200,
    events: [
      act("experimenter", "run", "tool_result", "Test complete: verdict computed by sparklab.stats.verdict"),
      { kind: "prereg", patch: { status: "tested" } },
      {
        kind: "verdict",
        item: {
          preregId: PREREG_ID,
          label: "supported",
          estimate: "1.84",
          ci: ["1.21", "2.79"],
          plot: { lo: 0.42, point: 0.58, hi: 0.8, nullAt: 0.3 },
          interpretation:
            "Within adults without a routine place of care, the undiagnosed share is higher among uninsured adults. This flags a subgroup for confirmatory re-measurement. It is not a clinical or causal claim.",
        },
      },
      { kind: "ledger", type: "test_result", origin: "agent:experimenter", summary: "P-001 verdict: supported (hold-out look 1 of 1)", hash: "e6a0…41cc" },
      agent("experimenter", "done", "Test complete"),
    ],
  },

  // ── Keep / Kill ─────────────────────────────────────────────
  {
    delay: 1500,
    events: [
      { kind: "stage", stage: "keepkill" },
      agent("supervisor", "working", "Summarizing the verdict"),
      act("supervisor", "keepkill", "thought", "Summarize without causal or clinical language; data are cross-sectional"),
    ],
  },
  {
    delay: 1600,
    events: [
      agent("supervisor", "waiting", "Waiting for your decision"),
      {
        kind: "chat",
        from: "supervisor",
        text: "P-001 returned 'supported'. Suggested next step: flag uninsured adults without a routine place of care for confirmatory re-measurement. Your call: keep, kill or revise.",
      },
      act("supervisor", "keepkill", "gate", "Waiting for a human keep / kill / revise decision"),
    ],
    gate: "decision",
  },
  {
    delay: 1000,
    events: [
      agent("supervisor", "done", "Cycle complete"),
      agent("scout", "idle"),
      agent("skeptic", "idle"),
      agent("experimenter", "idle"),
      act("supervisor", "keepkill", "thought", "SPARK cycle complete. The ledger holds the full audit trail."),
    ],
  },
]

// Events produced when a human resolves a gate.
export function resolveGate(gate: GateId, input: { text?: string; decision?: Decision; by?: string } = {}): SparkEvent[] {
  const by = input.by ?? "you"
  switch (gate) {
    case "objective": {
      const text = input.text?.trim() || DEFAULT_OBJECTIVE
      return [
        { kind: "objective", text },
        { kind: "chat", from: "human", text },
        act("human", "surprise", "human", "Objective set"),
        { kind: "ledger", type: "objective", origin: "human", summary: "Study objective set", hash: "1d2c…9b40" },
      ]
    }
    case "pick-surprise":
      return [
        { kind: "chat", from: "human", text: "Pursue E3." },
        act("human", "surprise", "human", "Chose to pursue E3"),
        { kind: "ledger", type: "surprise_selected", origin: "human", summary: "E3 selected for investigation", hash: "7a3e…12f8" },
      ]
    case "approve":
      return [
        { kind: "prereg", patch: { status: "approved", approvedBy: by } },
        act("human", "run", "human", "Approved P-001"),
        { kind: "ledger", type: "approve", origin: "human", summary: `P-001 approved by ${by}`, hash: "b5f7…0c3a" },
      ]
    case "unseal":
      return [
        { kind: "prereg", patch: { status: "unsealed", holdoutHash: "sha256:2e8b…f019 ✓ verified" } },
        act("human", "run", "human", "Unsealed hold-out cycle I (hash verified)"),
        { kind: "ledger", type: "unseal", origin: "human", summary: "Hold-out cycle I unsealed; SHA-256 matched ledger", hash: "2e8b…f019" },
      ]
    case "decision": {
      const d = input.decision ?? "keep"
      const label = { keep: "Keep", kill: "Kill", revise: "Revise" }[d]
      return [
        { kind: "decision", decision: d, note: input.text },
        { kind: "chat", from: "human", text: `${label}.${input.text ? ` ${input.text}` : ""}` },
        act("human", "keepkill", "human", `Decision: ${label}`),
        { kind: "ledger", type: "decision", origin: "human", summary: `Decision on P-001: ${label}`, hash: "f4d9…6e27" },
      ]
    }
  }
}
