# Design rationale: from research report to this skill

This skill was built from a research survey of existing tutoring SKILL.md
repositories (HKUDS/DeepTutor, bevibing/tutor-skills, m98/fluent,
DrCatHicks/learning-opportunities, Bhala-Srinivash/agent-tutor-skill,
GarethManning/education-agent-skills, anthropics/skills). The report
synthesized a "proposed optimum" tutoring skill from the best parts of each.
This file maps every recommendation in that optimum to where and how this
skill implements it, then lists where we deliberately went beyond the report.

## Report recommendation → implementation

| # | Report's recommendation | Where it lives here | Notes |
|---|---|---|---|
| 1 | Rich learner-profile data model (per-concept easiness, intervals, attempt counts; JSON or SQLite) | `profile.json` — schema in data-model.md | We chose JSON over SQLite: human-readable, diffable, portable across ephemeral environments, no dependency. Each concept carries scheduler state, per-rung BKT state, calibration stats, and a misconception ledger — strictly richer than any surveyed skill. |
| 2 | SM-2 or FSRS spaced scheduling | `tutor_engine.py` implements **both**; algorithms.md has the math | FSRS-lite is the default (better-fitting forgetting model; tunable target retention). Exact SM-2 (the report's pseudocode, faithfully) is one `settings --scheduler sm2` away — useful for learners migrating from Anki-classic habits. |
| 3 | Bayesian Knowledge Tracing — flagged as **missing from every surveyed skill** ("most rely on simple counters") | `tutor_engine.py` BKT update on every `record` | Implemented with format-aware guess/slip parameters (an MCQ correct is weaker evidence than a correct transfer task). This was the report's biggest identified gap; it is the core of this skill. |
| 4 | Curriculum adaptation: drill weak areas, surface due reviews, gate on readiness | `plan` command | Orders work remediate → due reviews (riskiest first by p_effective) → promotion probes → limited new material, with prerequisite-DAG unlock gating and light interleaving across concept families. |
| 5 | Persistent local storage across sessions | `tutor-data/` dir; data-model.md | Atomic writes, automatic `.bak`, append-only `sessions.jsonl` event log. Ephemeral environments are handled by exporting/importing `profile.json` (documented in SKILL.md Phase 3 and data-model.md). |
| 6 | Privacy: local-only, gitignored learner data | Engine writes `.gitignore` containing `*` into the data dir on init | Engine is stdlib-only Python with zero network calls. Privacy commitments are spelled out in data-model.md. |
| 7 | Quizzes with explanations and hint ladders | question-design.md | Per-rung question templates, a 4-rung hint ladder with honest crediting rules (full hint ⇒ scored incorrect, retried later as a variant), refutation-style feedback for misconceptions. |
| 8 | Community engagement / sharing | Out of scope by design | A skill shouldn't post anywhere on a learner's behalf. The nearest in-spirit feature: profiles and concept maps are portable JSON a learner can share deliberately. |

The report's proposed session workflow (load profile → check due → generate
questions → quiz → rate recall → SM-2 update → save → dashboard) is exactly
SKILL.md's Phase 2 loop, with two upgrades: recall ratings are **derived**
from observables (correctness, hints, confidence) rather than self-reported,
and every answer updates *both* the memory model and the BKT mastery model.

## Extensions beyond the report

The user asked us to extend the research where possible. These are the
substantive additions, each grounded in learning science (citations in
pedagogy.md):

- **E1 — Depth ladder (the "deep understanding" core).** Five rungs: Recall →
  Explain → Apply → Connect → Extend, with BKT tracked *separately per
  (concept, rung)*. Surveyed skills track "do you remember X"; none could
  represent "remembers X but can't apply it." Promotion requires P(L) ≥ 0.85,
  ≥ 3 correct, ≥ 2 distinct days, and no active misconceptions — so mastery
  claims survive a night's sleep, not just a hot streak.
- **E2 — BKT × memory integration.** Review priority uses
  p_effective = P(mastery) × R(retrievability): the concept most at risk is
  the one you've half-learned *and* half-forgotten. This mirrors the direction
  of half-life-regression / DAS3H research rather than treating knowledge and
  memory as separate ledgers.
- **E3 — Calibration tracking.** Confidence (0–100) is elicited *before* every
  reveal; Brier scores accumulate per concept; confident-but-wrong answers are
  flagged for hypercorrection-style vivid feedback. No surveyed skill measured
  whether the learner's self-assessment could be trusted.
- **E4 — Misconception ledger.** Specific false beliefs are recorded verbatim,
  block promotion while active, route the concept into remediation, and are
  resolved only after the learner demonstrates the correction. Refutation
  feedback (state the misconception → refute it → explain the correct model)
  is the prescribed response shape.
- **E5 — Prerequisite DAG.** Concepts declare prereqs; the engine
  topologically orders introductions, refuses to unlock a concept until its
  prereqs reach P(L) ≥ 0.60, and rejects cyclic maps at load time. Surveyed
  skills ordered material by list position.
- **E6 — Teach-back and transfer assessment.** Rubrics for scoring a
  learner's own explanation (4 criteria, partial credit rounds *down*) and
  far-transfer tasks as the only evidence accepted at rung 5.
- **E7 — Format-aware evidence weighting.** BKT guess/slip vary by question
  format (MCQ-4: g=.25; true/false: g=.50; open response: g=.08; transfer:
  g=.03 …), so the model knows a lucky multiple-choice hit from a constructed
  proof. Surveyed skills weighted all correctness equally.

## Future work (hooks already in place)

`sessions.jsonl` logs full before/after state on every record precisely so
that later versions can: fit per-learner FSRS weights from review history,
EM-fit per-concept BKT parameters, add forgetting-aware BKT, or swap in
DKT/IRT models — see algorithms.md §6. None of that requires a schema change.

## Honest limitations

BKT/FSRS parameters are literature-informed defaults, not fitted to any
individual (yet). The depth ladder is a pedagogical scaffold inspired by
Bloom-style taxonomies, not a validated psychometric scale. The engine
guarantees the bookkeeping is principled; the *teaching* quality still
depends on the model following pedagogy.md and question-design.md faithfully.
