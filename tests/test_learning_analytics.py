import sys, os, random
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import learning_analytics as la

NOW = datetime(2026, 11, 8)

def ev(skill, checks=1, hints=0, assisted=0, stuck=False, uid=1, lesson=1, step=0, minutes=0, typ='mission_step'):
    return {"event_type": typ, "user_id": uid, "created_at": NOW + timedelta(minutes=minutes),
            "meta": {"skill": skill, "checks": checks, "hints": hints, "assisted": assisted, "stuck": stuck, "lesson_id": lesson, "step": step}}

def test_step_score():
    assert la.step_score(1, 0, 0) == 1.0
    assert la.step_score(3, 1, 0) == 0.5
    assert la.step_score(1, 0, 1) == 0.2          # solution reveal caps
    assert la.step_score(20, 5, 0) == 0.2         # floor

def test_strength_recency_and_weak():
    events = [ev('loops', 5, 2, minutes=0), ev('loops', 4, 1, minutes=1), ev('forms', 1, minutes=2), ev('forms', 1, minutes=3)]
    s = la.skill_strengths(events)
    assert s['forms']['strength'] == 1.0
    assert s['loops']['strength'] < la.WEAK
    assert la.weakest_skills(s) == ['loops']
    # improving later results raise strength
    better = events + [ev('loops', 1, minutes=10), ev('loops', 1, minutes=11), ev('loops', 1, minutes=12)]
    assert la.skill_strengths(better)['loops']['strength'] > s['loops']['strength']

def test_weak_needs_two_steps():
    assert la.weakest_skills(la.skill_strengths([ev('x', 6, 3)])) == []

def test_stubborn_needs_enough_learners():
    few = [ev('s', checks=6, uid=u, lesson=2, step=1) for u in range(4)]
    assert la.stubborn_steps(few) == []
    many = [ev('s', checks=6, uid=u, lesson=2, step=1) for u in range(3)] + [ev('s', checks=1, uid=u, lesson=2, step=1) for u in range(3, 8)]
    # 3 of 8 learners struggled = 37.5%, below the 40% bar, so nothing is flagged
    assert la.stubborn_steps(many) == []
    more = many + [ev('s', checks=1, assisted=1, uid=20, lesson=2, step=1)]
    assert la.stubborn_steps(more)[0]['struggled'] == 4

def test_stuck_event_counts():
    evs = [ev('s', typ='mission_stuck', uid=u, lesson=3, step=0) for u in range(3)] + [ev('s', uid=u, lesson=3, step=0) for u in range(3, 6)]
    assert la.stubborn_steps(evs)[0]['share'] == 0.5

def test_warmup_due_window_and_recent_review():
    done = [{"track": "html", "order": 1, "completed_at": NOW - timedelta(days=1)},
            {"track": "html", "order": 2, "completed_at": NOW - timedelta(days=3)},
            {"track": "css", "order": 1, "completed_at": NOW - timedelta(days=60)}]
    assert la.pick_warmup(done, {}, NOW, random.Random(1)) == ("html", 2)
    assert la.pick_warmup(done, {("html", 2): NOW - timedelta(hours=5)}, NOW) is None
    assert la.pick_warmup([], {}, NOW) is None

def test_capstone_unlock():
    assert la.capstone_unlocked('html', [1, 2, 3, 4], [1, 2, 3, 4])
    assert not la.capstone_unlocked('html', [1, 2, 3], [1, 2, 3, 4])
    assert not la.capstone_unlocked('html', [], [])

def test_mastery_levels_match_js_rule():
    assert la.mastery_level(0, 6, 3) == 'mastered'
    assert la.mastery_level(0, 7, 3) == 'solid'
    assert la.mastery_level(1, 3, 3) == 'practising'

def test_learner_summary():
    steps = [ev('loops', 5, 2, minutes=0), ev('loops', 5, 2, minutes=1)]
    mis = [{"meta": {"lesson_id": 1, "assisted": 0, "attempts": 4, "steps": 3}}, {"meta": {"lesson_id": 2, "assisted": 1, "attempts": 4, "steps": 3}}]
    s = la.learner_summary(steps, mis)
    assert s['weakest'] == 'loops' and s['mastery'] == {'mastered': 1, 'solid': 0, 'practising': 1}
