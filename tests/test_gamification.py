"""
Tests for the gamification logic on the User model: levels, the Ship
Streak, weekly leagues, and badge awarding.

These exercise real bugs that were found by hand while building the
feature (see the level() test below) — the point of this suite is to
catch the next one automatically instead of by manual code review.
"""
from datetime import date, timedelta

from conftest import make_user


def test_level_thresholds(app, db):
    import app as app_module
    u = make_user(db, app_module, username='lvl1', email='lvl1@example.com')

    u.xp = 0
    assert u.level['name'] == 'Rookie'
    assert u.level['num'] == 1

    u.xp = 49
    assert u.level['name'] == 'Rookie'

    u.xp = 50
    assert u.level['name'] == 'Explorer'
    assert u.level['num'] == 2

    u.xp = 2500
    assert u.level['name'] == 'Guru'

    # Regression test: the top level (Master) must be reachable. An earlier
    # version of this loop only checked len(thresholds)-2 down to 0, which
    # meant the highest threshold (9999) was only ever used as "next_xp" for
    # Guru and never became a level of its own — a student could earn 9999 XP
    # and never see "Master" anywhere.
    u.xp = 9999
    assert u.level['name'] == 'Master'
    assert u.level['next_xp'] is None

    u.xp = 50000  # well past the top threshold — should stay at Master, not error
    assert u.level['name'] == 'Master'


def test_level_progress_pct_at_max_level(app, db):
    import app as app_module
    u = make_user(db, app_module, username='lvl2', email='lvl2@example.com')
    u.xp = 9999
    assert u.level_progress_pct == 100


def test_streak_increments_on_consecutive_days(app, db):
    import app as app_module
    u = make_user(db, app_module, username='streak1', email='streak1@example.com')
    u.streak_days = 0
    u.last_active = date.today() - timedelta(days=1)
    u.update_streak()
    assert u.streak_days == 1
    assert u.last_active == date.today()


def test_streak_resets_after_a_gap(app, db):
    import app as app_module
    u = make_user(db, app_module, username='streak2', email='streak2@example.com')
    u.streak_days = 12
    u.last_active = date.today() - timedelta(days=3)  # missed 2 days
    u.update_streak()
    assert u.streak_days == 1  # reset, not incremented


def test_streak_is_a_noop_if_already_updated_today(app, db):
    import app as app_module
    u = make_user(db, app_module, username='streak3', email='streak3@example.com')
    u.streak_days = 7
    u.last_active = date.today()
    u.update_streak()
    assert u.streak_days == 7  # unchanged — calling this twice in one day must not double-count


def test_streak_freeze_saves_a_single_missed_day(app, db):
    """Kinder-design rule: missing exactly one day spends a banked freeze and
    keeps the streak alive, instead of resetting it to 1."""
    import app as app_module
    u = make_user(db, app_module, username='streak4', email='streak4@example.com')
    u.streak_days = 5
    u.streak_freezes = 1
    u.last_active = date.today() - timedelta(days=2)  # missed exactly one day
    u.update_streak()
    assert u.streak_days == 6       # kept going, not reset
    assert u.streak_freezes == 0    # freeze was spent


def test_streak_resets_when_no_freeze_available(app, db):
    import app as app_module
    u = make_user(db, app_module, username='streak5', email='streak5@example.com')
    u.streak_days = 5
    u.streak_freezes = 0
    u.last_active = date.today() - timedelta(days=2)  # missed exactly one day, no freeze banked
    u.update_streak()
    assert u.streak_days == 1  # no freeze left, so it resets like before


def test_streak_freeze_earned_every_seven_days_capped(app, db):
    import app as app_module
    u = make_user(db, app_module, username='streak6', email='streak6@example.com')
    u.streak_days = 6
    u.streak_freezes = 1
    u.last_active = date.today() - timedelta(days=1)
    u.update_streak()
    assert u.streak_days == 7
    assert u.streak_freezes == 2  # earned one back at the 7-day mark

    u.streak_freezes = app_module.User.STREAK_FREEZE_CAP  # already at the cap
    u.streak_days = 13
    u.last_active = date.today() - timedelta(days=1)
    u.update_streak()
    assert u.streak_days == 14
    assert u.streak_freezes == app_module.User.STREAK_FREEZE_CAP  # unchanged — capped, no overflow


