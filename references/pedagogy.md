# Pedagogy: the science, and what to do about it

This file is the "why" behind every move in SKILL.md, plus concrete behaviors.
Skim before your first session; return when a learner struggles, plateaus, or
asks why the method feels harder than re-reading their notes (it should).

## The core findings this skill is built on

**Retrieval practice (the testing effect).** Actively recalling information
strengthens memory far more than re-studying it (Roediger & Karpicke, 2006).
Dunlosky et al.'s (2013) landmark review of ten learning techniques rated
practice testing and distributed practice as the only two "high utility"
techniques — above highlighting, re-reading, and summarization, which most
learners default to. *Behavior:* on review items, the question always comes
before any re-teaching. The struggle to retrieve IS the intervention. If a
learner says "can you remind me first?", offer the smallest possible cue (hint
ladder rung 1), not the answer.

**Spacing (distributed practice).** Memory consolidates best when practice is
spread over time, with reviews landing near the edge of forgetting (Ebbinghaus,
1885; Cepeda et al., 2006). *Behavior:* the scheduler implements this — trust
it. When a learner wants to "do all my reviews again right now", explain that
re-reviewing today adds almost nothing; the same minutes spent Thursday (when
retrievability has dropped) multiply stability. Tell them when to come back.

**Interleaving.** Mixing related-but-different problem types outperforms
blocked practice of one type at a time, because it forces *discrimination* —
choosing which concept applies, not just executing it (Rohrer & Taylor, 2007).
Blocked practice feels better and performs worse. *Behavior:* the planner
interleaves across concept families; preserve its order. At rungs 3–4, prefer
questions where part of the task is deciding *which* tool applies.

**Desirable difficulties.** Conditions that slow visible performance during
practice — spacing, interleaving, generation, reduced cues — improve long-term
retention and transfer (Bjork, 1994). Errors during effortful retrieval are a
feature. *Behavior:* when a learner is discouraged by errors, say this
explicitly: "the difficulty is the mechanism — easy practice is forgettable
practice." Never optimize a session to feel smooth.

**Generation & self-explanation.** Producing an answer, prediction, or
explanation — even a wrong one — beats receiving the same content
(generation effect; Chi et al., 1989, 1994 on self-explanation). The ICAP
framework (Chi & Wylie, 2014) ranks engagement: Interactive > Constructive >
Active > Passive. *Behavior:* keep the learner in Constructive/Interactive
modes. After a worked example, don't summarize it for them — have *them*
explain a step. Before revealing an outcome, ask them to predict it.

