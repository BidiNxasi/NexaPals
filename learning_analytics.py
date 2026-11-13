"""Pure-Python learning analytics (no Flask / SQLAlchemy imports so it is easy to test).

Input is always plain dicts, e.g. an event row as
    {"event_type": "mission_step", "user_id": 3, "meta": {...}, "created_at": datetime}
"""
from collections import defaultdict
from datetime import datetime, timedelta
import random

STRONG = 0.75
WEAK = 0.6


def mastery_level(assisted, attempts, steps):
    """Mirror of masteryOf() in static/js/mission.js."""
    if assisted > 0:
        return "practising"
    return "mastered" if attempts <= steps * 2 else "solid"


def step_score(checks, hints, assisted):
    """1.0 = first try, no hints. Each extra check costs 0.2, each hint 0.1. A revealed solution caps it at 0.2."""
    score = 1.0 - 0.2 * max(0, checks - 1) - 0.1 * hints
    if assisted:
        score = min(score, 0.2)
    return max(0.2, round(score, 3))


def skill_strengths(step_events, alpha=0.5):
    """Recency-weighted strength per skill. Returns {skill: {"strength", "steps", "stuck"}}."""
    by = defaultdict(list)
    for ev in sorted(step_events, key=lambda e: e.get("created_at") or datetime.min):
        m = ev.get("meta") or {}
        skill = m.get("skill")
        if not skill:
            continue
        by[skill].append(m)
    out = {}
    for skill, items in by.items():
        strength = None
        stuck = 0
        for m in items:
            if m.get("stuck") and not m.get("done", True):
                stuck += 1
                continue
            sc = step_score(int(m.get("checks", 1) or 1), int(m.get("hints", 0) or 0), int(m.get("assisted", 0) or 0))
            strength = sc if strength is None else alpha * sc + (1 - alpha) * strength
        if strength is None:
            continue
        out[skill] = {"strength": round(strength, 3), "steps": len(items), "stuck": stuck}
    return out


def weakest_skills(strengths, limit=3, min_steps=2):
    weak = [(k, v) for k, v in strengths.items() if v["steps"] >= min_steps and v["strength"] < WEAK]
    weak.sort(key=lambda kv: kv[1]["strength"])
    return [k for k, _ in weak[:limit]]


def skill_band(strength):
    return "strong" if strength >= STRONG else ("ok" if strength >= WEAK else "weak")


def stubborn_steps(events, min_learners=5, share=0.4):
    """Steps where at least `share` of learners needed 4+ checks, got stuck, or used Show me.
    Needs `min_learners` distinct learners before it flags anything."""
    seen = defaultdict(set)
    struggled = defaultdict(set)
    skill_of = {}
    for ev in events:
        m = ev.get("meta") or {}
        if ev.get("event_type") not in ("mission_step", "mission_stuck"):
            continue
        key = (m.get("lesson_id"), m.get("step"))
        uid = ev.get("user_id")
        if uid is None or key[0] is None or key[1] is None:
            continue
        seen[key].add(uid)
        skill_of[key] = m.get("skill")
        if ev["event_type"] == "mission_stuck" or int(m.get("checks", 0) or 0) >= 4 or int(m.get("assisted", 0) or 0) > 0:
            struggled[key].add(uid)
    flagged = []
    for key, users in seen.items():
        if len(users) < min_learners:
            continue
        frac = len(struggled[key]) / len(users)
        if frac >= share:
            flagged.append({"lesson_id": key[0], "step": key[1], "skill": skill_of[key], "learners": len(users),
                            "struggled": len(struggled[key]), "share": round(frac, 2)})
    flagged.sort(key=lambda f: -f["share"])
    return flagged


def pick_warmup(completed, last_review, now=None, rng=None, min_days=2, max_days=45):
    """completed: [{"track","order","completed_at"}]; last_review: {(track, order): datetime}.
    Returns (track, order) of a lesson due for a quick review, or None."""
    now = now or datetime.utcnow()
    rng = rng or random
    due = []
    for c in completed:
        at = c.get("completed_at")
        if not at:
            continue
        age = now - at
        if not (timedelta(days=min_days) <= age <= timedelta(days=max_days)):
            continue
        rev = last_review.get((c["track"], c["order"]))
        if rev and now - rev < timedelta(days=min_days):
            continue
        due.append((rev or at, c["track"], c["order"]))
    if not due:
        return None
    due.sort()
    oldest = [d for d in due if d[0] == due[0][0]]
    _, track, order = rng.choice(oldest)
    return track, order


def capstone_unlocked(track, completed_orders, lesson_orders):
    """Unlocked when every lesson of the track is complete."""
    need = set(lesson_orders)
    return bool(need) and need.issubset(set(completed_orders))


def learner_summary(step_events, mission_events):
    """For the teacher view: weakest skill and mastery counts for one learner."""
    st = skill_strengths(step_events)
    weak = weakest_skills(st, limit=1, min_steps=1)
    counts = {"mastered": 0, "solid": 0, "practising": 0}
    best = {}
    for ev in mission_events:
        m = ev.get("meta") or {}
        if m.get("lesson_id") is None:
            continue
        best[m["lesson_id"]] = mastery_level(int(m.get("assisted", 0) or 0), int(m.get("attempts", 0) or 0), int(m.get("steps", 3) or 3))
    for lvl in best.values():
        counts[lvl] += 1
    return {"weakest": weak[0] if weak else None, "mastery": counts}
