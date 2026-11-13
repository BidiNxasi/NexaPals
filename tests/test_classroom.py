"""
Tests for the teacher/classroom distribution feature.
"""


def _login(client, username, password='password123'):
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=True)


def test_create_classroom_generates_unique_join_code(client, db):
    from conftest import make_user
    import app as app_module
    teacher = make_user(db, app_module, username='teacher1', email='teacher1@example.com', role='student')
    _login(client, 'teacher1')

    resp = client.post('/teacher/create-classroom', data={'name': 'Room 4B'}, follow_redirects=True)
    assert resp.status_code == 200

    app_module.db.session.refresh(teacher)
    assert teacher.role == 'teacher'  # auto-upgraded from student
    classroom = app_module.Classroom.query.filter_by(teacher_id=teacher.id).first()
    assert classroom is not None
    assert classroom.name == 'Room 4B'
    assert len(classroom.join_code) == 6


def test_teacher_cannot_create_a_second_classroom(client, db):
    from conftest import make_user
    import app as app_module
    make_user(db, app_module, username='teacher2', email='teacher2@example.com')
    _login(client, 'teacher2')
    client.post('/teacher/create-classroom', data={'name': 'First'}, follow_redirects=True)
    client.post('/teacher/create-classroom', data={'name': 'Second'}, follow_redirects=True)

    count = app_module.Classroom.query.filter_by(
        teacher_id=app_module.User.query.filter_by(username='teacher2').first().id
    ).count()
    assert count == 1  # the second attempt must not create a duplicate


def test_student_can_join_classroom_with_valid_code(client, db):
    from conftest import make_user
    import app as app_module
    teacher = make_user(db, app_module, username='teacher3', email='teacher3@example.com')
    classroom = app_module.Classroom(name='Test Room', teacher_id=teacher.id, join_code='ABC123')
    db.session.add(classroom)
    db.session.commit()

    make_user(db, app_module, username='student1', email='student1@example.com')
    _login(client, 'student1')
    resp = client.post('/join-classroom', data={'join_code': 'abc123'}, follow_redirects=True)  # lowercase on purpose
    assert resp.status_code == 200

    student = app_module.User.query.filter_by(username='student1').first()
    assert student.classroom_id == classroom.id  # case-insensitive match worked


def test_student_join_with_invalid_code_does_not_crash(client, db):
    from conftest import make_user
    import app as app_module
    make_user(db, app_module, username='student2', email='student2@example.com')
    _login(client, 'student2')
    resp = client.post('/join-classroom', data={'join_code': 'NOTREAL'}, follow_redirects=True)
    assert resp.status_code == 200
    student = app_module.User.query.filter_by(username='student2').first()
    assert student.classroom_id is None


def test_teacher_dashboard_lists_joined_students(client, db):
    from conftest import make_user
    import app as app_module
    teacher = make_user(db, app_module, username='teacher4', email='teacher4@example.com')
    classroom = app_module.Classroom(name='Room X', teacher_id=teacher.id, join_code='XYZ999')
    db.session.add(classroom)
    db.session.commit()

    student = make_user(db, app_module, username='student3', email='student3@example.com')
    student.classroom_id = classroom.id
    db.session.commit()

    _login(client, 'teacher4')
    resp = client.get('/teacher')
    assert resp.status_code == 200
    assert b'student3' in resp.data


def test_remove_student_only_works_for_the_owning_teacher(client, db):
    from conftest import make_user
    import app as app_module
    teacher_a = make_user(db, app_module, username='teacherA', email='teacherA@example.com')
    teacher_b = make_user(db, app_module, username='teacherB', email='teacherB@example.com')
    classroom_a = app_module.Classroom(name='A room', teacher_id=teacher_a.id, join_code='AAA111')
    db.session.add(classroom_a)
    db.session.commit()

    student = make_user(db, app_module, username='student4', email='student4@example.com')
    student.classroom_id = classroom_a.id
    db.session.commit()

    # teacher B (who does NOT own this classroom) tries to remove the student
    _login(client, 'teacherB')
    client.post(f'/teacher/remove-student/{student.id}', follow_redirects=True)
    app_module.db.session.refresh(student)
    assert student.classroom_id == classroom_a.id  # unchanged — teacher B has no classroom of their own

    # the real owner can remove them
    _login(client, 'teacherA')
    client.post(f'/teacher/remove-student/{student.id}', follow_redirects=True)
    app_module.db.session.refresh(student)
    assert student.classroom_id is None
