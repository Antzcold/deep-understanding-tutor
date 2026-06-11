# Algorithms: the math the engine runs

Everything here is implemented in `scripts/tutor_engine.py` — this document
explains it so you can answer learner questions, tune settings sensibly, and
debug surprising schedules. **Never re-implement any of this in your head.**

## 1. Bayesian Knowledge Tracing (per depth rung)

Classic BKT (Corbett & Anderson, 1995) models a hidden binary "learned" state
per skill. The engine keeps an independent BKT state for **each (concept,
depth-rung) pair** — evidence that you can recall a definition is weak evidence
that you can transfer it.

Parameters:

| Symbol | Meaning | Default |
|---|---|---|
| P(L₀) | prior P(learned) before evidence | 0.20 |
| P(T) | learn-on-opportunity transition | 0.15 |
| P(G) | guess (correct while unlearned) | per format |
| P(S) | slip (wrong while learned) | per format |

Update, given an observation:

```
correct:    post = P(L)(1−S) / [ P(L)(1−S) + (1−P(L))·G ]
incorrect:  post = P(L)·S    / [ P(L)·S    + (1−P(L))(1−S) ]
then:       P(L) ← post + (1−post)·P(T)        (clamped to [0.001, 0.999])
```

**Format-aware guess/slip** (an extension over vanilla BKT — a correct MCQ is
much weaker evidence than a correct teach-back):

| format | guess | slip | notes |
|---|---|---|---|
| mcq4 | 0.25 | 0.10 | 4 options |
| mcq3 | 0.33 | 0.10 | |
| tf | 0.50 | 0.08 | true/false — avoid; weak evidence |
| cloze | 0.15 | 0.10 | |
| open | 0.08 | 0.12 | short free response |
| teachback | 0.05 | 0.15 | explain in own words |
| applied | 0.05 | 0.20 | multi-step → more slips |
| transfer | 0.03 | 0.25 | novel context → most slips |

Override per question with `--guess/--slip` if a particular item is unusually
guessable or slippery.

**Promotion seeding:** entering rung d+1 initializes
`P(L) = max(0.20, P(L at d) − 0.30)` — partial upward transfer, deliberately
conservative.

## 2. Scheduling — FSRS-lite (default)

A compact approximation of the open-source FSRS algorithm's DSR model:
**D**ifficulty (1–10), **S**tability (days for retrievability to fall to 90%),
**R**etrievability (P(recall) now).

Forgetting curve (FSRS-4.5 shape):

```
R(t, S) = (1 + F·t/S)^DECAY        F = 19/81, DECAY = −0.5
interval(S, r) = (S/F)·(r^(1/DECAY) − 1)
```

At the default target retention r = 0.90, `interval = S` exactly.
Lower the target (e.g. 0.85) → longer gaps, more forgetting, fewer reviews;
raise it (e.g. 0.93) → the reverse. Settable via
`settings --target-retention`.

**First review** seeds S and D from the rating
(S₀: again 0.5 / hard 1.5 / good 3 / easy 7 days; D₀: 7.5 / 6.5 / 5.0 / 3.5).

**Successful review** multiplies stability:

```
SInc = 1 + e^1.5 · (11 − D) · S^(−0.08) · (e^(1−R) − 1) · mult
mult: hard 0.55, good 1.0, easy 1.5            S ← S·max(1.01, SInc)
```

Properties worth knowing: growth is **larger when R has decayed more** (the
spacing effect — reviewing at the edge of forgetting pays best), **smaller for
difficult items**, and **saturates** as S grows. Typical growth at on-time
reviews is ~3× per success.

**Lapse (again):**

```
S ← clamp( 1.7 · D^(−0.3) · ((S+1)^0.4 − 1) · e^(1−R),  0.25,  S )
```

Post-lapse stability is a fraction of prior stability, never more.

**Difficulty drifts** with ratings (`D ← 0.95·(D − 0.6·(g−3)) + 0.05·5`,
g: again 1 … easy 4) with mild mean reversion. **Same-day repeats** apply small
fixed multipliers instead of the full model.

**Honesty note:** this is FSRS-*inspired* with hand-set constants, not the
fitted 17+-weight FSRS — see §6 for the upgrade path. For a personal tutor
the shape of the curve matters far more than the third decimal of the weights.

## 3. Scheduling — SM-2 (selectable)

`settings --scheduler sm2` switches to the exact SuperMemo-2 algorithm the
research report recommends for simplicity:

```
quality q: again→1, hard→3, good→4, easy→5
q < 3:  reps←0, interval←1 day
q ≥ 3:  interval ← 1, 6, then round(prev × EF)
        EF ← max(1.3, EF + 0.1 − (5−q)(0.08 + (5−q)·0.02))
```

Under SM-2 the engine mirrors the interval into the stability field so
risk-ordering (§4) still works. FSRS-lite remains the default because its
retrievability term reacts to *when* you actually reviewed, not just how many
times.

## 4. Integration: P(can do it right now)

The report treats knowledge tracing and scheduling as separate gaps. This
skill **combines** them — the planner orders reviews by

```
p_effective = P(L at current rung) × R(now)
```

i.e., "probability the learner has it" × "probability they can retrieve it
today". Lowest first = riskiest first. This mirrors the direction of
memory-aware tracing models like Duolingo's Half-Life Regression (Settles &
Meeder, 2016) and DAS3H (Choffin et al., 2019), in a deliberately simple form.

## 5. Gates, thresholds, calibration

**Unlock:** a concept becomes introducible when every prerequisite has
P(L) ≥ 0.60 at its current rung. **Promotion:** P(L) ≥ 0.85 at the current
rung, ≥ 3 correct there, across ≥ 2 distinct days, with no active
misconceptions. **Remediation:** ≥ 3 attempts with P(L) < 0.35 → the planner
steps the concept down a rung; active misconceptions route to remediation
regardless. **Mastered:** promotion-grade evidence at the target rung.

**Calibration:** each answer with a confidence c ∈ [0,1] adds a Brier
component `(c − outcome)²`. Mean Brier ≈ 0 is perfect calibration; 0.25 is
what flat 50% guessing scores; *rising* means growing miscalibration even if
accuracy is fine. `confidence ≥ 75% ∧ wrong` increments the overconfidence
counter and flags a hypercorrection moment (see pedagogy.md).

**Rating derivation** when `--rating` is omitted: wrong → again; correct with
hints → hard; correct → good; correct with confidence ≥ 90% → easy. When in
doubt, just ask the learner "how hard was that?" and pass it explicitly.

## 6. Known simplifications & upgrade path (extending further)

In rough order of value if you (or the user) want to push beyond this skill:

1. **Fit FSRS weights per learner** from `sessions.jsonl` once a few hundred
   reviews exist (the log already stores every field the FSRS optimizer
   needs: ratings, elapsed intervals, outcomes).
2. **Per-concept BKT parameter fitting** (P(T), P(G), P(S) vary by concept in
   reality; EM over the log is the standard approach).
3. **Forgetting-aware BKT** (BKT assumes no forgetting; the p_effective
   product is a patch — a principled version adds a forget transition).
4. **Deep Knowledge Tracing / attention-based KT** (Piech et al., 2015 and
   successors) — needs more data than one learner usually generates; flag
   honestly if asked.
5. **Item Response Theory** difficulty per *question* (currently difficulty
   lives per concept via FSRS-D and per format via guess/slip).
6. **Desirable-difficulty-aware scheduling**: schedule *harder formats* (not
   just later dates) as stability grows — partially emulated now by the
   rung ladder.
