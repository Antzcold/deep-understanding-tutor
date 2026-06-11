# AGENTS.md

Guidance for AI coding agents working in this repository. (Claude Code, and
other agents that read `AGENTS.md`, load this automatically.)

## What this repository is

The `deep-understanding-tutor` Agent Skill — an adaptive tutoring system. **The
repository root _is_ the skill**: the loose files at the top level are the
source of truth and are directly usable as a skill (no unzip step).

```
SKILL.md                       # the instructions the LLM follows when tutoring
scripts/tutor_engine.py        # the deterministic engine (~1000 lines, stdlib only)
references/pedagogy.md         # learning science + how to act on it
references/question-design.md  # probe formats, grading rubrics, hint ladder
references/algorithms.md       # the math (BKT, FSRS-lite, calibration)
references/data-model.md       # profile.json / sessions.jsonl formats
references/design-rationale.md # how this maps to the research / other skills
package.sh                     # builds the distributable archives from source
```

## Editing the skill

Edit the loose source files directly, then run the engine selftest:

```bash
python3 scripts/tutor_engine.py selftest        # invariant tests — run after ANY engine change
python3 scripts/tutor_engine.py --help
```

### Building the distributable archives

`deep-understanding-tutor.skill` (the bundle) and `deep-understanding-tutor.zip`
(SKILL.md + the bundle, for upload) are **build artifacts** — gitignored, not
committed. They are needed only for uploading to claude.ai/Desktop or sharing a
single file. Regenerate them from source with:

```bash
./package.sh          # runs selftest, then rebuilds both archives
```

Distribution is via **GitHub Releases**: `package.sh` builds the archive and it
is attached to a tagged release (`gh release create vX.Y.Z deep-understanding-tutor.skill`).
Never commit the archives — they would silently go stale against the source.

## Architecture: who does what

The hard architectural boundary is **LLM teaches, engine computes**:

- **The LLM (this skill's instructions in `SKILL.md`)** does all teaching —
  explanations, question generation, grading open answers, feedback, judgment.
- **`scripts/tutor_engine.py`** does *all* the math and bookkeeping. Never
  compute probabilities, intervals, or due dates by hand — LLM arithmetic
  drifts and the learner's schedule depends on exactness. This is a hard rule in
  `SKILL.md`, not a style preference.

The engine is **stdlib-only, Python 3.9+, no network, no dependencies.** All
learner state stays local.

### The engine pipeline

Every CLI call is `python3 $ENGINE --dir <DATA> <command>`. The lifecycle:

```
init  →  add-concepts  →  plan  →  record  →  dashboard
         (concept DAG)   (per   (per      (wrap-up)
                          session) answer)
```

Key subcommands (`cmd_*` functions in `tutor_engine.py`):
- `init` — create the learner `profile.json`.
- `template` / `add-concepts --file` — load the prerequisite concept map (a DAG; the engine rejects cycles).
- `plan` — compute the ordered, interleaved session plan (remediate → due reviews → promotions → new) as JSON, plus `coach_notes`.
- `record` — log one answer; updates BKT mastery + the spaced-repetition schedule; returns `guidance` directives the LLM must act on.
- `resolve-misconception` / `dashboard` / `selftest`.

### Core models inside the engine

- **BKT (Bayesian Knowledge Tracing)** — mastery `P(learned)`, tracked
  **separately per depth rung** (1 Recall → 5 Extend). `FORMAT_PARAMS` sets
  guess/slip per question format (an MCQ correct answer is weaker evidence than
  a teach-back). See the `# BKT` block near the top of the file.
- **Depth ladder** — promotion to the next rung is gated on strong spaced
  evidence (`PROMOTE_P`, `PROMOTE_MIN_CORRECT`, multiple distinct days, no active
  misconceptions). Promotion resets the evidence bar.
- **Scheduler** — FSRS-lite by default, SM-2 selectable via `settings`.
- **Calibration** — Brier scores from confidence-before-reveal; flags
  hypercorrection windows (wrong-with-high-confidence).
- **Misconception ledger** — logged verbatim; the planner keeps routing to a
  concept until the misconception is resolved.

### Persistence (`Store` class)

State lives entirely in `--dir <DATA>` (default `./tutor-data`, overridable via
`TUTOR_DATA_DIR`):
- `profile.json` — full learner state; written atomically (temp file + `os.replace`), with a `.bak` kept on every save.
- `sessions.jsonl` — append-only event log.
- `.gitignore` — the engine **self-gitignores** the data dir (`*`) so learner
  data never enters version control. Do not undo this.

## Hard rules carried by this skill (do not weaken when editing)

- All math through the engine — no hand-computed values.
- One question at a time; confidence collected before revealing correctness.
- Teach before testing on new material; test before re-teaching on reviews.
- Learner data is local-only and never transmitted.

`references/algorithms.md` and `references/data-model.md` are the authoritative
specs for the math and file formats — consult them before changing engine
behavior or the profile schema.
