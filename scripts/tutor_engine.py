#!/usr/bin/env python3
"""
tutor_engine.py — deterministic core of the deep-understanding-tutor skill.

The LLM does the teaching; this engine does ALL the math and bookkeeping:

  * Bayesian Knowledge Tracing (BKT), tracked separately per depth level
  * FSRS-lite spaced-repetition scheduling (SM-2 available via settings)
  * Confidence calibration (Brier scores, hypercorrection flags)
  * Misconception ledger
  * Prerequisite DAG with unlock gating and topological introduction order
  * Session planning (remediate -> due reviews -> promotions -> new material)
  * Persistent local learner profile (JSON) + append-only session log (JSONL)

Stdlib only. Python 3.9+. All state lives in --dir (default ./tutor-data),
which is created self-gitignoring so learner data never enters version control.

Run `python3 tutor_engine.py --help` or see references/algorithms.md for the
math, and references/data-model.md for the file formats.
"""

import argparse
import json
import math
import os
import shutil
import sys
import tempfile
from datetime import date, timedelta

ENGINE_VERSION = "1.0.0"
PROFILE_NAME = "profile.json"
LOG_NAME = "sessions.jsonl"

DEPTH_NAMES = {1: "Recall", 2: "Explain", 3: "Apply", 4: "Connect", 5: "Extend"}
MAX_DEPTH = 5

# ---------------------------------------------------------------------------
# BKT — Bayesian Knowledge Tracing (Corbett & Anderson, 1995)
# ---------------------------------------------------------------------------
# Question-format-specific guess/slip parameters. A correct answer on a
# 4-option MCQ is weaker evidence of mastery (guess=0.25) than a correct
# free-form teach-back (guess=0.05). Slip rises with task complexity.
FORMAT_PARAMS = {
    "mcq4":      {"guess": 0.25, "slip": 0.10},
    "mcq3":      {"guess": 0.33, "slip": 0.10},
    "tf":        {"guess": 0.50, "slip": 0.08},
    "cloze":     {"guess": 0.15, "slip": 0.10},
    "open":      {"guess": 0.08, "slip": 0.12},
    "teachback": {"guess": 0.05, "slip": 0.15},
    "applied":   {"guess": 0.05, "slip": 0.20},
    "transfer":  {"guess": 0.03, "slip": 0.25},
}
DEFAULT_FORMAT = "open"
P_LEARN = 0.15          # P(T): chance an opportunity transitions un-known -> known
P_INIT = 0.20           # P(L0): prior mastery for a never-seen concept/depth

# Promotion gate: advance a depth rung only with strong, spaced evidence.
PROMOTE_P = 0.85
PROMOTE_MIN_CORRECT = 3
PROMOTE_MIN_DAYS = 2
REMEDIATE_P = 0.35
REMEDIATE_MIN_ATTEMPTS = 3
UNLOCK_PREREQ_P = 0.60  # prereq mastery (at its current depth) needed to unlock


def bkt_update(p, correct, guess, slip, p_learn=P_LEARN):
    """One BKT step: Bayes posterior on the observation, then learning transition."""
    p = min(max(p, 0.001), 0.999)
    if correct:
        num = p * (1.0 - slip)
        den = num + (1.0 - p) * guess
    else:
        num = p * slip
        den = num + (1.0 - p) * (1.0 - guess)
    posterior = num / den if den > 1e-12 else p
    p_new = posterior + (1.0 - posterior) * p_learn
    return min(max(p_new, 0.001), 0.999)


# ---------------------------------------------------------------------------
# FSRS-lite scheduler
# ---------------------------------------------------------------------------
# Simplified from the open FSRS algorithm (three-component DSR model:
# Difficulty, Stability, Retrievability). Constants chosen so that at the
# default 90% retention target, interval == stability — the FSRS-4.5 curve.
# This is intentionally a compact approximation; see references/algorithms.md.
F_FACTOR = 19.0 / 81.0
F_DECAY = -0.5
INIT_STABILITY = {"again": 0.5, "hard": 1.5, "good": 3.0, "easy": 7.0}
INIT_DIFFICULTY = {"again": 7.5, "hard": 6.5, "good": 5.0, "easy": 3.5}
RATING_NUM = {"again": 1, "hard": 2, "good": 3, "easy": 4}
SUCCESS_MULT = {"hard": 0.55, "good": 1.0, "easy": 1.5}
W_SINC_SCALE = 1.5      # exp(this) scales stability growth on success
W_SINC_SPOW = -0.08     # stability saturation exponent
W_SINC_RGAIN = 1.0      # lower retrievability at review -> bigger gain (spacing effect)
W_FAIL_SCALE = 1.7
W_FAIL_DPOW = -0.3
W_FAIL_SPOW = 0.4
W_FAIL_RGAIN = 1.0
MIN_STABILITY = 0.25
MAX_INTERVAL = 365


def retrievability(elapsed_days, stability):
    """P(recall) after elapsed_days given stability (power forgetting curve)."""
    if stability is None or stability <= 0:
        return None
    t = max(0.0, float(elapsed_days))
    return (1.0 + F_FACTOR * t / stability) ** F_DECAY


