"""
Tests for the opt-in weekly parent digest: the preferences page (login-free,
token-based), the digest-content builder, and the "skip if nothing happened"
rule that keeps parents from getting an empty email every week.
"""
from datetime import datetime, timedelta

from conftest import make_user


def test_parent_manage_page_loads_with_valid_token(client, db):
    import app as app_module
    u = make_user(db, app_module, username='pd1', email='pd1@example.com',
                  is_minor=True, parent_email='parent1@example.com',
                  parent_verified=True, parent_manage_token='tok-pd1')
    resp = client.get('/parent/manage/tok-pd1')
    assert resp.status_code == 200
    assert b'pd1' in resp.data


def test_parent_manage_rejects_unknown_token(client, db):
    resp = client.get('/parent/manage/not-a-real-token', follow_redirects=True)
    assert resp.status_code == 200  # redirects home with a flash, no 500


def test_parent_manage_toggle_opt_in(client, db):
    import app as app_module
    u = make_user(db, app_module, username='pd2', email='pd2@example.com',
                  is_minor=True, parent_email='parent2@example.com',
                  parent_verified=True, parent_manage_token='tok-pd2')
    assert u.parent_digest_opt_in is False  # off by default

    resp = client.post('/parent/manage/tok-pd2', data={'digest_opt_in': '1'}, follow_redirects=True)
    assert resp.status_code == 200
    app_module.db.session.refresh(u)
    assert u.parent_digest_opt_in is True

    # Unchecking the box (no field sent at all) turns it back off.
    client.post('/parent/manage/tok-pd2', data={}, follow_redirects=True)
    app_module.db.session.refresh(u)
    assert u.parent_digest_opt_in is False


def test_digest_builder_returns_none_for_a_quiet_week(app, db):
    import app as app_module
    u = make_user(db, app_module, username='pd3', email='pd3@example.com')
    u.weekly_xp = 0
    db.session.commit()
    digest = app_module._build_parent_digest(u)
    assert digest is None  # no activity -> no email, not an empty one


def test_digest_builder_summarises_a_real_week(app, db):
    import app as app_module
    u = make_user(db, app_module, username='pd4', email='pd4@example.com')
    u.weekly_xp = 40
    u.streak_days = 3
    u.parent_manage_token = 'tok-pd4'
    db.session.commit()

    lesson = app_module.Lesson.query.first()
    progress = app_module.LessonProgress(
        user_id=u.id, lesson_id=lesson.id, completed=True, score=100,
        completed_at=datetime.utcnow(),
    )
    db.session.add(progress)
    db.session.commit()

    digest = app_module._build_parent_digest(u)
    assert digest is not None
    assert digest['username'] == 'pd4'
    assert digest['lessons_completed'] == 1
    assert digest['xp_earned'] == 40
    assert digest['streak_days'] == 3


def test_digest_builder_ignores_lessons_completed_before_this_week(app, db):
    import app as app_module
    u = make_user(db, app_module, username='pd5', email='pd5@example.com')
    u.weekly_xp = 0
    db.session.commit()

    lesson = app_module.Lesson.query.first()
    old_progress = app_module.LessonProgress(
        user_id=u.id, lesson_id=lesson.id, completed=True, score=100,
        completed_at=datetime.utcnow() - timedelta(days=30),
    )
    db.session.add(old_progress)
    db.session.commit()

    digest = app_module._build_parent_digest(u)
    assert digest is None  # old activity + zero weekly XP -> nothing to report
