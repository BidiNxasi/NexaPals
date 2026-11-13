"""
Route-level tests using Flask's test client — no browser needed.
"""


def _signup_payload(**overrides):
    payload = {
        'username': 'newkid',
        'email': 'newkid@example.com',
        'password': 'password123',
        'terms_accepted': 'on',
    }
    payload.update(overrides)
    return payload


def test_signup_rejects_missing_terms_acceptance(client, db):
    import app as app_module
    payload = _signup_payload()
    del payload['terms_accepted']  # simulates the checkbox being left unchecked
    resp = client.post('/signup', data=payload, follow_redirects=True)
    assert resp.status_code == 200
    assert app_module.User.query.filter_by(username='newkid').first() is None


def test_signup_rejects_minor_without_parent_email(client, db):
    import app as app_module
    payload = _signup_payload(username='minorkid', email='minorkid@example.com', is_minor='on')
    # no parent_email supplied
    resp = client.post('/signup', data=payload, follow_redirects=True)
    assert resp.status_code == 200
    assert app_module.User.query.filter_by(username='minorkid').first() is None


def test_signup_accepts_minor_with_valid_parent_email(client, db):
    import app as app_module
    payload = _signup_payload(
        username='minorkid2', email='minorkid2@example.com',
        is_minor='on', parent_email='parent@example.com',
    )
    resp = client.post('/signup', data=payload, follow_redirects=True)
    assert resp.status_code == 200
    user = app_module.User.query.filter_by(username='minorkid2').first()
    assert user is not None
    assert user.is_minor is True
    assert user.parent_email == 'parent@example.com'
    assert user.parent_verified is False  # pending until the parent clicks the emailed link
    assert user.parent_verify_token is not None
    assert user.terms_accepted_at is not None


def test_signup_adult_account_is_parent_verified_by_default(client, db):
    import app as app_module
    payload = _signup_payload(username='adultuser', email='adultuser@example.com')
    resp = client.post('/signup', data=payload, follow_redirects=True)
    assert resp.status_code == 200
    user = app_module.User.query.filter_by(username='adultuser').first()
    assert user is not None
    assert user.is_minor is False
    assert user.parent_verified is True
    assert user.parent_verify_token is None


def test_signup_rejects_duplicate_username(client, db):
    payload = _signup_payload(username='dupeuser', email='dupe1@example.com')
    client.post('/signup', data=payload, follow_redirects=True)
    payload2 = _signup_payload(username='dupeuser', email='dupe2@example.com')
    resp = client.post('/signup', data=payload2, follow_redirects=True)
    import app as app_module
    matches = app_module.User.query.filter_by(username='dupeuser').all()
    assert len(matches) == 1  # the second attempt must not create a second row


def test_verify_parent_marks_account_verified(client, db):
    import app as app_module
    payload = _signup_payload(
        username='minorkid3', email='minorkid3@example.com',
        is_minor='on', parent_email='parent3@example.com',
    )
    client.post('/signup', data=payload, follow_redirects=True)
    user = app_module.User.query.filter_by(username='minorkid3').first()
    token = user.parent_verify_token
    assert token

    resp = client.get(f'/verify-parent/{token}', follow_redirects=True)
    assert resp.status_code == 200
    app_module.db.session.refresh(user)
    assert user.parent_verified is True
    assert user.parent_verify_token is None
    assert user.parent_manage_token  # a standing manage link is issued on verification


def test_verify_parent_rejects_unknown_token(client, db):
    resp = client.get('/verify-parent/not-a-real-token', follow_redirects=True)
    assert resp.status_code == 200  # redirects home with a flash, doesn't 500


def test_login_wrong_password_fails(client, db):
    from conftest import make_user
    import app as app_module
    make_user(db, app_module, username='logintest', email='logintest@example.com', password='correcthorse')
    resp = client.post('/login', data={'username': 'logintest', 'password': 'wrongpassword'},
                        follow_redirects=True)
    assert resp.status_code == 200
    assert b'Invalid credentials' in resp.data


def test_login_does_not_award_streak_credit(client, db):
    """Regression test for the Ship Streak change: logging in must NOT by
    itself advance streak_days — only shipping something (a lesson or a
    saved project) should."""
    from conftest import make_user
    import app as app_module
    u = make_user(db, app_module, username='shiptest', email='shiptest@example.com', password='password123')
    u.streak_days = 0
    u.last_active = None
    app_module.db.session.commit()

    resp = client.post('/login', data={'username': 'shiptest', 'password': 'password123'},
                        follow_redirects=True)
    assert resp.status_code == 200
    app_module.db.session.refresh(u)
    assert u.streak_days == 0  # unchanged by login alone


def test_404_returns_custom_page(client):
    resp = client.get('/this-route-does-not-exist')
    assert resp.status_code == 404


def test_healthz(client):
    resp = client.get('/healthz')
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'ok'


def test_privacy_and_terms_pages_load(client):
    for path in ('/privacy', '/terms'):
        resp = client.get(path)
        assert resp.status_code == 200
