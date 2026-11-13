"""
Shared pytest fixtures.

app.py is a single-file Flask app (not an app-factory), and it creates and
seeds its database as a side effect of being imported. To keep tests from
touching your real database.db, this file points the app at a temporary
SQLite file BEFORE importing app.py, so the import-time `db.create_all()` /
`seed_database()` runs against the temp file instead.

Run with:  pip install -r requirements.txt -r requirements-dev.txt
           pytest
"""
import os
import sys
import tempfile
import pytest

# Must happen before `import app` — these become the values app.py reads
# via os.getenv() while building its Flask config.
_tmp_dir = tempfile.mkdtemp()
_tmp_db_path = os.path.join(_tmp_dir, 'test.db')
os.environ['DATABASE_URL'] = f'sqlite:///{_tmp_db_path}'
os.environ['SECRET_KEY'] = 'test-secret-key-not-for-production'
os.environ.setdefault('FLASK_ENV', 'testing')  # anything but 'production'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as app_module  # noqa: E402  (import after env vars are set, on purpose)

app_module.app.config['TESTING'] = True
app_module.app.config['WTF_CSRF_ENABLED'] = False


@pytest.fixture()
def app():
    """The Flask app, with a fresh app context per test function."""
    with app_module.app.app_context():
        yield app_module.app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    return app_module.db


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """The signup/login/AI rate limiters live in plain module-level dicts
    (see the NOTE in app.py's RATE LIMITING section) so they persist across
    tests in the same process. Without this reset, a handful of signup
    tests in a row would start silently tripping the real 5-per-hour signup
    limit and fail for a reason that has nothing to do with what they're
    actually testing."""
    app_module._action_hits.clear()
    app_module._failed_logins.clear()
    yield
    app_module._action_hits.clear()
    app_module._failed_logins.clear()


def make_user(db, app_module, **overrides):
    """Create and persist a bare User row for tests that need one directly,
    bypassing the /signup route and its validation."""
    from werkzeug.security import generate_password_hash
    defaults = dict(
        username=overrides.pop('username', 'testuser'),
        email=overrides.pop('email', 'testuser@example.com'),
        password_hash=generate_password_hash(overrides.pop('password', 'password123')),
    )
    defaults.update(overrides)
    user = app_module.User(**defaults)
    db.session.add(user)
    db.session.commit()
    return user
