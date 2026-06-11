# Deep Understanding Tutor

A [Claude](https://claude.com/claude-code) Skill that tutors a human toward
**deep, durable understanding** of any topic — not just recall.

Claude does the teaching (explanations, questions, feedback, judgment). A
deterministic Python engine does **all** the math and bookkeeping, so the
learner's schedule and mastery estimates stay exact:

- **Bayesian Knowledge Tracing** — mastery tracked *separately per depth rung*
- **Spaced repetition** — FSRS-lite by default, SM-2 selectable
- **Confidence calibration** — Brier scores + hypercorrection detection
- **Misconception ledger** — wrong beliefs logged and re-routed until resolved
- **Prerequisite DAG** — unlock gating and topological introduction order
- **Five-rung depth ladder** — Recall → Explain → Apply → Connect → Extend

All learner data stays local (a self-gitignored `tutor-data/` directory); no
network calls, no external dependencies, Python 3.9+ stdlib only.

## Layout

The repository root **is** the skill:

```
SKILL.md                  # the instructions Claude follows when tutoring
scripts/tutor_engine.py   # the deterministic engine (all the math)
references/               # pedagogy, question design, algorithms, data model
```

## Use it

**Claude Code** — point it at this folder, or copy it into your skills
directory. Then ask Claude to "teach me X" / "quiz me on Y" and the skill
activates.

**claude.ai / Desktop** — upload the packaged `.skill` (or `.zip`) from the
[Releases](../../releases) page.

## Build the distributable

The `.skill` / `.zip` archives are build artifacts (not committed). Regenerate
them from source:

```bash
./package.sh        # runs the engine selftest, then builds both archives
```

## Develop

```bash
python3 scripts/tutor_engine.py selftest    # invariant tests — run after any engine change
python3 scripts/tutor_engine.py --help      # CLI: init, add-concepts, plan, record, dashboard
```

See [`CLAUDE.md`](CLAUDE.md) for the architecture and the LLM/engine boundary.

## License

[CC-BY-4.0](LICENSE) — use and adapt freely with attribution.
