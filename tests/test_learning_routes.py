"""Route tests for missions, quiz gating, skills, warm-up, practice and capstones.
NOTE: written without being able to run Flask in the build sandbox. Run `pytest tests/test_learning_routes.py` first."""
import json
from datetime import datetime, timedelta
from conftest import make_user


def _login(client, user):
    with client.session_transaction() as s:
        s['_user_id'] = str(user.id)
        s['_fresh'] = True


def _lesson(app_module, track='html', order=1):
    return app_module.Lesson.query.filter_by(track=track, order=order).first()


def test_lessons_get_missions_with_skill_and_worked_example(app, db):
    import app as app_module
    lesson = _lesson(app_module)
    p = json.loads(lesson.practice_json)
    assert len(p['steps']) >= 2 and p['skill'] == 'html-structure' and p['worked']
    assert all(s['skill'] for s in p['steps'])


def test_quiz_blocked_until_mission_done(client, db):
    import app as app_module
    user = make_user(db, app_module)
    _login(client, user)
    lesson = _lesson(app_module)
    quiz = json.loads(lesson.quiz_json)
    answers = [q['answer'] for q in quiz]
    r = client.post('/api/lesson/complete', json={'lesson_id': lesson.id, 'answers': answers})
    assert r.status_code == 403 and r.get_json()['needs_mission']
    client.post('/api/mission/complete', json={'lesson_id': lesson.id, 'attempts': 4, 'hints': 0, 'assisted': 0})
    r = client.post('/api/lesson/complete', json={'lesson_id': lesson.id, 'answers': answers})
    assert r.status_code == 200 and r.get_json()['passed']


def test_step_events_feed_skills_page(client, db):
    import app as app_module
    user = make_user(db, app_module, username='skiller', email='s@example.com')
    _login(client, user)
    for _ in range(2):
        client.post('/api/mission/step', json={'lesson_id': None, 'step': 0, 'skill': 'loops-arrays', 'checks': 6, 'hints': 2, 'assisted': 0, 'stuck': False})
    r = client.get('/my-skills')
    assert r.status_code == 200 and b'Practise next' in r.data and b'Loops' in r.data


def test_unknown_skill_is_ignored_and_practice_404s(client, db):
    import app as app_module
    user = make_user(db, app_module, username='p1', email='p1@example.com')
    _login(client, user)
    client.post('/api/mission/step', json={'skill': '<script>', 'checks': 1})
    ev = app_module.AnalyticsEvent.query.filter_by(user_id=user.id, event_type='mission_step').first()
    assert json.loads(ev.meta)['skill'] == ''
    assert client.get('/practice/not-a-skill').status_code == 404
    assert client.get('/practice/loops-arrays').status_code == 200


def test_capstone_locked_until_track_complete(client, db):
    import app as app_module
    user = make_user(db, app_module, username='cap', email='cap@example.com')
    _login(client, user)
    assert b'Capstone locked' in client.get('/capstone/html').data
    for l in app_module.Lesson.query.filter_by(track='html').all():
        db.session.add(app_module.LessonProgress(user_id=user.id, lesson_id=l.id, completed=True, completed_at=datetime.utcnow()))
    db.session.commit()
    assert b'Capstone locked' not in client.get('/capstone/html').data


def test_warmup_empty_then_due(client, db):
    import app as app_module
    user = make_user(db, app_module, username='wu', email='wu@example.com')
    _login(client, user)
    assert b'Nothing is due' in client.get('/warmup').data
    lesson = _lesson(app_module)
    db.session.add(app_module.LessonProgress(user_id=user.id, lesson_id=lesson.id, completed=True,
                                             completed_at=datetime.utcnow() - timedelta(days=3)))
    db.session.commit()
    assert b'Warm-up: ' in client.get('/warmup').data


def test_teacher_sees_stuck_steps_only_for_own_students(client, db):
    import app as app_module
    teacher = make_user(db, app_module, username='teach', email='t@example.com', role='teacher')
    room = app_module.Classroom(name='C', teacher_id=teacher.id, join_code='ZZZ999')
    db.session.add(room); db.session.commit()
    lesson = _lesson(app_module)
    for i in range(4):
        u = make_user(db, app_module, username='kid%d' % i, email='k%d@example.com' % i, classroom_id=room.id)
        client.post('/api/mission/step')  # unauthenticated, ignored
        db.session.add(app_module.AnalyticsEvent(event_type='mission_step', user_id=u.id, meta=json.dumps(
            {'lesson_id': lesson.id, 'step': 0, 'skill': 'html-structure', 'checks': 6, 'hints': 1, 'assisted': 0, 'stuck': False, 'done': True})))
    db.session.commit()
    _login(client, teacher)
    r = client.get('/teacher')
    assert r.status_code == 200 and b'4 of 4 struggled' in r.data


def test_start_pages_are_public(client):
    r = client.get('/start')
    assert r.status_code == 200 and b'Program a robot' in r.data
    r = client.get('/start/code')
    assert r.status_code == 200 and b'Your first real code' in r.data
