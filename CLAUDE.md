# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

This is the **packaged distribution** of the `deep-understanding-tutor` Claude
Skill — an adaptive tutoring system. It is *not* a normal source checkout and is
not a git repository. On disk there are only three artifacts:

- `SKILL.md` — the skill's instructions (a copy, identical to the one inside the bundle).
- `deep-understanding-tutor.skill` — the actual skill bundle (a ZIP archive). **The real source lives here.**
- `deep-understanding-tutor.zip` — the redistributable, containing `SKILL.md` + the `.skill` bundle.

The engine and reference docs are **only inside the `.skill` archive** — they are
not extracted on disk. The bundle's internal layout is:

```
deep-understanding-tutor/
  SKILL.md
  scripts/tutor_engine.py        # the deterministic engine (~1000 lines, stdlib only)
  references/pedagogy.md         # learning science + how to act on it
  references/question-design.md  # probe formats, grading rubrics, hint ladder
  references/algorithms.md       # the math (BKT, FSRS-lite, calibration)
  references/data-model.md       # profile.json / sessions.jsonl formats
  references/design-rationale.md # how this maps to the research / other skills
```

## Editing the skill (extract → edit → repackage)

Because source lives inside the archive, edits require unpacking and repacking.
Both `.skill` and `.zip` are plain ZIPs.

```bash
# Extract to inspect or edit
unzip -o deep-understanding-tutor.skill -d /tmp/dut && cd /tmp/dut/deep-understanding-tutor

# Run / test the engine after editing
python3 scripts/tutor_engine.py selftest        # built-in invariant tests — run after ANY engine change
python3 scripts/tutor_engine.py --help

# Repackage (the .skill is a zip whose top dir is deep-understanding-tutor/)
cd /tmp/dut && zip -r deep-understanding-tutor.skill deep-understanding-tutor
```

When changing the skill, keep the **three on-disk artifacts consistent**: the
top-level `SKILL.md`, the `SKILL.md` inside the `.skill` bundle, and the `.skill`
nested inside the `.zip` must all match (they currently are byte-identical).
After editing, rebuild the `.skill`, copy its `SKILL.md` to the top level, and
rebuild the `.zip` from `SKILL.md` + the new `.skill`.

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
