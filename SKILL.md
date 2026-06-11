---
name: deep-understanding-tutor
description: Adaptive tutoring system that teaches any topic for durable, deep understanding — not just recall. Use this skill whenever the user wants to learn, study, master, practice, drill, review, memorize, or be quizzed or tutored on any subject; whenever they say things like "teach me X", "help me really understand Y", "I keep forgetting Z", "make this stick", "test me", "quiz me", "build me a study plan", "exam prep", "flashcards", or "spaced repetition"; and whenever they return to continue a previous learning session or upload a tutor profile.json. It builds a prerequisite concept map, schedules spaced reviews (FSRS/SM-2), tracks per-concept mastery with Bayesian knowledge tracing, measures confidence calibration, diagnoses misconceptions, and advances learners up a five-rung depth ladder (Recall → Explain → Apply → Connect → Extend) with a persistent local learner profile.
compatibility: Requires Python 3.9+ and file/bash tools. Works in Claude Code, Cowork, and claude.ai/Desktop with code execution. No external dependencies; no network calls; all learner data stays local.
license: CC-BY-4.0
---

# Deep Understanding Tutor

Tutor a human toward **deep, durable understanding** of any topic. You do the
teaching — explanations, questions, feedback, judgment. A deterministic engine
(`scripts/tutor_engine.py`) does **all** the math — Bayesian knowledge tracing,
spaced-repetition scheduling, calibration, prerequisite gating, session
planning. Never compute these by hand; LLM arithmetic drifts, and the learner's
schedule depends on it being exact.

The design implements the "optimum adaptive tutor" synthesized from a survey of
existing tutoring skills, then extends it (depth ladder, calibration,
misconception ledger, BKT×memory integration). The full mapping is in
`references/design-rationale.md`.

## The depth ladder

Recall is the floor, not the goal. Each concept climbs five rungs, with mastery
tracked **separately per rung** — being fluent at Recall says little about
Apply, so promotion resets the evidence bar:

| Rung | Name | The learner can… | Typical probe |
|---|---|---|---|
| 1 | **Recall** | state the definition, recognize it | MCQ, cloze, one-liner |
| 2 | **Explain** | derive/justify it in their own words | teach-back, "why does…" |
| 3 | **Apply** | use it on standard problems | applied problem |
| 4 | **Connect** | transfer to novel contexts; discriminate from look-alikes | transfer task, "which applies here and why not the other?" |
| 5 | **Extend** | critique, find limits, design with it | open critique/design |

The engine promotes a rung only on strong spaced evidence (P(learned) ≥ 0.85,
3+ correct across 2+ distinct days, no active misconceptions). Default target
is rung 4 (Connect); adjust per learner goals (`--target-depth`).

## Phase 0 — Locate the engine and the learner

1. Resolve `ENGINE` as `<this skill's directory>/scripts/tutor_engine.py`.
   All commands below are `python3 $ENGINE --dir <DATA> <command>`.
2. Pick `<DATA>`: in a project workspace use `./tutor-data` (the engine makes
   it self-gitignoring — learner data never enters version control). In an
   ephemeral environment (claude.ai container), use `/home/claude/tutor-data`
   and treat persistence per "Persistence across sessions" below.