def interval_for(stability, target_retention):
    """Days until retrievability decays to the target retention."""
    raw = (stability / F_FACTOR) * (target_retention ** (1.0 / F_DECAY) - 1.0)
    return int(min(MAX_INTERVAL, max(1, round(raw))))


def fsrs_review(sched, rating, elapsed_days):
    """Update stability/difficulty in place. Returns retrievability at review time."""
    s, d = sched.get("stability"), sched.get("difficulty")
    if s is None:  # first ever review of this concept
        sched["stability"] = INIT_STABILITY[rating]
        sched["difficulty"] = INIT_DIFFICULTY[rating]
        sched["reps"] = 1
        if rating == "again":
            sched["lapses"] = sched.get("lapses", 0) + 1
        return None

    r = retrievability(elapsed_days, s)
    g = RATING_NUM[rating]
    same_day = elapsed_days < 0.5

    if rating == "again":
        if same_day:
            s_new = max(MIN_STABILITY, s * 0.5)
        else:
            s_new = (W_FAIL_SCALE * (d ** W_FAIL_DPOW)
                     * (((s + 1.0) ** W_FAIL_SPOW) - 1.0)
                     * math.exp(W_FAIL_RGAIN * (1.0 - r)))
            s_new = max(MIN_STABILITY, min(s, s_new))
        sched["lapses"] = sched.get("lapses", 0) + 1
    else:
        if same_day:
            s_new = s * {"hard": 1.05, "good": 1.15, "easy": 1.3}[rating]
        else:
            sinc = 1.0 + (math.exp(W_SINC_SCALE) * (11.0 - d)
                          * (s ** W_SINC_SPOW)
                          * (math.exp(W_SINC_RGAIN * (1.0 - r)) - 1.0)
                          * SUCCESS_MULT[rating])
            s_new = s * max(1.01, sinc)

    d_new = d - 0.6 * (g - 3)
    d_new = 0.95 * d_new + 0.05 * 5.0           # mean reversion
    sched["stability"] = round(s_new, 4)
    sched["difficulty"] = round(min(10.0, max(1.0, d_new)), 4)
    sched["reps"] = sched.get("reps", 0) + 1
    return r


# ---------------------------------------------------------------------------
# SM-2 (SuperMemo-2) — classic alternative, selectable via settings
# ---------------------------------------------------------------------------
SM2_QUALITY = {"again": 1, "hard": 3, "good": 4, "easy": 5}