**Worked examples and fading (cognitive load).** Novices learn faster from
studying worked examples than from unsupported problem solving; experts are
the reverse (Sweller's worked-example effect; Kalyuga's expertise reversal).
*Behavior:* this is why `mode: new` teaches before testing — worked example →
self-explanation → check. As mastery rises (the engine's P(L) tells you), fade
support: complete example → completion problem (you do step 3) → full problem.
Don't keep training wheels on a rung-3 learner.

**Mastery learning.** Bloom (1984) found one-on-one tutoring with mastery
checks moved average students ~2 standard deviations above classroom
instruction. The active ingredients: don't advance past unmastered material,
and give immediate corrective feedback. *Behavior:* the prerequisite gating and
promotion thresholds encode this. Resist learner pressure to skip ahead past
shaky prerequisites; instead show them the dashboard and negotiate ("let's
spend five minutes shoring up conditional probability — Bayes will take half
the time if we do").

**Calibration and the illusion of knowing.** Learners' judgments of their own
learning are systematically miscalibrated; fluency (it reads easily, it sounds
familiar) masquerades as knowledge (Koriat & Bjork, 2005). This is *the*
central enemy of deep understanding: people stop studying what they think they
know. *Behavior:* the confidence-before-reveal step makes calibration visible
and trainable. Review the Brier trend at wrap-up. A learner who is often
confident-and-wrong needs more retrieval and less re-reading; tell them so,
gently, with their own numbers.

**The hypercorrection effect.** Errors made with *high* confidence, once
corrected, are remembered *better* than low-confidence errors (Butterfield &
Metcalfe, 2001). Surprise drives encoding. *Behavior:* when the engine flags
`hypercorrection_moment`, slow down. Make the correction vivid — a concrete
counterexample, a memorable contrast — and have the learner restate the
correct idea in their own words before moving on. These are the highest-value
moments in any session; never rush past one.

**Misconceptions need refutation, not repetition.** Stable wrong models (e.g.
"P(A|B) = P(B|A)", "heavier objects fall faster") survive ordinary correct
instruction; refutation texts — explicitly stating the misconception, refuting
it, and supplying the correct model — outperform simply presenting the right
answer. *Behavior:* that three-step structure is the required feedback shape
for any `--misconception`-worthy error. And because misconceptions regress,
re-probe them in a later session even after `resolve-misconception`.

**Productive failure.** Letting learners attempt problems *before* instruction
— and struggle — can produce deeper learning than instruction-first, provided
a consolidation phase follows (Kapur, 2008). *Behavior:* optional spice for
rung 3+ on a new-ish concept: pose the problem first ("try it with what you
have"), let them generate an approach, then teach against their attempt. Use
judgment — it suits curious learners and backfires on anxious ones.

## The depth ladder, pedagogically

The ladder operationalizes "deep understanding" as observable capability, in
the spirit of Bloom's taxonomy and Webb's Depth of Knowledge — without
pretending those frameworks give exact boundaries:

1. **Recall** — necessary substrate. Fast, low-stakes, scheduler-friendly.
2. **Explain** — the Feynman test: derive or justify in own words, no jargon
   shields. Most fluency illusions die here, which is why promotion to rung 2
   is where many learners first feel friction. Normalize it.
3. **Apply** — execute on standard cases. Watch for "plug and chug" success
   that bypasses understanding; one "why did that step work?" probe catches it.
4. **Connect** — the heart of transfer: novel contexts, discriminating between
   look-alike concepts, recognizing when the concept *doesn't* apply. Deep
   understanding largely IS this rung.
5. **Extend** — critique, limits, design. Optional for many goals (it's why
   target depth defaults to 4) but where mastery becomes ownership.

Per-rung tracking exists because evidence at one rung is weak evidence about
the next: the engine deliberately discounts P(learned) on promotion
(`p_new = max(0.2, p_prev − 0.30)`). Treat a freshly promoted learner as a
careful novice at the new rung — scaffold the first item.

## Tone and motivation

- Praise effort, strategy, and specific new capability — not intelligence
  (Dweck's mindset work survives replication better at this behavioral level
  than as a global trait intervention; regardless, "you derived that from
  first principles" is simply more informative than "you're smart").
- Errors get curiosity, not consolation: "interesting — what made that option
  tempting?" surfaces the misconception and dignifies the attempt.
- Keep stakes low and pace humane. One question at a time. Silence while they
  think is fine; don't fill it with hints they didn't ask for.
- End sessions on a win where possible, and always with a concrete next step
  ("two reviews Thursday").
- Respect autonomy: the schedule advises, the learner decides. A learner who
  feels policed quits; one who sees the dashboard's logic usually self-corrects.

## Diagnostic (cold-start) technique

The Phase-1 diagnostic exists to seed the mastery model, not to judge. Sample
across the concept map: prereq-free concepts first, then one or two mid-graph,
mixing formats (an MCQ correct is weak evidence; an open-answer correct is
strong — the engine weighs them differently via guess/slip). Five to eight
items is plenty; stop early if a clear floor emerges. Frame every diagnostic
item as "helping me not waste your time," and record with `--mode diagnostic`.

## When the learner is stuck or sliding

- Two consecutive misses on a concept → drop a rung (the planner will, too) or
  step back to a prerequisite. Going backward to go forward is the mastery-
  learning move, not a defeat.
- Discouragement → name desirable difficulty; show the dashboard's risen P(L)
  on concepts that once felt this hard.
- Boredom with easy items → check calibration: if Brier is good and P(L) high,
  the engine will promote shortly anyway; you can pull a promotion probe
  forward.
- "Just give me the answer" fatigue → shrink the session, end on a success,
  shorten the hint-ladder patience. A small honest session beats an abandoned
  perfect one.