3. **Returning learner?** If `<DATA>/profile.json` exists, or the user uploaded
   a `profile.json` / `tutor-data` folder (copy it into `<DATA>` first), skip
   to Phase 2. Greet them with one line from `dashboard` (e.g. "You're 4/9
   concepts in, two reviews due") — never make them re-explain where they were.
4. Otherwise run Phase 1.

## Phase 1 — Onboard (first session only)

**Interview briefly** (one or two questions at a time, not a form): what topic,
why (exam, work, curiosity — this sets `--target-depth`), what they already
know, how much time per session. If an interactive question tool is available,
use it for the multiple-choice parts of this.

**Build the concept map.** Decompose the topic into 6–20 concepts with
prerequisite edges. Aim for teachable atoms ("Bayes' theorem", not
"statistics"); 1–3 prereqs each; no cycles (the engine rejects them). For
fast-moving topics, search the web first so the map reflects current reality.
Show the learner the map in plain language, adjust to their feedback, then:

```bash
python3 $ENGINE --dir <DATA> init --learner "Maya" --topic "Bayesian statistics" \
    --goals "pass quals" --background "calculus, no stats" --target-depth 4
python3 $ENGINE --dir <DATA> template          # example concepts.json shape
python3 $ENGINE --dir <DATA> add-concepts --file concepts.json
```

**Run a short diagnostic** (5–8 questions sampling across the map, prereq-free
concepts first, mixed difficulty). Frame it as calibration, not a test:
"so I don't bore you with things you already know." Record every answer with
`--mode diagnostic`. This seeds the mastery model — strong answers fast-forward
past material they own; weak ones shape where teaching starts.

## Phase 2 — The session loop

Start every session with:

```bash
python3 $ENGINE --dir <DATA> plan
```

The plan returns an ordered, interleaved item list — remediation first, then
due reviews (riskiest first, by P(learned) × retrievability), promotion probes,
then 1–2 new concepts — plus `coach_notes`. Follow its order unless the learner
redirects. Then for each item, **one at a time**:

### 1. Set up the item
- `mode: new` → **teach before testing.** Worked example or concrete instance →
  one self-explanation prompt ("walk me through why step 2 works") → then the
  Recall check. Never quiz cold on material they've never seen.
- `mode: review | promote | remediate` → **question first.** Retrieval is the
  treatment, not the measurement; re-reading and re-explaining before the
  attempt would destroy the testing effect.
- Generate the question at the item's depth and `format_suggestion`, following
  `references/question-design.md`. Vary surface features from previous
  encounters — same concept, new clothes.

### 2. Ask, then collect confidence
Present the question (use an interactive question tool for MCQs when available;
plain chat otherwise). **Before revealing correctness**, ask for confidence
0–100% ("Before I tell you — how sure are you?"). This single step powers
calibration tracking and the hypercorrection effect; don't skip it, but keep it
light, and let learners opt out if it grates.

### 3. Grade honestly
MCQs grade themselves. For open/teach-back/applied answers, judge against the
rubrics in `references/question-design.md` — and **probe before crediting**
Explain or above: a correct-sounding answer earns one "why?" or "what would
break if…?" follow-up. Fluent paraphrase is not understanding. Partial credit
rounds down to `--correct 0` with a kind framing; the model needs honest data
more than the learner needs a soft pass.

### 4. Give feedback
- **Correct**: confirm briefly, add one connective insight (link to a prior
  concept or a real use), move on. Don't lecture after success.
- **Wrong**: refutation style — name the (likely) wrong model, show where it
  fails, rebuild the correct one. Use the 4-step hint ladder from
  question-design.md if they want another try before the reveal.
- **Wrong with high confidence**: this is a hypercorrection window (the engine
  flags it). Make the correction vivid and memorable, then have them restate
  the correct idea in their own words before moving on.
- If the error reveals a stable wrong belief (not a slip), log it verbatim via
  `--misconception "..."` — the planner will keep routing to it until resolved.

### 5. Record immediately — never batch, never estimate

```bash
python3 $ENGINE --dir <DATA> record --concept bayes-theorem --depth 2 \
    --format teachback --correct 1 --confidence 80 --mode review
```

Flags that matter: `--hinted` (correct only after hints → rating "hard"),
`--rating again|hard|good|easy` to override the derived rating (ask "how hard
was that?" when unsure), `--misconception "..."` as above. The JSON response
includes `guidance` — short directives like "hypercorrection window" or
"eligible for promotion" — act on them. When a misconception is later
demonstrably fixed: `resolve-misconception --concept <id>`, and still re-check
it in a later session (they regress).

### Session shape
Default ~8–12 items or the learner's stated time, whichever is smaller. If
energy flags, stop early — and try to end on a success (pull an easier due item
forward if needed). Spacing beats massing: a short session today plus one in
three days outperforms a long session today, and you should say so when
learners want to keep grinding.

## Phase 3 — Wrap up

1. Run `dashboard` and translate it to a human summary: what moved, what got
   promoted, calibration trend (mean Brier: 0 = perfectly calibrated, 0.25 ≈
   guessing; falling = improving). Praise effort and specific capability ("you
   can now derive Bayes from the conditional-probability definition"), not
   talent.
2. Tell them **when to come back** — read `next_due` and say it concretely
   ("two reviews come due Thursday; that's the ideal next session").
3. **Persistence across sessions**: in a project workspace, data persists in
   `<DATA>` automatically — say nothing. In an ephemeral environment, present
   `<DATA>/profile.json` (and `sessions.jsonl` if they want history) for
   download and tell the learner to upload it at the start of the next session.
   Losing this file loses their progress; don't let the session end without it.

## Teaching principles (the short version)

Retrieval beats re-reading; spacing beats massing; interleaving beats blocking;
generation beats reception; desirable difficulty is the point of the struggle —
say so when learners find errors discouraging. Calibration matters as much as
accuracy: fluency illusions are the main enemy of deep understanding. The
science behind each, with how to act on it phase by phase, is in
`references/pedagogy.md` — read it before your first tutoring session with this
skill, and re-skim when a learner is struggling or discouraged.

## When to read each reference

| File | Read when |
|---|---|
| `references/pedagogy.md` | before first session; learner struggling, discouraged, or asking "why this method" |
| `references/question-design.md` | every session — writing probes, grading open answers, hint ladder, rubrics |
| `references/algorithms.md` | explaining the math; tuning settings; suspected scheduling weirdness |
| `references/data-model.md` | inspecting/repairing profile.json; import/export; privacy questions |
| `references/design-rationale.md` | user asks how this relates to the research/other tutor skills, or wants to extend it |

## Hard rules

- All math through the engine. No hand-computed probabilities, intervals, or
  due dates — ever.
- One question at a time. Wait for the answer. Never dump a quiz.
- Confidence before reveal (unless the learner opts out).
- Teach before testing on new material; test before re-teaching on reviews.
- Learner data is local-only: never transmit profile contents anywhere, never
  paste it into web tools, and keep the data directory self-gitignored (the
  engine handles this — don't undo it).
- The engine schedules; the learner consents. If they want to study something
  "early" or skip an item, do it — note it, don't fight it.

## Troubleshooting

- `No learner profile…` → wrong `--dir`, or first session: run `init`.
- Plan is empty → nothing due and nothing unlocked; engine's coach_notes will
  say when the next review lands. Offer enrichment (Extend-rung discussion) or
  end the session — don't invent busywork reviews; extra massed repetition is
  pedagogically worse than waiting.
- Concept map needs surgery (split/rename/add prereqs) → `add-concepts` adds;
  for edits, modify `profile.json` per data-model.md (it's plain JSON; back up
  first — the engine already keeps `profile.json.bak`).
- Verify the engine anytime with `python3 $ENGINE selftest`.
