# Question design, grading, and feedback

How to write probes for each depth rung, build misconception-driven
distractors, grade open answers against rubrics, run the hint ladder, and
phrase confidence elicitation. Use this every session.

## General rules

- **One concept, one question.** If answering needs two unintroduced concepts,
  the question is mis-rung or the map needs an edge.
- **Vary surface features** across encounters with the same concept: new
  numbers, new domain, new phrasing. Identical repeats train pattern-matching
  on the question, not the concept.
- **Match format to evidence value.** A 4-option MCQ correct is 25%-guessable;
  the engine knows (`--format mcq4`). When you need strong evidence — promotion
  probes especially — prefer open, teachback, applied, or transfer formats.
- **Never stack questions.** Ask one, wait, grade, feed back, record, next.
- Honor the plan's `format_suggestion` unless you have a reason not to.

## Probe templates by rung

### Rung 1 — Recall
- MCQ (4 options, see distractor design below), cloze ("The posterior is
  proportional to ___ × ___"), or a one-line free response ("In one sentence,
  what is a conjugate prior?").
- Keep them fast: recall items are scheduler fuel, not the main event.

### Rung 2 — Explain
- Teach-back: "Explain X to someone who knows [prerequisite] but not X.
  No formulas allowed." (Feynman move — jargon is a hiding place.)
- Mechanism: "WHY does X hold? Walk me through it."
- Derivation-lite: "Starting from [prereq], get me to X."
- Prediction-with-reason: "What happens to the posterior if the prior gets
  flatter — and why?"
- **Always one probe deeper before crediting** ("you said it 'renormalizes' —
  what exactly gets renormalized, and why must it?").

### Rung 3 — Apply
- Standard problem with realistic numbers/setup. New surface every time.
- Completion problems while fading worked examples: "I've set up the
  likelihood and prior; you do the update step."
- After a correct answer, occasionally ask "why did that step work?" — catches
  plug-and-chug.

### Rung 4 — Connect (transfer & discrimination)
- **Far transfer**: same structure, alien clothing. ("A spam filter has seen 3
  spammy words... medical test... A/B test ending early" — for Bayes.)
- **Discrimination**: "Here are two scenarios; one is a conditional-probability
  question, one is a joint-probability question. Which is which, and what's
  the tell?"
- **Boundary**: "Give me a situation where applying X would be a mistake."
- **Connection**: "How does X relate to [other learned concept]? Where do they
  meet, where do they part?"

### Rung 5 — Extend
- Critique: "Here's a (flawed) analysis using X. Find the problem."
- Design: "Construct a problem whose answer hinges on X — and solve it."
- Limits: "Under what assumptions does X break? What would you reach for then?"
- Synthesis: "Argue for or against: [provocative claim about the concept]."

## Misconception-driven distractors (MCQs)

Each wrong option should be a *diagnosis*, not filler. Build distractors from:
1. The concept's **active/resolved misconceptions** in the profile (best
   source — it's this learner's actual failure modes).
2. **Canonical confusions** for the domain (e.g., P(A|B) vs P(B|A); correlation
   vs causation; confusing a definition with its converse).
3. **Right idea, wrong step**: the answer you'd get with one specific error.

When the learner picks a diagnostic distractor, you instantly know *which*
wrong model fired — feed that into refutation feedback and, if it's stable,
`--misconception`. Avoid joke options and "all of the above"; they waste a
diagnostic slot.

## Confidence elicitation

After their answer, before any reveal:
> "Before I tell you — how confident are you, 0–100%?"

Keep it light and quick; a number, not an essay. If a learner finds it
annoying, offer coarse bins (sure / pretty sure / coin flip / guessing → 95 /
75 / 50 / 25) or let them skip it (just omit `--confidence`). Never reveal
correctness first and ask confidence after — post-hoc confidence is worthless
for calibration.

## Grading open answers

Default rubric (Explain/teach-back). Score each criterion pass/fail:

| Criterion | Passes when… |
|---|---|
| **Core mechanism** | the *why* is present, not just the *what* |
| **Own words** | no leaning on undefined jargon or memorized phrasing |
| **Correct boundaries** | no overclaim; conditions/assumptions respected |
| **Survives one probe** | holds up under one "why/what-if" follow-up |

- 4/4 → `--correct 1`, rating `good` (or `easy` if instant and confident).
- 3/4 with the miss being minor wording → probe once more; if repaired
  unaided, `--correct 1 --hinted` (rating `hard`).
- Core mechanism absent, or collapses under the probe → `--correct 0`. Be
  kind in words, honest in data: "you've got the shape of it — the engine's
  going to want another pass at the 'why', and so do I."

Applied/transfer answers: grade the **setup and reasoning**, not arithmetic
slips. A right method with a dropped sign is `--correct 1` with a note; a
correct number from a wrong method is `--correct 0` (and say why — that one's
important).

**Partial credit does not exist in the data.** Round down. The mastery model
self-corrects fast with honest inputs and slowly with flattering ones.

## The hint ladder (use on request or visible stall)

Offer rungs one at a time; each rung used → at best `--hinted`:

1. **Orient** — restate the question, highlight what's actually being asked.
   ("Notice it's asking for P(disease | positive), not the reverse.")
2. **Conceptual nudge** — name the relevant concept or principle, no mechanics.
   ("This is a job for the law of total probability.")
3. **Structural hint** — give the skeleton, they fill it. ("Set up
   numerator = prior × likelihood; what goes in each slot?")
4. **Worked solution** — full walkthrough with self-explanation prompts
   ("before I do the last step — what must it accomplish?"). This counts as
   `--correct 0` for the attempt; schedule a fresh-surface variant later in
   the session or flag it for next time.

## Feedback shapes

- **Correct** → confirm + one connective sentence (tie to prior concept or a
  real use). Stop. Post-success lectures dilute the win.
- **Wrong** → refutation triple: (1) name the wrong model that likely produced
  the answer, (2) show concretely where it fails (counterexample beats
  assertion), (3) rebuild the correct model. Then a restate-in-own-words.
- **Confidently wrong** (engine flags `hypercorrection_moment`) → same triple,
  but slower and more vivid: a concrete, surprising counterexample they'll
  remember. This is the best learning moment available; spend 2–3x normal
  time here.
- **"Close but mushy"** → don't relitigate the whole answer; probe the one
  soft spot.

## Worked-example pattern for `mode: new`

1. **Hook** (one line): why this concept exists / what breaks without it.
2. **Worked instance**: small, concrete, fully explicit.
3. **Self-explanation prompt**: learner explains one chosen step ("why divide
   by P(B) here?") — Constructive, not passive.
4. **Recall check**: the item's actual question, recorded normally.
Keep total teach time short (2–4 minutes of reading); depth comes from the
ladder, not from the lecture.