def sm2_review(sched, rating):
    """Classic SM-2. Returns the new interval in days."""
    sm2 = sched.setdefault("sm2", {"interval": 0, "ef": 2.5, "reps": 0})
    q = SM2_QUALITY[rating]
    if q < 3:
        sm2["reps"] = 0
        sm2["interval"] = 1
        sched["lapses"] = sched.get("lapses", 0) + 1
    else:
        sm2["reps"] += 1
        if sm2["reps"] == 1:
            sm2["interval"] = 1
        elif sm2["reps"] == 2:
            sm2["interval"] = 6
        else:
            sm2["interval"] = int(round(sm2["interval"] * sm2["ef"]))
        sm2["ef"] = max(1.3, sm2["ef"] + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
    sched["reps"] = sched.get("reps", 0) + 1
    sm2["interval"] = min(MAX_INTERVAL, max(1, sm2["interval"]))
    return sm2["interval"]


# ---------------------------------------------------------------------------
# Profile store
# ---------------------------------------------------------------------------
class Store:
    def __init__(self, dirpath, today):
        self.dir = os.path.abspath(dirpath)
        self.today = today
        self.path = os.path.join(self.dir, PROFILE_NAME)
        self.log_path = os.path.join(self.dir, LOG_NAME)
        self.profile = None

    # -- persistence ---------------------------------------------------------
    def ensure_dir(self):
        os.makedirs(self.dir, exist_ok=True)
        gi = os.path.join(self.dir, ".gitignore")
        if not os.path.exists(gi):
            with open(gi, "w") as f:
                f.write("# Learner data stays local. This directory ignores itself.\n*\n")

    def load(self, required=True):
        if not os.path.exists(self.path):
            if required:
                die("No learner profile at %s — run `init` first (or copy an "
                    "existing profile.json into that directory)." % self.path)
            return None
        with open(self.path) as f:
            self.profile = json.load(f)
        return self.profile

    def save(self):
        self.ensure_dir()
        if os.path.exists(self.path):
            shutil.copy2(self.path, self.path + ".bak")
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=".profile-", suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(self.profile, f, indent=2, sort_keys=False)
            f.write("\n")
        os.replace(tmp, self.path)

    def log(self, event):
        self.ensure_dir()
        event = dict(event)
        event.setdefault("date", self.today.isoformat())
        with open(self.log_path, "a") as f:
            f.write(json.dumps(event) + "\n")

    # -- domain helpers ------------------------------------------------------
    def concept(self, cid):
        c = self.profile["concepts"].get(cid)
        if c is None:
            die("Unknown concept id '%s'. Known ids: %s"
                % (cid, ", ".join(sorted(self.profile["concepts"]))))
        return c

    def depth_state(self, concept, depth):
        ds = concept.setdefault("depths", {})
        key = str(depth)
        if key not in ds:
            prev = ds.get(str(depth - 1))
            # Knowing a concept at one rung only partially transfers upward.
            p0 = max(P_INIT, prev["p"] - 0.30) if prev else P_INIT
            ds[key] = {"p": round(p0, 4), "attempts": 0, "correct": 0,
                       "days_correct": []}
        return ds[key]

    def unlocked(self, concept):
        for pid in concept.get("prereqs", []):
            pre = self.profile["concepts"].get(pid)
            if pre is None:
                return False
            st = pre.get("depths", {}).get(str(pre.get("depth", 1)))
            if st is None or st["p"] < UNLOCK_PREREQ_P:
                return False
        return True

    def promotion_eligible(self, concept):
        d = concept.get("depth", 1)
        if d >= MAX_DEPTH:
            return False
        st = concept.get("depths", {}).get(str(d))
        if st is None:
            return False
        active_misc = any(m["status"] == "active"
                          for m in concept.get("misconceptions", []))
        return (st["p"] >= PROMOTE_P and st["correct"] >= PROMOTE_MIN_CORRECT
                and len(st["days_correct"]) >= PROMOTE_MIN_DAYS
                and not active_misc)

    def mastered(self, concept):
        target = concept.get("target_depth",
                             self.profile["learner"]["settings"]["target_depth"])
        d = concept.get("depth", 1)
        st = concept.get("depths", {}).get(str(d))
        if st is None:
            return False
        solid = (st["p"] >= PROMOTE_P and st["correct"] >= PROMOTE_MIN_CORRECT
                 and len(st["days_correct"]) >= PROMOTE_MIN_DAYS)
        return d >= target and solid

    def p_effective(self, concept):
        """P(can produce it right now) = P(learned) x retrievability.

        Extension beyond plain BKT/FSRS: combines knowledge tracing with the
        memory model (cf. HLR, DAS3H) so review order targets true risk.
        """
        d = concept.get("depth", 1)
        st = concept.get("depths", {}).get(str(d))
        p = st["p"] if st else P_INIT
        sched = concept.get("sched", {})
        if sched.get("stability") and sched.get("last_review"):
            elapsed = (self.today - date.fromisoformat(sched["last_review"])).days
            r = retrievability(elapsed, sched["stability"])
        else:
            r = 1.0
        return p * (r if r is not None else 1.0), p, r


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_init(store, args):
    store.ensure_dir()
    if os.path.exists(store.path) and not args.force:
        die("Profile already exists at %s (use --force to overwrite)." % store.path)
    store.profile = {
        "version": 1,
        "engine": ENGINE_VERSION,
        "created": store.today.isoformat(),
        "topic": args.topic,
        "learner": {
            "name": args.learner,
            "goals": args.goals or "",
            "background": args.background or "",
            "settings": {
                "scheduler": "fsrs",          # or "sm2"
                "target_retention": 0.90,
                "target_depth": max(1, min(MAX_DEPTH, args.target_depth)),
                "max_items": 10,
                "new_per_session": 2,
            },
        },
        "concepts": {},
    }
    store.save()
    store.log({"event": "init", "topic": args.topic, "learner": args.learner})
    out({"ok": True, "profile": store.path,
         "note": "Directory is self-gitignoring; learner data stays local."})


def cmd_settings(store, args):
    store.load()
    s = store.profile["learner"]["settings"]
    changed = {}
    for key in ("scheduler", "target_retention", "target_depth",
                "max_items", "new_per_session"):
        val = getattr(args, key, None)
        if val is not None:
            if key == "scheduler" and val not in ("fsrs", "sm2"):
                die("scheduler must be 'fsrs' or 'sm2'")
            if key == "target_retention" and not (0.7 <= val <= 0.97):
                die("target_retention must be between 0.70 and 0.97")
            s[key] = val
            changed[key] = val
    store.save()
    out({"ok": True, "settings": s, "changed": changed})


def cmd_template(_store, _args):
    out({
        "concepts": [
            {"id": "bayes-theorem", "name": "Bayes' theorem",
             "summary": "Posterior = likelihood x prior / evidence.",
             "prereqs": ["conditional-probability"], "target_depth": 4},
            {"id": "conditional-probability", "name": "Conditional probability",
             "summary": "P(A|B) and how conditioning reshapes the sample space.",
             "prereqs": []},
        ],
        "note": ("Feed a file shaped like this to `add-concepts --file ...`. "
                 "ids: lowercase-kebab, unique. prereqs may reference ids "
                 "defined in the same file. target_depth is optional "
                 "(defaults to the learner's setting).")
    })


def _toposort(concepts):
    order, temp, perm = [], set(), set()

    def visit(cid):
        if cid in perm:
            return
        if cid in temp:
            die("Prerequisite cycle detected involving '%s'." % cid)
        temp.add(cid)
        for pid in concepts[cid].get("prereqs", []):
            if pid in concepts:
                visit(pid)
        temp.discard(cid)
        perm.add(cid)
        order.append(cid)

    for cid in concepts:
        visit(cid)
    return order


def cmd_add_concepts(store, args):
    store.load()
    if args.file == "-":
        data = json.load(sys.stdin)
    else:
        with open(args.file) as f:
            data = json.load(f)
    items = data["concepts"] if isinstance(data, dict) else data
    existing = store.profile["concepts"]
    batch_ids = {c["id"] for c in items}
    added, skipped = [], []
    for c in items:
        cid = c["id"]
        if cid in existing:
            skipped.append(cid)
            continue
        for pid in c.get("prereqs", []):
            if pid not in existing and pid not in batch_ids:
                die("Concept '%s' lists unknown prerequisite '%s'." % (cid, pid))
        entry = {
            "name": c.get("name", cid),
            "summary": c.get("summary", ""),
            "prereqs": list(c.get("prereqs", [])),
            "depth": 1,
            "introduced": None,
            "sched": {"stability": None, "difficulty": None, "last_review": None,
                      "due": None, "reps": 0, "lapses": 0},
            "depths": {},
            "calibration": {"n": 0, "brier_sum": 0.0, "overconfident_errors": 0},
            "misconceptions": [],
        }
        if "target_depth" in c:
            entry["target_depth"] = max(1, min(MAX_DEPTH, int(c["target_depth"])))
        existing[cid] = entry
        added.append(cid)
    _toposort(existing)  # validates: raises on cycles
    store.save()
    store.log({"event": "add_concepts", "added": added, "skipped": skipped})
    out({"ok": True, "added": added, "skipped_existing": skipped,
         "total_concepts": len(existing)})


FORMAT_SUGGESTION = {
    1: "mcq4 / cloze / open one-liner",
    2: "teachback / open 'explain why'",
    3: "applied problem",
    4: "transfer task in a novel context / discrimination question",
    5: "open critique, design, or limits-of-the-model question",
}


def cmd_plan(store, args):
    store.load()
    settings = store.profile["learner"]["settings"]
    max_items = args.max_items or settings["max_items"]
    new_quota = settings["new_per_session"]
    concepts = store.profile["concepts"]

    remediate, reviews, promotes, news = [], [], [], []
    mastered_ids, locked = [], []

    for cid in _toposort(concepts):
        c = concepts[cid]
        d = c.get("depth", 1)
        st = c.get("depths", {}).get(str(d))
        active_misc = [m["text"] for m in c.get("misconceptions", [])
                       if m["status"] == "active"]
        if c["introduced"] is None:
            if store.unlocked(c):
                news.append(cid)
            else:
                locked.append(cid)
            continue
        if store.mastered(c):
            mastered_ids.append(cid)
            # mastered concepts still surface when overdue — maintenance only
        p_eff, p, r = store.p_effective(c)
        if active_misc:
            remediate.append((cid, d, "active misconception(s): "
                              + "; ".join(active_misc[:2]), p_eff))
        elif st and st["attempts"] >= REMEDIATE_MIN_ATTEMPTS and st["p"] < REMEDIATE_P:
            back = max(1, d - 1)
            remediate.append((cid, back,
                              "struggling at %s (P=%.2f) — step back to %s"
                              % (DEPTH_NAMES[d], st["p"], DEPTH_NAMES[back]), p_eff))
        elif store.promotion_eligible(c):
            promotes.append((cid, d + 1,
                             "solid at %s (P=%.2f, %dx correct over %d days) — "
                             "probe %s" % (DEPTH_NAMES[d], st["p"], st["correct"],
                                           len(st["days_correct"]),
                                           DEPTH_NAMES[d + 1]), p_eff))
        else:
            due = c["sched"].get("due")
            if due and date.fromisoformat(due) <= store.today and not store.mastered(c):
                reviews.append((cid, d, "due %s, P(now)=%.2f" % (due, p_eff), p_eff))

    reviews.sort(key=lambda t: t[3])  # most at-risk first

    items = []

    def push(pool, mode, limit=None):
        for cid, depth, reason, _ in pool[:limit]:
            if len(items) >= max_items:
                return
            items.append({
                "order": len(items) + 1, "concept_id": cid,
                "name": concepts[cid]["name"], "depth": depth,
                "depth_name": DEPTH_NAMES[depth], "mode": mode,
                "format_suggestion": FORMAT_SUGGESTION[depth], "reason": reason,
            })

    push(remediate, "remediate")
    # reserve room for new material so learners always progress
    reserve = min(new_quota, len(news)) if len(items) < max_items else 0
    room = max(0, max_items - len(items) - reserve)
    push(reviews[:room], "review")
    push(promotes, "promote")
    for cid in news[:new_quota]:
        if len(items) >= max_items:
            break
        c = concepts[cid]
        items.append({
            "order": len(items) + 1, "concept_id": cid, "name": c["name"],
            "depth": 1, "depth_name": DEPTH_NAMES[1], "mode": "new",
            "format_suggestion": "teach first (worked example + self-explanation), "
                                 "then a Recall check",
            "reason": "unlocked — prerequisites are solid"
            if c.get("prereqs") else "unlocked — no prerequisites",
        })

    # light interleave: avoid same prereq-family back to back where possible
    def family(it):
        pr = concepts[it["concept_id"]].get("prereqs", [])
        return pr[0] if pr else it["concept_id"]

    for i in range(1, len(items)):
        if family(items[i]) == family(items[i - 1]):
            for j in range(i + 1, len(items)):
                if family(items[j]) != family(items[i - 1]):
                    items[i], items[j] = items[j], items[i]
                    break
    for n, it in enumerate(items, 1):
        it["order"] = n

    coach = []
    if remediate:
        coach.append("Misconceptions/struggles first: use refutation feedback "
                     "(state the wrong idea, why it fails, the correct model).")
    if reviews:
        coach.append("Reviews are ordered by risk (P(learned) x retrievability). "
                     "Vary surface features from last time — same concept, new clothes.")
    if promotes:
        coach.append("Promotion probes test the NEXT depth. Expect more errors; "
                     "that's desirable difficulty, not failure.")
    if news:
        coach.append("New concepts: teach before testing. Worked example, then a "
                     "self-explanation prompt, then the check.")
    if not items:
        nxt = _next_due(store)
        coach.append("Nothing due and nothing new. Next review due %s — spacing "
                     "works by waiting; let it." % (nxt or "n/a"))

    store.log({"event": "plan", "n_items": len(items)})
    out({"generated": store.today.isoformat(),
         "learner": store.profile["learner"]["name"],
         "topic": store.profile["topic"],
         "stats": {"due_reviews": len(reviews), "remediation": len(remediate),
                   "promotion_ready": len(promotes), "new_available": len(news),
                   "locked": len(locked), "mastered": len(mastered_ids)},
         "items": items, "coach_notes": coach})


def _next_due(store):
    dues = [c["sched"]["due"] for c in store.profile["concepts"].values()
            if c["sched"].get("due")]
    return min(dues) if dues else None


def _derive_rating(correct, confidence, hinted):
    if not correct:
        return "again"
    if hinted:
        return "hard"
    if confidence is not None and confidence >= 0.9:
        return "easy"
    return "good"


def cmd_record(store, args):
    store.load()
    c = store.concept(args.concept)
    settings = store.profile["learner"]["settings"]
    depth = args.depth or c.get("depth", 1)
    if not 1 <= depth <= MAX_DEPTH:
        die("depth must be 1..%d" % MAX_DEPTH)
    fmt = args.format or DEFAULT_FORMAT
    if fmt not in FORMAT_PARAMS:
        die("format must be one of: %s" % ", ".join(FORMAT_PARAMS))
    correct = args.correct in ("1", "yes", "true", "y")
    confidence = None
    if args.confidence is not None:
        confidence = max(0.0, min(1.0, args.confidence / 100.0))
    rating = args.rating or _derive_rating(correct, confidence, args.hinted)
    if rating not in RATING_NUM:
        die("rating must be one of: again, hard, good, easy")
    if correct and rating == "again":
        die("rating 'again' implies an incorrect answer; use hard/good/easy.")
    if not correct:
        rating = "again"

    # ---- BKT (per depth) ----
    params = FORMAT_PARAMS[fmt]
    guess = args.guess if args.guess is not None else params["guess"]
    slip = args.slip if args.slip is not None else params["slip"]
    st = store.depth_state(c, depth)
    p_before = st["p"]
    st["p"] = round(bkt_update(p_before, correct, guess, slip), 4)
    st["attempts"] += 1
    if correct:
        st["correct"] += 1
        today_iso = store.today.isoformat()
        if today_iso not in st["days_correct"]:
            st["days_correct"].append(today_iso)

    # depth pointer moves with demonstrated work at a higher rung
    promoted = False
    if depth > c.get("depth", 1):
        c["depth"] = depth
        promoted = True

    # ---- calibration ----
    brier = None
    hypercorrect = False
    if confidence is not None:
        brier = round((confidence - (1.0 if correct else 0.0)) ** 2, 4)
        cal = c["calibration"]
        cal["n"] += 1
        cal["brier_sum"] = round(cal["brier_sum"] + brier, 4)
        if not correct and confidence >= 0.75:
            cal["overconfident_errors"] += 1
            hypercorrect = True

    # ---- misconception ledger ----
    if args.misconception:
        c["misconceptions"].append({"text": args.misconception, "status": "active",
                                    "noted": store.today.isoformat(),
                                    "resolved": None})

    # ---- scheduling ----
    sched = c["sched"]
    s_before = sched.get("stability")
    last = sched.get("last_review")
    elapsed = (store.today - date.fromisoformat(last)).days if last else 0
    if settings["scheduler"] == "sm2":
        interval = sm2_review(sched, rating)
        # keep an FSRS-comparable stability figure for p_effective ordering
        sched["stability"] = float(max(MIN_STABILITY, interval))
        sched["difficulty"] = sched.get("difficulty") or 5.0
    else:
        fsrs_review(sched, rating, elapsed)
        interval = interval_for(sched["stability"], settings["target_retention"])
    sched["last_review"] = store.today.isoformat()
    sched["due"] = (store.today + timedelta(days=interval)).isoformat()

    if c["introduced"] is None:
        c["introduced"] = store.today.isoformat()

    eligible_next = store.promotion_eligible(c)
    is_mastered = store.mastered(c)

    store.save()
    store.log({"event": "record", "concept": args.concept, "depth": depth,
               "mode": args.mode, "format": fmt, "correct": correct,
               "confidence": confidence, "rating": rating, "brier": brier,
               "p_before": p_before, "p_after": st["p"],
               "stability_before": s_before, "stability_after": sched["stability"],
               "due": sched["due"], "misconception": args.misconception,
               "note": args.note})

    cal = c["calibration"]
    out({"ok": True, "concept": args.concept, "depth": depth,
         "depth_name": DEPTH_NAMES[depth],
         "bkt": {"p_before": p_before, "p_after": st["p"],
                 "attempts_at_depth": st["attempts"],
                 "correct_at_depth": st["correct"],
                 "distinct_days_correct": len(st["days_correct"])},
         "schedule": {"rating": rating, "stability_days": sched["stability"],
                      "difficulty": sched.get("difficulty"),
                      "interval_days": interval, "due": sched["due"],
                      "scheduler": settings["scheduler"]},
         "calibration": {"this_brier": brier,
                         "mean_brier": round(cal["brier_sum"] / cal["n"], 4)
                         if cal["n"] else None,
                         "hypercorrection_moment": hypercorrect},
         "flags": {"promoted_to_new_depth": promoted,
                   "promotion_eligible": eligible_next,
                   "mastered": is_mastered,
                   "active_misconceptions": [m["text"] for m in c["misconceptions"]
                                             if m["status"] == "active"]},
         "guidance": _record_guidance(correct, hypercorrect, eligible_next,
                                      is_mastered, promoted, depth)})


def _record_guidance(correct, hypercorrect, eligible, mastered, promoted, depth):
    g = []
    if hypercorrect:
        g.append("High-confidence error — hypercorrection window. Give vivid, "
                 "memorable corrective feedback and have the learner restate "
                 "the correct idea in their own words before moving on.")
    if not correct:
        g.append("Use the hint ladder on a retry variant later this session "
                 "rather than re-asking the identical question now.")
    if promoted:
        g.append("Learner just moved up to %s — expect wobble; scaffold the "
                 "first item at this rung." % DEPTH_NAMES[depth])
    if eligible:
        g.append("Eligible for promotion: next session, probe one depth higher.")
    if mastered:
        g.append("Target depth reached and solid. Shift to maintenance reviews; "
                 "celebrate specifically what they can now do.")
    return g


def cmd_resolve(store, args):
    store.load()
    c = store.concept(args.concept)
    active = [m for m in c["misconceptions"] if m["status"] == "active"]
    if not active:
        die("No active misconceptions on '%s'." % args.concept)
    idx = args.index
    if idx is None:
        if len(active) > 1:
            die("Multiple active misconceptions; pass --index:\n" + "\n".join(
                "  [%d] %s" % (i, m["text"]) for i, m in enumerate(active)))
        idx = 0
    if not 0 <= idx < len(active):
        die("--index out of range (0..%d)" % (len(active) - 1))
    active[idx]["status"] = "resolved"
    active[idx]["resolved"] = store.today.isoformat()
    store.save()
    store.log({"event": "resolve_misconception", "concept": args.concept,
               "text": active[idx]["text"]})
    out({"ok": True, "resolved": active[idx]["text"],
         "note": "Schedule a spaced re-check: misconceptions regress; verify "
                 "the fix sticks in a later session."})


def cmd_dashboard(store, args):
    store.load()
    concepts = store.profile["concepts"]
    settings = store.profile["learner"]["settings"]
    rows = []
    n_mastered = n_due = 0
    total_brier_sum = total_brier_n = 0
    for cid in _toposort(concepts):
        c = concepts[cid]
        d = c.get("depth", 1)
        st = c.get("depths", {}).get(str(d))
        p_eff, p, r = store.p_effective(c)
        due = c["sched"].get("due")
        is_due = bool(due and date.fromisoformat(due) <= store.today)
        if c["introduced"] is None:
            status = "ready" if store.unlocked(c) else "locked"
        elif store.mastered(c):
            status = "mastered"
            n_mastered += 1
        elif any(m["status"] == "active" for m in c.get("misconceptions", [])):
            status = "misconception!"
        elif is_due:
            status = "DUE"
        else:
            status = "learning"
        if is_due and c["introduced"]:
            n_due += 1
        cal = c["calibration"]
        total_brier_sum += cal["brier_sum"]
        total_brier_n += cal["n"]
        ever_reviewed = c["sched"].get("stability") is not None
        rows.append((cid, c["name"][:30], status, DEPTH_NAMES[d],
                     "%.0f%%" % (100 * p) if st else "—",
                     ("%.0f%%" % (100 * r)) if (r is not None and ever_reviewed)
                     else "—",
                     due or "—",
                     "%.2f" % (cal["brier_sum"] / cal["n"]) if cal["n"] else "—",
                     str(sum(1 for m in c.get("misconceptions", [])
                             if m["status"] == "active"))))
    if args.json:
        out({"today": store.today.isoformat(), "topic": store.profile["topic"],
             "learner": store.profile["learner"]["name"],
             "summary": {"concepts": len(rows), "mastered": n_mastered,
                         "due": n_due,
                         "mean_brier": round(total_brier_sum / total_brier_n, 3)
                         if total_brier_n else None,
                         "next_due": _next_due(store)},
             "rows": [dict(zip(("id", "name", "status", "depth", "p_learned",
                                "retrievability", "due", "brier",
                                "active_misconceptions"), rw)) for rw in rows]})
        return
    hdr = ("id", "name", "status", "depth", "P(L)", "R(now)", "due", "brier", "misc")
    widths = [max(len(str(x)) for x in [h] + [rw[i] for rw in rows])
              for i, h in enumerate(hdr)]
    line = "  ".join(h.ljust(w) for h, w in zip(hdr, widths))
    print(line)
    print("-" * len(line))
    for rw in rows:
        print("  ".join(str(x).ljust(w) for x, w in zip(rw, widths)))
    mb = ("%.3f" % (total_brier_sum / total_brier_n)) if total_brier_n else "n/a"
    print("\n%s | %d concepts, %d mastered, %d due today | mean Brier %s "
          "(0=perfectly calibrated, 0.25=guessing) | next due: %s"
          % (store.profile["topic"], len(rows), n_mastered, n_due, mb,
             _next_due(store) or "n/a"))
    print("Scheduler: %s @ %.0f%% retention | target depth: %s"
          % (settings["scheduler"], settings["target_retention"] * 100,
             DEPTH_NAMES[settings["target_depth"]]))


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
def cmd_selftest(_store, _args):
    import subprocess
    tmp = tempfile.mkdtemp(prefix="tutor-selftest-")
    me = os.path.abspath(__file__)
    fails = []

    def run(argv, expect_fail=False):
        r = subprocess.run([sys.executable, me, "--dir", tmp] + argv,
                           capture_output=True, text=True)
        if (r.returncode != 0) != expect_fail:
            fails.append("cmd %s rc=%d stderr=%s" % (argv, r.returncode,
                                                     r.stderr.strip()[:200]))
        return r.stdout

    def check(label, cond):
        print(("PASS  " if cond else "FAIL  ") + label)
        if not cond:
            fails.append(label)

    run(["--today", "2026-01-01", "init", "--learner", "T", "--topic", "Test"])
    cmap = {"concepts": [
        {"id": "a", "name": "A", "prereqs": []},
        {"id": "b", "name": "B", "prereqs": ["a"]}]}
    cpath = os.path.join(tmp, "c.json")
    with open(cpath, "w") as f:
        json.dump(cmap, f)
    run(["add-concepts", "--file", cpath])
    bad = os.path.join(tmp, "bad.json")
    with open(bad, "w") as f:
        json.dump({"concepts": [{"id": "x", "prereqs": ["y"]},
                                {"id": "y", "prereqs": ["x"]}]}, f)
    run(["add-concepts", "--file", bad], expect_fail=True)
    check("cycle detection rejects circular prereqs", True)

    plan = json.loads(run(["--today", "2026-01-01", "plan"]))
    check("plan introduces only unlocked concept 'a' first",
          [i["concept_id"] for i in plan["items"] if i["mode"] == "new"] == ["a"])

    r1 = json.loads(run(["--today", "2026-01-01", "record", "--concept", "a",
                         "--correct", "1", "--format", "open",
                         "--confidence", "60"]))
    check("BKT rises on correct", r1["bkt"]["p_after"] > r1["bkt"]["p_before"])
    r2 = json.loads(run(["--today", "2026-01-02", "record", "--concept", "a",
                         "--correct", "1", "--format", "open",
                         "--confidence", "80"]))
    r3 = json.loads(run(["--today", "2026-01-04", "record", "--concept", "a",
                         "--correct", "1", "--format", "teachback",
                         "--confidence", "85"]))
    check("promotion needs P>=0.85, 3 correct, 2+ days",
          r3["flags"]["promotion_eligible"])
    check("stability grows across spaced successes",
          r3["schedule"]["stability_days"] > r1["schedule"]["stability_days"])

    plan2 = json.loads(run(["--today", "2026-01-05", "plan"]))
    modes = {i["concept_id"]: i["mode"] for i in plan2["items"]}
    check("plan proposes promotion for 'a' and unlocks 'b'",
          modes.get("a") == "promote" and modes.get("b") == "new")

    r4 = json.loads(run(["--today", "2026-01-05", "record", "--concept", "a",
                         "--depth", "2", "--correct", "0", "--format",
                         "teachback", "--confidence", "90",
                         "--misconception", "thinks A is symmetric"]))
    check("wrong answer drops BKT", r4["bkt"]["p_after"] < 0.5)
    check("high-confidence error flags hypercorrection",
          r4["calibration"]["hypercorrection_moment"])
    check("depth pointer advanced to Explain",
          r4["flags"]["promoted_to_new_depth"] and r4["depth"] == 2)
    check("lapse shrinks stability",
          r4["schedule"]["stability_days"] < r3["schedule"]["stability_days"])

    plan3 = json.loads(run(["--today", "2026-01-06", "plan"]))
    check("active misconception routes to remediate",
          any(i["concept_id"] == "a" and i["mode"] == "remediate"
              for i in plan3["items"]))
    run(["resolve-misconception", "--concept", "a"])
    dash = json.loads(run(["--today", "2026-01-06", "dashboard", "--json"]))
    check("dashboard JSON renders with both concepts",
          len(dash["rows"]) == 2)

    run(["settings", "--scheduler", "sm2"])
    r5 = json.loads(run(["--today", "2026-01-08", "record", "--concept", "b",
                         "--correct", "1", "--format", "mcq4",
                         "--confidence", "50"]))
    check("sm2 scheduler produces a valid due date",
          r5["schedule"]["scheduler"] == "sm2" and r5["schedule"]["due"]
          > "2026-01-08")
    check("self-gitignore written",
          os.path.exists(os.path.join(tmp, ".gitignore")))
    check("backup created on save",
          os.path.exists(os.path.join(tmp, "profile.json.bak")))

    # pure-math invariants
    p = 0.2
    for _ in range(10):
        p = bkt_update(p, True, 0.25, 0.1)
    check("BKT converges upward under repeated success", p > 0.95)
    check("retrievability(0)=1", abs(retrievability(0, 3.0) - 1.0) < 1e-9)
    check("interval==stability at 90% retention",
          interval_for(10.0, 0.9) == 10)

    shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d failure(s)." % len(fails))
    sys.exit(1 if fails else 0)


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------
def out(obj):
    print(json.dumps(obj, indent=2))


def die(msg):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(1)


def build_parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dir", default=os.environ.get("TUTOR_DATA_DIR", "./tutor-data"),
                   help="learner data directory (default ./tutor-data)")
    p.add_argument("--today", default=None,
                   help="override today's date (YYYY-MM-DD) — for testing")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="create a learner profile")
    sp.add_argument("--learner", required=True)
    sp.add_argument("--topic", required=True)
    sp.add_argument("--goals", default="")
    sp.add_argument("--background", default="")
    sp.add_argument("--target-depth", type=int, default=4,
                    help="1=Recall 2=Explain 3=Apply 4=Connect 5=Extend (default 4)")
    sp.add_argument("--force", action="store_true")

    sp = sub.add_parser("settings", help="view/change settings")
    sp.add_argument("--scheduler", choices=["fsrs", "sm2"])
    sp.add_argument("--target-retention", dest="target_retention", type=float)
    sp.add_argument("--target-depth", dest="target_depth", type=int)
    sp.add_argument("--max-items", dest="max_items", type=int)
    sp.add_argument("--new-per-session", dest="new_per_session", type=int)

    sub.add_parser("template", help="print an example concepts.json")

    sp = sub.add_parser("add-concepts", help="add concepts from a JSON file")
    sp.add_argument("--file", required=True, help="path or '-' for stdin")

    sp = sub.add_parser("plan", help="compute today's session plan (JSON)")
    sp.add_argument("--max-items", type=int, default=None)

    sp = sub.add_parser("record", help="record one answer; updates BKT + schedule")
    sp.add_argument("--concept", required=True)
    sp.add_argument("--depth", type=int, default=None,
                    help="depth probed (default: concept's current depth)")
    sp.add_argument("--format", default=None,
                    help="|".join(FORMAT_PARAMS))
    sp.add_argument("--correct", required=True, choices=["0", "1", "yes", "no",
                                                         "y", "n", "true", "false"])
    sp.add_argument("--confidence", type=float, default=None,
                    help="learner's pre-reveal confidence, 0-100")
    sp.add_argument("--rating", choices=list(RATING_NUM), default=None,
                    help="again|hard|good|easy (default: derived)")
    sp.add_argument("--hinted", action="store_true",
                    help="correct only after hints (derives rating 'hard')")
    sp.add_argument("--mode", default="review",
                    choices=["new", "review", "promote", "remediate", "diagnostic"])
    sp.add_argument("--misconception", default=None,
                    help="log a revealed misconception (verbatim, short)")
    sp.add_argument("--note", default=None)
    sp.add_argument("--guess", type=float, default=None, help="override BKT guess")
    sp.add_argument("--slip", type=float, default=None, help="override BKT slip")

    sp = sub.add_parser("resolve-misconception", help="mark a misconception resolved")
    sp.add_argument("--concept", required=True)
    sp.add_argument("--index", type=int, default=None,
                    help="index among ACTIVE misconceptions (default: only one)")

    sp = sub.add_parser("dashboard", help="mastery overview")
    sp.add_argument("--json", action="store_true")

    sub.add_parser("selftest", help="run built-in invariant tests")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    today = date.fromisoformat(args.today) if args.today else date.today()
    store = Store(args.dir, today)
    {
        "init": cmd_init, "settings": cmd_settings, "template": cmd_template,
        "add-concepts": cmd_add_concepts, "plan": cmd_plan, "record": cmd_record,
        "resolve-misconception": cmd_resolve, "dashboard": cmd_dashboard,
        "selftest": cmd_selftest,
    }[args.cmd](store, args)


if __name__ == "__main__":
    main()