def test_add_xp_within_the_same_week_just_accumulates(app, db):
    import app as app_module
    u = make_user(db, app_module, username='xp1', email='xp1@example.com')
    this_monday = date.today() - timedelta(days=date.today().weekday())
    u.week_start = this_monday
    u.xp = 10
    u.weekly_xp = 10
    u.league = 'bronze'
    u.add_xp(15)
    assert u.xp == 25
    assert u.weekly_xp == 25
    assert u.league == 'bronze'  # no week boundary crossed, no promotion check triggered


def test_league_promotion_on_new_week_with_enough_weekly_xp(app, db):
    import app as app_module
    u = make_user(db, app_module, username='xp2', email='xp2@example.com')
    u.league = 'bronze'
    u.weekly_xp = 150  # over the 100 XP promotion threshold
    u.week_start = date.today() - timedelta(days=14)  # a past week
    u.add_xp(10)
    assert u.league == 'silver'  # promoted
    assert u.weekly_xp == 10     # reset to 0, then this call's XP added
    assert u.xp == 10


def test_league_no_demotion_on_fully_inactive_week(app, db):
    """Kinder-design rule: leagues never go down. Missing a whole week just
    means the league stays exactly where it was — no drop for illness, exams,
    a holiday, or any other reason a kid might go quiet for a week."""
    import app as app_module
    u = make_user(db, app_module, username='xp3', email='xp3@example.com')
    u.league = 'gold'
    u.weekly_xp = 0  # earned nothing last week
    u.week_start = date.today() - timedelta(days=14)
    u.add_xp(5)
    assert u.league == 'gold'  # unchanged, not demoted


def test_league_escalating_promotion_thresholds(app, db):
    """Each league needs more weekly XP to climb out of than the last —
    100 from bronze, 150 from silver, 200 from gold."""
    import app as app_module
    u = make_user(db, app_module, username='xp6', email='xp6@example.com')
    u.league = 'silver'
    u.weekly_xp = 120  # enough to leave bronze, NOT enough to leave silver
    u.week_start = date.today() - timedelta(days=14)
    u.add_xp(5)
    assert u.league == 'silver'  # not promoted — needed 150

    u2 = make_user(db, app_module, username='xp7', email='xp7@example.com')
    u2.league = 'silver'
    u2.weekly_xp = 150
    u2.week_start = date.today() - timedelta(days=14)
    u2.add_xp(5)
    assert u2.league == 'gold'  # promoted — met the (higher) silver threshold


def test_league_cannot_promote_past_diamond(app, db):
    import app as app_module
    u = make_user(db, app_module, username='xp4', email='xp4@example.com')
    u.league = 'diamond'
    u.weekly_xp = 500
    u.week_start = date.today() - timedelta(days=14)
    u.add_xp(5)
    assert u.league == 'diamond'  # already at the top, no error, no overflow


def test_league_cannot_demote_below_bronze(app, db):
    import app as app_module
    u = make_user(db, app_module, username='xp5', email='xp5@example.com')
    u.league = 'bronze'
    u.weekly_xp = 0
    u.week_start = date.today() - timedelta(days=14)
    u.add_xp(5)
    assert u.league == 'bronze'  # already at the bottom, no error, no negative index


def test_award_badges_first_lesson(app, db):
    import app as app_module
    u = make_user(db, app_module, username='badge1', email='badge1@example.com')
    db.session.commit()

    lesson = app_module.Lesson.query.first()
    assert lesson is not None, 'seed_database() should have created at least one lesson'

    progress = app_module.LessonProgress(user_id=u.id, lesson_id=lesson.id, completed=True, score=100)
    db.session.add(progress)
    db.session.commit()

    earned = app_module._award_badges(u)
    slugs = {b.slug for b in earned}
    assert 'first-lesson' in slugs


def test_award_badges_does_not_double_award(app, db):
    import app as app_module
    u = make_user(db, app_module, username='badge2', email='badge2@example.com')
    lesson = app_module.Lesson.query.first()
    progress = app_module.LessonProgress(user_id=u.id, lesson_id=lesson.id, completed=True, score=100)
    db.session.add(progress)
    db.session.commit()

    first_call = app_module._award_badges(u)
    second_call = app_module._award_badges(u)
    assert len(first_call) >= 1
    assert len(second_call) == 0  # already has it — must not be handed out twice
