# Data model, persistence, and privacy

Everything the engine stores, where, and how to move/inspect/repair it.

## File layout

```
<DATA>/                      default ./tutor-data  (or $TUTOR_DATA_DIR)
├── .gitignore               contains "*" — the directory ignores itself
├── profile.json             the learner model (single source of truth)
├── profile.json.bak         automatic backup of the previous save
└── sessions.jsonl           append-only event log (one JSON object per line)
```

Writes are atomic (temp file + rename) and every save first copies the old
profile to `.bak`, so a crash mid-write cannot corrupt state.

## profile.json schema (annotated example)

```jsonc
{
  "version": 1,
  "engine": "1.0.0",
  "created": "2026-06-01",
  "topic": "Bayesian statistics",
  "learner": {
    "name": "Maya",
    "goals": "pass quals",
    "background": "calculus, no stats",
    "settings": {
      "scheduler": "fsrs",          // or "sm2"
      "target_retention": 0.90,     // 0.70–0.97
      "target_depth": 4,            // default mastery rung (1–5)
      "max_items": 10,              // per session plan
      "new_per_session": 2
    }
  },
  "concepts": {
    "bayes-theorem": {
      "name": "Bayes' theorem",
      "summary": "Posterior = likelihood × prior / evidence.",
      "prereqs": ["conditional-probability"],
      "target_depth": 4,            // optional per-concept override
      "depth": 2,                   // current rung (1–5)
      "introduced": "2026-06-06",   // null = never taught
      "sched": {                    // ONE schedule per concept (memory of it)
        "stability": 7.43,          // days; null before first review
        "difficulty": 4.86,         // 1–10 (FSRS-D)
        "last_review": "2026-06-08",
        "due": "2026-06-15",
        "reps": 4, "lapses": 1,
        "sm2": {"interval": 6, "ef": 2.5, "reps": 2}   // present if sm2 used
      },
      "depths": {                   // BKT state PER RUNG (the extension)
        "1": {"p": 0.97, "attempts": 4, "correct": 4,
               "days_correct": ["2026-06-06", "2026-06-08"]},
        "2": {"p": 0.41, "attempts": 1, "correct": 0, "days_correct": []}
      },
      "calibration": {"n": 5, "brier_sum": 0.41, "overconfident_errors": 1},
      "misconceptions": [
        {"text": "believes P(A|B) = P(B|A)", "status": "resolved",
         "noted": "2026-06-06", "resolved": "2026-06-08"}
      ]
    }
  }
}
```

Status values you'll see on the dashboard are **derived**, not stored:
`locked` (prereqs unmet) → `ready` (unlocked, never taught) → `learning` →
`DUE` / `misconception!` → `mastered`.

## sessions.jsonl

One line per event (`init`, `add_concepts`, `plan`, `record`,
`resolve_misconception`). `record` lines carry the full before/after state —
p_before/p_after, stability_before/after, rating, brier, due — which makes the
log sufficient for future re-fitting of scheduler/BKT parameters (see
algorithms.md §6) and for any "show me my history" request:

```bash
grep '"event": "record"' sessions.jsonl | tail -20      # recent answers
python3 - <<'EOF'                                        # accuracy by week, etc.
import json
rows = [json.loads(l) for l in open("tutor-data/sessions.jsonl")
        if '"record"' in l]
...
EOF
```

## Persistence by environment

- **Claude Code / Cowork / any real workspace:** `<DATA>` lives in the
  project; nothing to do. The self-gitignore keeps it out of commits.
- **Ephemeral containers (claude.ai):** the filesystem resets between
  conversations. At session end, present `profile.json` (plus
  `sessions.jsonl` if the learner wants history) for download. Next session,
  the learner uploads it; copy it into `<DATA>/` before running `plan`.
  `profile.json` alone is sufficient to resume perfectly — the log adds
  history, not state.
- **Multiple topics:** one directory per topic
  (`tutor-data/bayes/`, `tutor-data/japanese/`), each with its own profile.

## Privacy commitments (state them if asked; never weaken them)

- All data is local files. The engine makes **zero network calls** — it's
  stdlib-only Python you can read in one sitting.
- The data directory self-gitignores so learner records never reach a repo.
- Never paste profile contents into web tools, search queries, or any
  external service. Quoting a learner's own data back to them in chat is fine
  — it's theirs.
- The profile may contain sensitive signal (what someone struggles with,
  their misconceptions, their goals). Treat it like a medical chart, not like
  config.
- If a learner wants to delete their data: delete `<DATA>`. That's all of it.

## Manual edits & repair

`profile.json` is meant to be human-editable. Safe operations with the engine
idle: renaming a concept's `name`/`summary`, adding/removing `prereqs`
(no cycles — run any engine command afterward; it validates), adjusting
`target_depth`, deleting a concept key (also remove it from others' prereqs).
Avoid hand-editing `sched` or `depths` numbers — that's the model's memory.
If the profile is ever corrupted: `profile.json.bak` is one save behind;
`sessions.jsonl` is the audit trail of everything that happened.
