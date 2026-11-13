import os
import json
import smtplib
import bleach
import requests as http_requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_talisman import Talisman
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from collections import defaultdict
import time as _time
import secrets

load_dotenv()

app = Flask(__name__)
IS_PROD = os.getenv('FLASK_ENV') == 'production'
_secret_key = os.getenv('SECRET_KEY')
if not _secret_key:
    if IS_PROD:
        raise RuntimeError('SECRET_KEY must be set in production — refusing to boot with the default key.')
    _secret_key = 'fallback-key-for-testing'  # dev-only fallback, never used in production
app.config['SECRET_KEY'] = _secret_key
# DATABASE_URL lets you point at Postgres/MySQL in production without touching
# code — e.g. postgresql://user:pass@host/dbname. Defaults to local SQLite for
# dev. NOTE: SQLite plus more than one gunicorn worker is a real risk of
# "database is locked" errors under concurrent writes — use a real database
# (or --workers 1) before you have real traffic.
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL') or 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ── Security: session cookies ──────────────────────────────────────────────
app.config['SESSION_COOKIE_SECURE']   = IS_PROD
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours

# ── Security: HTTPS + headers via Talisman ────────────────────────────────
csp = {
    'default-src': ["'self'"],
    'script-src':  ["'self'", "'unsafe-inline'", 'cdnjs.cloudflare.com'],
    'style-src':   ["'self'", "'unsafe-inline'", 'fonts.googleapis.com', 'cdnjs.cloudflare.com'],
    'font-src':    ["'self'", 'fonts.gstatic.com', 'cdnjs.cloudflare.com'],
    'img-src':     ["'self'", 'data:'],
    'frame-src':   ["'self'"],
}
Talisman(
    app,
    force_https=IS_PROD,
    strict_transport_security=IS_PROD,
    content_security_policy=csp,
    frame_options='SAMEORIGIN',
    referrer_policy='strict-origin-when-cross-origin',
)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
csrf = CSRFProtect(app)

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)

# ── Input sanitisation helper ──────────────────────────────────────────────
ALLOWED_TAGS: list = []  # strip ALL html from user text inputs

def sanitize(text: str, max_len: int = 500) -> str:
    """Strip HTML tags and limit length on any user-supplied text."""
    return bleach.clean(str(text or ''), tags=ALLOWED_TAGS, strip=True)[:max_len]

# ==================== DATABASE MODELS ====================

class User(UserMixin, db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role          = db.Column(db.String(20),  default='student')
    xp            = db.Column(db.Integer,     default=0)
    avatar        = db.Column(db.String(20),  default='fa-egg')  # Font Awesome icon class, not an emoji
    streak_days   = db.Column(db.Integer,     default=0)
    last_active   = db.Column(db.Date,        default=date.today)
    created_at    = db.Column(db.DateTime,    default=datetime.utcnow)
    # Weekly league (Bronze/Silver/Gold/Diamond) — separate from all-time XP so
    # a student who joins later can still compete for something this week.
    weekly_xp     = db.Column(db.Integer,     default=0)
    league        = db.Column(db.String(20),  default='bronze')
    week_start    = db.Column(db.Date,        default=date.today)
    # Streak freezes: a banked "miss one day, keep your streak" token. New
    # accounts start with one so a single off day early on doesn't wipe out
    # the first thing a new student built. Kinder-design note: punitive
    # streak resets are a well-documented manipulative-design pattern for
    # products used by children, so a miss costs a freeze, not the streak.
    streak_freezes = db.Column(db.Integer,    default=1)
    # Caps the "ship bonus" XP (saving a project) to once per real day, so
    # spam-saving the same project can't be used to farm XP.
    last_ship_bonus_date = db.Column(db.Date, nullable=True)
    # Parental consent (see /privacy and /terms) — captured at signup for any
    # account that self-identifies as under 18.
    is_minor             = db.Column(db.Boolean, default=False)
    parent_email         = db.Column(db.String(120), nullable=True)
    parent_verified       = db.Column(db.Boolean, default=True)  # True for adult accounts by default
    parent_verify_token   = db.Column(db.String(64), nullable=True)
    consent_recorded_at   = db.Column(db.DateTime, nullable=True)
    terms_accepted_at     = db.Column(db.DateTime, nullable=True)
    # Opt-in weekly parent digest — a standing (non-expiring) token lets a
    # parent reach their preferences page from the email at any time, without
    # needing to log in (they don't have a Nexa Pals account of their own).
    parent_digest_opt_in  = db.Column(db.Boolean, default=False)
    parent_manage_token   = db.Column(db.String(64), nullable=True)
    last_digest_sent_at   = db.Column(db.DateTime, nullable=True)
    classroom_id          = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=True)

    @property
    def level(self):
        thresholds = [0, 50, 150, 300, 500, 800, 1200, 1800, 2500, 9999]
        names      = ['Rookie','Explorer','Builder','Coder','Hacker',
                      'Wizard','Champion','Legend','Guru','Master']
        for i in range(len(thresholds)-1, -1, -1):
            if self.xp >= thresholds[i]:
                nxt = thresholds[i+1] if i+1 < len(thresholds) else None
                return {'num': i+1, 'name': names[i], 'next_xp': nxt, 'current_xp': thresholds[i]}
        return {'num': 1, 'name': 'Rookie', 'next_xp': 50, 'current_xp': 0}

    @property
    def level_progress_pct(self):
        lv = self.level
        if not lv['next_xp'] or lv['next_xp'] == lv['current_xp']:
            return 100
        return min(100, int((self.xp - lv['current_xp']) / (lv['next_xp'] - lv['current_xp']) * 100))

    STREAK_FREEZE_CAP = 3  # max freezes a student can bank at once

    def update_streak(self):
        """Called only when the student SHIPS something (completes a lesson,
        saves a project) — not on login. A streak that counts attendance
        rather than output just measures who remembered to open the app.

        Kinder-design note: a single missed day auto-spends a banked streak
        freeze (if one is available) instead of resetting the streak to 1.
        Losing a two-week streak because of one busy evening is the kind of
        harsh, loss-aversion-driven mechanic that's fine for adults who chose
        it and out of place in a product built for 10-year-olds."""
        from datetime import timedelta
        today = date.today()
        if self.last_active == today:
            return
        yesterday   = today - timedelta(days=1)
        missed_one  = today - timedelta(days=2)
        if self.last_active and self.last_active == yesterday:
            self.streak_days = (self.streak_days or 0) + 1
        elif self.last_active and self.last_active == missed_one and (self.streak_freezes or 0) > 0:
            self.streak_freezes -= 1
            self.streak_days = (self.streak_days or 0) + 1
        else:
            self.streak_days = 1
        self.last_active = today
        # Earn back a freeze at every full week of streak, capped.
        if self.streak_days and self.streak_days % 7 == 0 and (self.streak_freezes or 0) < self.STREAK_FREEZE_CAP:
            self.streak_freezes = (self.streak_freezes or 0) + 1

    LEAGUES = ['bronze', 'silver', 'gold', 'diamond']
    # Escalating weekly-XP thresholds to promote OUT of each league — climbing
    # gets a little harder each tier, same as the levels/XP curve already does.
    LEAGUE_PROMOTE_THRESHOLDS = {'bronze': 100, 'silver': 150, 'gold': 200}
    LEAGUE_PROMOTE_XP = LEAGUE_PROMOTE_THRESHOLDS['bronze']  # kept for back-compat display of the entry threshold

    def add_xp(self, amount):
        """The single place XP is ever added. Keeps all-time XP and this
        week's league XP in sync, and lazily rolls the league over if a new
        week has started since this user was last active."""
        self._sync_week()
        self.xp = (self.xp or 0) + amount
        self.weekly_xp = (self.weekly_xp or 0) + amount

    def _sync_week(self):
        """Rolls the league over when a new ISO week starts. Kinder-design
        note: leagues only ever go UP or stay the same here — there is no
        demotion for a quiet week. Being dropped a league for missing a week
        (illness, exams, a holiday) is discouraging in a way that doesn't
        serve a learning product; the upside of leagues (something to work
        toward) doesn't need a punitive downside to work."""
        from datetime import timedelta
        this_monday = date.today() - timedelta(days=date.today().weekday())
        if self.week_start == this_monday:
            return
        idx = self.LEAGUES.index(self.league) if self.league in self.LEAGUES else 0
        threshold = self.LEAGUE_PROMOTE_THRESHOLDS.get(self.league)
        if threshold is not None and (self.weekly_xp or 0) >= threshold and idx < len(self.LEAGUES) - 1:
            idx += 1
        self.league = self.LEAGUES[idx]
        self.weekly_xp = 0
        self.week_start = this_monday

    @property
    def league_promote_xp(self):
        """The weekly XP needed to move up from this user's CURRENT league,
        or None if they're already at the top league."""
        return self.LEAGUE_PROMOTE_THRESHOLDS.get(self.league)

class Badge(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    slug        = db.Column(db.String(50), unique=True, nullable=False)
    name        = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(200))
    emoji       = db.Column(db.String(20), default='fa-medal')  # Font Awesome icon class, not an emoji
    color       = db.Column(db.String(10), default='FFB347')

class UserBadge(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    badge_id  = db.Column(db.Integer, db.ForeignKey('badge.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)
    badge     = db.relationship('Badge')

class Classroom(db.Model):
    """A teacher's group of students — the school/classroom distribution
    channel. Deliberately simple for an MVP: one classroom per teacher, a
    student belongs to at most one classroom (via User.classroom_id), joined
    with a short human-typeable code rather than an email invite flow."""
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    join_code  = db.Column(db.String(10), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    students   = db.relationship('User', backref='classroom', foreign_keys='User.classroom_id')

class DailyChallenge(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    date        = db.Column(db.Date, unique=True, nullable=False)
    title       = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    xp_reward   = db.Column(db.Integer, default=25)
    html_start  = db.Column(db.Text, default='')
    css_start   = db.Column(db.Text, default='')
    js_start    = db.Column(db.Text, default='')

class UserProject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    html_code = db.Column(db.Text, default='')
    css_code = db.Column(db.Text, default='')
    js_code = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ProjectTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    difficulty = db.Column(db.String(20))
    icon = db.Column(db.String(50))
    color = db.Column(db.String(7))
    html_code = db.Column(db.Text, default='')
    css_code = db.Column(db.Text, default='')
    js_code = db.Column(db.Text, default='')
    order = db.Column(db.Integer, default=0)
    category = db.Column(db.String(50), default='general')  # 'game', 'art', 'general'

class Testimonial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(300), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    emoji = db.Column(db.String(20), default='fa-star')  # Font Awesome icon class, not an emoji
    is_approved = db.Column(db.Boolean, default=True)

class AnalyticsEvent(db.Model):
    """A minimal, self-hosted event log — no external service required.
    Swap this for real analytics (PostHog, GA, etc.) once you have network
    access and API keys; the call sites (_log_event) stay the same either way."""
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    meta = db.Column(db.Text, nullable=True)  # small JSON blob, e.g. {"lesson_id": 3}
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class ErrorLog(db.Model):
    """A minimal, self-hosted error log — swap for Sentry/equivalent once
    you have network access and an API key."""
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    path = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

def _log_event(event_type, user_id=None, meta=None):
    """Best-effort event log — never let a logging failure break the request
    that triggered it."""
    try:
        db.session.add(AnalyticsEvent(
            event_type=event_type,
            user_id=user_id,
            meta=json.dumps(meta) if meta else None,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    track = db.Column(db.String(50), nullable=False)   # 'html', 'css', 'javascript'
    order = db.Column(db.Integer, default=0)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)       # HTML content rendered in page
    quiz_json = db.Column(db.Text, default='[]')       # JSON array of question dicts
    practice_json = db.Column(db.Text, nullable=True)  # optional embedded live-code challenge
    xp_reward = db.Column(db.Integer, default=10)

class LessonProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    quiz_passed = db.Column(db.Boolean, default=False)
    score = db.Column(db.Integer, default=0)           # quiz % score
    completed_at = db.Column(db.DateTime)
    __table_args__ = (db.UniqueConstraint('user_id', 'lesson_id'),)

# ==================== RATE LIMITING ====================
# NOTE — scaling limitation: these limits are held in plain Python memory, so
# each gunicorn worker process has its OWN separate counters. With more than
# one worker, a user's requests can land on different workers and the limit
# effectively multiplies by the worker count. Fine for a single-worker deploy
# or local dev; before running multiple workers in production, replace this
# with a shared store (Redis is the standard choice) so all workers see the
# same counts. The function signatures below wouldn't need to change.
_failed_logins = defaultdict(list)
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300

def _is_rate_limited(ip):
    now = _time.time()
    _failed_logins[ip] = [t for t in _failed_logins[ip] if now - t < LOGIN_WINDOW_SECONDS]
    return len(_failed_logins[ip]) >= LOGIN_MAX_ATTEMPTS

def _record_failed_login(ip):
    _failed_logins[ip].append(_time.time())

# Generic sliding-window limiter reused for signup and the AI endpoints, keyed
# by (bucket, ip) so each limited action has its own independent window.
_action_hits = defaultdict(list)

def _is_action_rate_limited(bucket, ip, max_hits, window_seconds):
    now = _time.time()
    key = (bucket, ip)
    _action_hits[key] = [t for t in _action_hits[key] if now - t < window_seconds]
    if len(_action_hits[key]) >= max_hits:
        return True
    _action_hits[key].append(now)
    return False

SIGNUP_MAX_PER_WINDOW = 5
SIGNUP_WINDOW_SECONDS = 3600
AI_MAX_PER_WINDOW = 20
AI_WINDOW_SECONDS = 300

# ==================== SEED DATA ====================
LESSON_DATA = [
    # ── HTML TRACK ──────────────────────────────────────────────────────────────
    {
        'track': 'html', 'order': 1, 'title': 'What is HTML?', 'xp_reward': 10,
        'content': """
<p>HTML stands for <strong>HyperText Markup Language</strong>. It's the skeleton of every webpage — it tells the browser <em>what</em> to show.</p>
<p>HTML uses <strong>tags</strong> — little labels wrapped in angle brackets. Most tags come in pairs:</p>
<pre><code>&lt;h1&gt;Hello World&lt;/h1&gt;</code></pre>
<p>The first tag <code>&lt;h1&gt;</code> opens the element, and <code>&lt;/h1&gt;</code> (with the slash) closes it. Everything in between is the content!</p>
<p>Here are the most important tags:</p>
<ul>
  <li><code>&lt;h1&gt;</code> to <code>&lt;h6&gt;</code> — headings (h1 is biggest)</li>
  <li><code>&lt;p&gt;</code> — a paragraph</li>
  <li><code>&lt;strong&gt;</code> — <strong>bold</strong> text</li>
  <li><code>&lt;em&gt;</code> — <em>italic</em> text</li>
</ul>
<div class="lesson-try-it">
  <p><i class="fas fa-pen"></i> <strong>Try it!</strong> In the Playground, type:</p>
  <pre><code>&lt;h1&gt;My name is ...&lt;/h1&gt;\n&lt;p&gt;I love coding!&lt;/p&gt;</code></pre>
  <p>Then click <i class="fas fa-play"></i> Run and watch it appear!</p>
</div>
""",
        'practice_json': json.dumps({"starter_html": "<h1>My name is ...</h1>\n<!-- add a paragraph below with a sentence about yourself -->", "checks": [{"contains": "<p>", "hint": "Add a paragraph using &lt;p&gt;your sentence here&lt;/p&gt;."}], "success_msg": "Nice \u2014 your page now has a heading AND a paragraph!"}),
        'quiz_json': json.dumps([
            {"q": "What does HTML stand for?",
             "options": ["HyperText Markup Language","High Tech Modern Language","HyperText Making Language","Home Tool Markup Language"],
             "answer": 0},
            {"q": "Which tag makes the BIGGEST heading?",
             "options": ["<h6>","<h1>","<big>","<heading>"],
             "answer": 1},
            {"q": "How do you close an HTML tag?",
             "options": ["With a * before the name","With a / before the name","With a ! before the name","You don't need to close them"],
             "answer": 1},
        ])
    },
    {
        'track': 'html', 'order': 2, 'title': 'Links & Images', 'xp_reward': 10,
        'content': """
<p>Two of the most powerful HTML tags let you <strong>link to other pages</strong> and <strong>display pictures</strong>.</p>
<h3>Links — <code>&lt;a&gt;</code></h3>
<pre><code>&lt;a href="https://google.com"&gt;Visit Google&lt;/a&gt;</code></pre>
<p>The <code>href</code> attribute tells the browser <em>where</em> to go. An <strong>attribute</strong> is extra info you put inside the opening tag.</p>
<h3>Images — <code>&lt;img&gt;</code></h3>
<pre><code>&lt;img src="cat.jpg" alt="A fluffy cat"&gt;</code></pre>
<p><code>&lt;img&gt;</code> is a <strong>self-closing</strong> tag — it has no closing tag! The <code>src</code> attribute is the image address, and <code>alt</code> is a description for people who can't see it.</p>
<div class="lesson-try-it">
  <p><i class="fas fa-pen"></i> <strong>Try it!</strong></p>
  <pre><code>&lt;a href="https://wikipedia.org"&gt;Go to Wikipedia!&lt;/a&gt;\n&lt;br&gt;\n&lt;img src="https://placekitten.com/200/200" alt="cute kitten"&gt;</code></pre>
</div>
""",
        'practice_json': json.dumps({"starter_html": "<a>Visit Wikipedia</a>", "checks": [{"contains": "href=", "hint": "Add an href attribute, e.g. &lt;a href=\"https://wikipedia.org\"&gt;Visit Wikipedia&lt;/a&gt;."}], "success_msg": "Your link goes somewhere now \u2014 try clicking it in the preview!"}),
        'quiz_json': json.dumps([
            {"q": "Which attribute tells a link WHERE to go?",
             "options": ["src","link","href","url"],
             "answer": 2},
            {"q": "The <img> tag needs a closing </img> tag.",
             "options": ["True","False"],
             "answer": 1},
            {"q": "What does the 'alt' attribute on an image do?",
             "options": ["Makes the image alternate colours","Describes the image in words","Changes image size","Adds a link to the image"],
             "answer": 1},
        ])
    },
    {
        'track': 'html', 'order': 3, 'title': 'Lists & Tables', 'xp_reward': 10,
        'content': """
<p>HTML has two types of lists and a powerful table structure.</p>
<h3>Unordered List — bullets</h3>
<pre><code>&lt;ul&gt;\n  &lt;li&gt;Pizza&lt;/li&gt;\n  &lt;li&gt;Ice cream&lt;/li&gt;\n  &lt;li&gt;Robots&lt;/li&gt;\n&lt;/ul&gt;</code></pre>
<h3>Ordered List — numbers</h3>
<pre><code>&lt;ol&gt;\n  &lt;li&gt;Wake up&lt;/li&gt;\n  &lt;li&gt;Eat breakfast&lt;/li&gt;\n  &lt;li&gt;Code!&lt;/li&gt;\n&lt;/ol&gt;</code></pre>
<h3>Tables</h3>
<pre><code>&lt;table&gt;\n  &lt;tr&gt;\n    &lt;th&gt;Name&lt;/th&gt;\n    &lt;th&gt;Score&lt;/th&gt;\n  &lt;/tr&gt;\n  &lt;tr&gt;\n    &lt;td&gt;Karabo&lt;/td&gt;\n    &lt;td&gt;100&lt;/td&gt;\n  &lt;/tr&gt;\n&lt;/table&gt;</code></pre>
<p><code>&lt;tr&gt;</code> = table row, <code>&lt;th&gt;</code> = header cell, <code>&lt;td&gt;</code> = data cell.</p>
<div class="lesson-try-it">
  <p><i class="fas fa-pen"></i> <strong>Try it!</strong> Build a list of your top 3 favourite games or foods.</p>
</div>
""",
        'practice_json': json.dumps({
            'task': 'This list only has 2 items. Add a third &lt;li&gt; so it has 3, then hit Check.',
            'starter_html': '<ul>\n  <li>Pizza</li>\n  <li>Ice cream</li>\n</ul>',
            'checks': [
                {'contains': '<li>', 'min_count': 3, 'hint': 'You need at least 3 &lt;li&gt; items in your list.'},
            ],
            'success_msg': 'Your list has 3 items — nice work!',
        }),
        'quiz_json': json.dumps([
            {"q": "Which tag creates an UNORDERED (bulleted) list?",
             "options": ["<ol>","<list>","<ul>","<bl>"],
             "answer": 2},
            {"q": "What does <tr> stand for in a table?",
             "options": ["Table Row","Text Right","Table Result","Table Reference"],
             "answer": 0},
            {"q": "Which tag makes a table HEADER cell?",
             "options": ["<td>","<tc>","<th>","<thead>"],
             "answer": 2},
        ])
    },
    {
        'track': 'html', 'order': 4, 'title': 'Forms & Inputs', 'xp_reward': 15,
        'content': """
<p>Forms let users type information and send it — like login pages and search bars!</p>
<pre><code>&lt;form&gt;\n  &lt;label&gt;Your name:&lt;/label&gt;\n  &lt;input type="text" placeholder="Type here..."&gt;\n  &lt;br&gt;&lt;br&gt;\n  &lt;input type="submit" value="Send!"&gt;\n&lt;/form&gt;</code></pre>
<p>The <code>type</code> attribute changes what kind of input it is:</p>
<ul>
  <li><code>type="text"</code> — regular text box</li>
  <li><code>type="password"</code> — hides what you type</li>
  <li><code>type="email"</code> — checks for a valid email</li>
  <li><code>type="number"</code> — only allows numbers</li>
  <li><code>type="checkbox"</code> — a tick box</li>
  <li><code>type="submit"</code> — the Send button</li>
</ul>
<p>A <code>&lt;textarea&gt;</code> is for longer messages:</p>
<pre><code>&lt;textarea rows="4" placeholder="Write something..."&gt;&lt;/textarea&gt;</code></pre>
<div class="lesson-try-it">
  <p><i class="fas fa-pen"></i> <strong>Try it!</strong> Build a mini "about me" form with a name field, an email field, and a submit button.</p>
</div>
""",
        'practice_json': json.dumps({"starter_html": "<form>\n  <label>Your name:</label>\n  <input type=\"text\" placeholder=\"Type here...\">\n  <br><br>\n  <!-- add a submit button below -->\n</form>", "checks": [{"contains": "type=\"submit\"", "hint": "Add &lt;input type=\"submit\" value=\"Send!\"&gt; inside the form."}], "success_msg": "Your form is complete and ready to send!"}),
        'quiz_json': json.dumps([
            {"q": "Which input type hides your text as you type?",
             "options": ["type=\"hidden\"","type=\"secret\"","type=\"password\"","type=\"blur\""],
             "answer": 2},
            {"q": "What tag wraps all the inputs in a form?",
             "options": ["<input>","<form>","<group>","<fields>"],
             "answer": 1},
            {"q": "Which tag is best for a long message box?",
             "options": ["<input type=\"text\">","<input type=\"long\">","<textbox>","<textarea>"],
             "answer": 3},
        ])
    },
    # ── CSS TRACK ───────────────────────────────────────────────────────────────
    {
        'track': 'css', 'order': 1, 'title': 'What is CSS?', 'xp_reward': 10,
        'content': """
<p>If HTML is the skeleton of a page, <strong>CSS</strong> is the clothes and makeup! CSS stands for <strong>Cascading Style Sheets</strong>.</p>
<p>CSS rules look like this:</p>
<pre><code>h1 {\n  color: red;\n  font-size: 50px;\n}</code></pre>
<p>Break it down:</p>
<ul>
  <li><strong>Selector</strong> (<code>h1</code>) — which element to style</li>
  <li><strong>Property</strong> (<code>color</code>) — what to change</li>
  <li><strong>Value</strong> (<code>red</code>) — what to set it to</li>
</ul>
<p>You can use colour names (<code>red</code>, <code>blue</code>) or hex codes (<code>#FF0000</code> for red).</p>
<div class="lesson-try-it">
  <p><i class="fas fa-pen"></i> <strong>Try it!</strong> In the CSS panel of the Playground:</p>
  <pre><code>h1 { color: #FFB347; font-size: 60px; }\nbody { background: #1e2a3e; }</code></pre>
</div>
""",
        'practice_json': json.dumps({"starter_html": "<h1 id=\"title\">Hello!</h1>", "starter_css": "h1 {\n  /* style this heading \u2014 pick any colour you like */\n}", "checks": [{"contains": "color", "hint": "Add a color property inside the h1 { } rule, e.g. color: #FFB347;"}], "success_msg": "Your heading has some style now!"}),
        'quiz_json': json.dumps([
            {"q": "CSS stands for…",
             "options": ["Creative Style Syntax","Cascading Style Sheets","Computer Screen Styling","Coloured Style System"],
             "answer": 1},
            {"q": "In a CSS rule, what is the SELECTOR?",
             "options": ["The value after the colon","The part inside the { }","The element you want to style","The property you want to change"],
             "answer": 2},
            {"q": "Which CSS property changes text colour?",
             "options": ["font-color","text-color","color","colour"],
             "answer": 2},
        ])
    },
    {
        'track': 'css', 'order': 2, 'title': 'Colours & Backgrounds', 'xp_reward': 10,
        'content': """
<p>CSS gives you lots of ways to set colours and backgrounds.</p>
<h3>Colour formats</h3>
<ul>
  <li><strong>Named</strong>: <code>color: tomato;</code></li>
  <li><strong>Hex</strong>: <code>color: #FF6347;</code></li>
  <li><strong>RGB</strong>: <code>color: rgb(255, 99, 71);</code></li>
</ul>
<h3>Backgrounds</h3>
<pre><code>body {\n  background-color: #f0f5ff;\n  background-image: url("pattern.png");\n}</code></pre>
<p>The coolest trick: <strong>gradients</strong>!</p>
<pre><code>body {\n  background: linear-gradient(135deg, #FFB347, #9B7EDE);\n}</code></pre>
<div class="lesson-try-it">
  <p><i class="fas fa-pen"></i> <strong>Try it!</strong></p>
  <pre><code>body {\n  background: linear-gradient(135deg, #667eea, #764ba2);\n  color: white;\n  font-family: sans-serif;\n  text-align: center;\n  padding: 50px;\n}</code></pre>
</div>
""",
        'practice_json': json.dumps({"starter_css": "body {\n  /* give the whole page a nice colour behind everything */\n}", "checks": [{"contains": "background", "hint": "Add a background-color (or background) property inside the body rule."}], "success_msg": "The whole page has a background now \u2014 much better than plain white!"}),
        'quiz_json': json.dumps([
            {"q": "Which is a valid CSS hex colour?",
             "options": ["color: red-255","color: #FF5733","color: rgb-orange","color: 255,0,0"],
             "answer": 1},
            {"q": "How do you make a gradient background in CSS?",
             "options": ["background: gradient(red, blue)","background: mix(red, blue)","background: linear-gradient(red, blue)","background-gradient: linear red blue"],
             "answer": 2},
            {"q": "Which property sets a plain background colour?",
             "options": ["background","background-color","bg-color","color-background"],
             "answer": 1},
        ])
    },
    {
        'track': 'css', 'order': 3, 'title': 'Fonts, Size & Spacing', 'xp_reward': 10,
        'content': """
<p>Typography — the art of setting text — is huge in web design.</p>
<h3>Font properties</h3>
<pre><code>p {\n  font-family: 'Arial', sans-serif;\n  font-size: 18px;\n  font-weight: bold;\n  line-height: 1.6;\n}</code></pre>
<h3>Spacing: margin & padding</h3>
<p><strong>Margin</strong> = space OUTSIDE the element. <strong>Padding</strong> = space INSIDE.</p>
<pre><code>div {\n  margin: 20px;\n  padding: 10px;\n  border: 3px solid #FFB347;\n}</code></pre>
<p>Think of it like a framed picture: padding is the gap inside the frame, margin is the wall space around the frame.</p>
<div class="lesson-try-it">
  <p><i class="fas fa-pen"></i> <strong>Try it!</strong></p>
  <pre><code>div {\n  background: white;\n  margin: 30px auto;\n  padding: 20px;\n  border-radius: 20px;\n  width: 300px;\n  box-shadow: 0 10px 30px rgba(0,0,0,0.1);\n}</code></pre>
</div>
""",
        'practice_json': json.dumps({"starter_html": "<p>This text feels a bit squished against the edges.</p>", "starter_css": "p {\n  /* give this paragraph some breathing room around the text */\n}", "checks": [{"contains": "padding", "hint": "Add padding inside the p { } rule, e.g. padding: 15px;"}], "success_msg": "That paragraph has room to breathe now!"}),
        'quiz_json': json.dumps([
            {"q": "What is the difference between margin and padding?",
             "options": ["They are the same thing","Margin is space inside, padding is space outside","Margin is space outside, padding is space inside","Margin is for text, padding is for images"],
             "answer": 2},
            {"q": "Which property rounds the corners of an element?",
             "options": ["corner-radius","border-round","border-radius","round-corners"],
             "answer": 2},
            {"q": "Which unit makes font size relative to the screen?",
             "options": ["px","vw","em","cm"],
             "answer": 1},
        ])
    },
    {
        'track': 'css', 'order': 4, 'title': 'Flexbox Layout', 'xp_reward': 15,
        'content': """
<p><strong>Flexbox</strong> is a CSS superpower for arranging elements in a row or column.</p>
<pre><code>.container {\n  display: flex;\n  gap: 20px;\n  justify-content: center;\n  align-items: center;\n  flex-wrap: wrap;\n}</code></pre>
<p>Key properties:</p>
<ul>
  <li><code>justify-content</code> — horizontal alignment (<code>center</code>, <code>space-between</code>, <code>flex-start</code>)</li>
  <li><code>align-items</code> — vertical alignment (<code>center</code>, <code>flex-start</code>, <code>stretch</code>)</li>
  <li><code>flex-wrap: wrap</code> — items wrap to next line if they don't fit</li>
  <li><code>gap</code> — space between items</li>
</ul>
<div class="lesson-try-it">
  <p><i class="fas fa-pen"></i> <strong>Try it!</strong></p>
  <pre><code>&lt;div class="row"&gt;\n  &lt;div class="card"&gt;Games&lt;/div&gt;\n  &lt;div class="card"&gt;Art&lt;/div&gt;\n  &lt;div class="card"&gt;Robots&lt;/div&gt;\n&lt;/div&gt;</code></pre>
  <pre><code>.row { display: flex; gap: 20px; justify-content: center; padding: 30px; }\n.card { background: #9B7EDE; color: white; padding: 20px 30px; border-radius: 20px; font-size: 1.3rem; font-weight: bold; }</code></pre>
</div>
""",
        'practice_json': json.dumps({"starter_html": "<div class=\"row\">\n  <div class=\"card\">Games</div>\n  <div class=\"card\">Art</div>\n  <div class=\"card\">Robots</div>\n</div>", "starter_css": ".row {\n  /* make these cards line up neatly in a row, evenly spaced */\n}\n.card {\n  background: #9B7EDE;\n  color: white;\n  padding: 15px 25px;\n  border-radius: 16px;\n  font-weight: bold;\n}", "checks": [{"contains": "display", "hint": "Add display: flex; to the .row rule."}, {"contains": "flex", "hint": "Set display to flex so the cards line up in a row."}], "success_msg": "Flexbox in action \u2014 those cards are lined up perfectly!"}),
        'quiz_json': json.dumps([
            {"q": "Which CSS property enables flexbox on a container?",
             "options": ["layout: flex","flex: true","display: flex","flex-mode: on"],
             "answer": 2},
            {"q": "Which property controls HORIZONTAL alignment in a flex row?",
             "options": ["align-items","flex-align","justify-content","horizontal-align"],
             "answer": 2},
            {"q": "What does 'flex-wrap: wrap' do?",
             "options": ["Wraps text in italic","Makes items wrap to next line","Wraps the container in a border","Disables flexbox"],
             "answer": 1},
        ])
    },
    {
        'track': 'css', 'order': 5, 'title': 'Animations & Transitions', 'xp_reward': 15,
        'content': """
<p>CSS can animate elements — no JavaScript needed!</p>
<h3>Transitions — smooth changes on hover</h3>
<pre><code>button {\n  background: #FFB347;\n  transition: background 0.3s, transform 0.2s;\n}\nbutton:hover {\n  background: #9B7EDE;\n  transform: scale(1.1);\n}</code></pre>
<h3>Keyframe Animations — repeating motion</h3>
<pre><code>@keyframes bounce {\n  0%   { transform: translateY(0); }\n  50%  { transform: translateY(-30px); }\n  100% { transform: translateY(0); }\n}\n\n.ball {\n  animation: bounce 1s infinite;\n}</code></pre>
<p><code>@keyframes</code> defines the motion, then you assign it to an element with the <code>animation</code> property.</p>
<div class="lesson-try-it">
  <p><i class="fas fa-pen"></i> <strong>Try it!</strong> Make a shape bounce:</p>
  <pre><code>&lt;div class="flyer"&gt;&lt;/div&gt;</code></pre>
  <pre><code>@keyframes fly {\n  0%,100% { transform: translateY(0) rotate(0deg); }\n  50% { transform: translateY(-40px) rotate(10deg); }\n}\n.flyer { width: 60px; height: 60px; background: #9B7EDE; border-radius: 16px; margin: 50px auto 0; animation: fly 2s infinite; }</code></pre>
</div>
""",
        'practice_json': json.dumps({"starter_html": "<div class=\"ball\"></div>", "starter_css": ".ball {\n  width: 50px;\n  height: 50px;\n  background: #9B7EDE;\n  border-radius: 50%;\n  margin: 40px auto;\n  /* make the hover effect below happen smoothly, not instantly */\n}\n.ball:hover {\n  transform: scale(1.3);\n}", "checks": [{"contains": "transition", "hint": "Add a transition property to .ball, e.g. transition: transform 0.3s;"}], "success_msg": "Hover over the ball now \u2014 smooth, not snappy. That's a transition!"}),
        'quiz_json': json.dumps([
            {"q": "Which CSS property makes a smooth colour change on hover?",
             "options": ["animation","transform","transition","keyframes"],
             "answer": 2},
            {"q": "What does 'animation: bounce 1s infinite' mean?",
             "options": ["Play bounce once for 1 second","Play bounce for 1 second then stop","Play bounce animation every 1 second, forever","Bounce by 1 pixel infinitely"],
             "answer": 2},
            {"q": "Which keyword starts a CSS animation definition?",
             "options": ["@animation","@keyframes","@motion","@frames"],
             "answer": 1},
        ])
    },
    # ── JAVASCRIPT TRACK ─────────────────────────────────────────────────────────
    {
        'track': 'javascript', 'order': 1, 'title': 'Variables & Data Types', 'xp_reward': 10,
        'content': """
<p>JavaScript (JS) makes web pages <strong>interactive</strong> — clicks, games, forms that react!</p>
<h3>Variables — storing information</h3>
<pre><code>let name = "Karabo";\nlet age = 12;\nlet isCool = true;\n\nconsole.log(name); // prints: Karabo</code></pre>
<ul>
  <li><code>let</code> — a variable you can change later</li>
  <li><code>const</code> — a value that never changes</li>
  <li><code>var</code> — the old way (avoid it)</li>
</ul>
<h3>Data types</h3>
<ul>
  <li><strong>String</strong>: text in quotes → <code>"hello"</code></li>
  <li><strong>Number</strong>: a number → <code>42</code></li>
  <li><strong>Boolean</strong>: true or false → <code>true</code></li>
</ul>
<div class="lesson-try-it">
  <p><i class="fas fa-pen"></i> <strong>Try it!</strong> In the JS panel:</p>
  <pre><code>let myName = "Your name here";\nlet myAge = 12;\nalert("Hi! I am " + myName + " and I am " + myAge + " years old!");</code></pre>
</div>
""",
        'practice_json': json.dumps({"starter_js": "let myName = \"Your name here\";\nlet myAge = 12;\n\n// pop up a message on the screen with your name and age\n", "checks": [{"contains": "alert(", "hint": "Use alert(...) to pop up a message, e.g. alert(\"Hi \" + myName);"}], "success_msg": "There's your message, popped right up \u2014 nice work with variables!"}),
        'quiz_json': json.dumps([
            {"q": "Which keyword creates a variable you can change later?",
             "options": ["const","fixed","let","var"],
             "answer": 2},
            {"q": "What data type is: \"Hello World\"?",
             "options": ["Number","Boolean","String","Variable"],
             "answer": 2},
            {"q": "What does console.log() do?",
             "options": ["Shows an alert popup","Logs text to the browser console","Creates a variable","Adds text to the page"],
             "answer": 1},
        ])
    },
    {
        'track': 'javascript', 'order': 2, 'title': 'If Statements & Logic', 'xp_reward': 10,
        'content': """
<p><strong>If statements</strong> let your code make decisions!</p>
<pre><code>let score = 85;\n\nif (score >= 90) {\n  alert("A - Amazing!");\n} else if (score >= 70) {\n  alert("B - Good job!");\n} else {\n  alert("Keep practising!");\n}</code></pre>
<h3>Comparison operators</h3>
<ul>
  <li><code>===</code> — exactly equal</li>
  <li><code>!==</code> — not equal</li>
  <li><code>&gt;</code> — greater than</li>
  <li><code>&lt;</code> — less than</li>
  <li><code>&gt;=</code> — greater than or equal</li>
</ul>
<h3>Logical operators</h3>
<ul>
  <li><code>&&</code> — AND (both must be true)</li>
  <li><code>||</code> — OR (at least one must be true)</li>
  <li><code>!</code> — NOT (flip true to false)</li>
</ul>
<div class="lesson-try-it">
  <p><i class="fas fa-pen"></i> <strong>Try it!</strong></p>
  <pre><code>let password = prompt("Enter the secret password:");\nif (password === "nexa123") {\n  alert("Access granted! Welcome, pal!");\n} else {\n  alert("Wrong password. Try again!");\n}</code></pre>
</div>
""",
        'practice_json': json.dumps({"starter_js": "let score = 85;\n\n// look at the score and pop up a message that depends on how good it is\n", "checks": [{"contains": "if", "hint": "Use an if statement: if (score >= 90) { ... }"}, {"contains": "else", "hint": "Add an else (or else if) for the other cases."}], "success_msg": "Your code is making decisions now \u2014 that's the heart of programming!"}),
        'quiz_json': json.dumps([
            {"q": "Which operator checks if two values are EXACTLY equal?",
             "options": ["==","=","===","equals"],
             "answer": 2},
            {"q": "What does the && operator mean?",
             "options": ["OR","NOT","AND","EQUALS"],
             "answer": 2},
            {"q": "What runs when the if condition is FALSE?",
             "options": ["The if block again","The else block","Nothing happens","The whole page reloads"],
             "answer": 1},
        ])
    },
    {
        'track': 'javascript', 'order': 3, 'title': 'Functions', 'xp_reward': 10,
        'content': """
<p>A <strong>function</strong> is a named block of code you can use over and over.</p>
<pre><code>function greet(name) {\n  return "Hello, " + name + "!";\n}\n\nlet message = greet("Thabiso");\nalert(message); // "Hello, Thabiso!"</code></pre>
<p>Functions can take <strong>parameters</strong> (inputs) and <strong>return</strong> a value (output).</p>
<h3>Arrow functions (short version)</h3>
<pre><code>const double = (n) => n * 2;\nconsole.log(double(5)); // 10</code></pre>
<h3>Why use functions?</h3>
<ul>
  <li>Write code once, use it many times</li>
  <li>Keep your code tidy and readable</li>
  <li>Easy to fix — change the function, it changes everywhere</li>
</ul>
<div class="lesson-try-it">
  <p><i class="fas fa-pen"></i> <strong>Try it!</strong></p>
  <pre><code>function calculateScore(correct, total) {\n  let percent = Math.round((correct / total) * 100);\n  return "You got " + percent + "%!";\n}\nalert(calculateScore(8, 10)); // "You got 80%!"</code></pre>
</div>
""",
        'practice_json': json.dumps({
            'task': 'Write a function called sayHi that returns "Hello, pal!", then call it inside an alert().',
            'starter_js': 'function sayHi() {\n  // your code here\n}\n\n// now call your function inside an alert() below\n',
            'checks': [
                {'contains': 'function sayhi', 'hint': 'Start with: function sayHi() { ... }'},
                {'contains': 'return', 'hint': "Your function needs to return a value with the return keyword."},
                {'contains': 'sayhi(', 'min_count': 2, 'hint': 'Call sayHi() somewhere after defining it, e.g. alert(sayHi());'},
            ],
            'success_msg': 'Your function works and you called it — that\'s the whole idea of a function!',
        }),
        'quiz_json': json.dumps([
            {"q": "What keyword defines a function?",
             "options": ["def","fn","function","make"],
             "answer": 2},
            {"q": "What does 'return' do in a function?",
             "options": ["Exits the whole program","Sends a value back to where the function was called","Repeats the function","Deletes the function"],
             "answer": 1},
            {"q": "What are the inputs to a function called?",
             "options": ["Returns","Arguments/Parameters","Inputs","Variables"],
             "answer": 1},
        ])
    },
    {
        'track': 'javascript', 'order': 4, 'title': 'DOM — Changing the Page', 'xp_reward': 15,
        'content': """
<p>The DOM (Document Object Model) lets JavaScript <strong>talk to your HTML</strong> and change it live!</p>
<h3>Finding elements</h3>
<pre><code>// Find by ID\nlet title = document.getElementById("myTitle");\n\n// Find by CSS class\nlet cards = document.querySelectorAll(".card");</code></pre>
<h3>Changing things</h3>
<pre><code>// Change text\ntitle.textContent = "New Title!";\n\n// Change style\ntitle.style.color = "red";\ntitle.style.fontSize = "3rem";\n\n// Add/remove CSS classes\ntitle.classList.add("highlight");\ntitle.classList.remove("hidden");</code></pre>
<h3>Responding to clicks</h3>
<pre><code>let btn = document.getElementById("myBtn");\nbtn.addEventListener("click", function() {\n  alert("You clicked me!");\n});</code></pre>
<div class="lesson-try-it">
  <p><i class="fas fa-pen"></i> <strong>Try it!</strong></p>
  <pre><code>&lt;h1 id="title"&gt;Click the button!&lt;/h1&gt;\n&lt;button id="btn"&gt;Change Me&lt;/button&gt;</code></pre>
  <pre><code>let colours = ["#FFB347","#9B7EDE","#5D9BEC","#1e5f4b"];\nlet i = 0;\ndocument.getElementById("btn").addEventListener("click", () => {\n  document.getElementById("title").style.color = colours[i % colours.length];\n  document.getElementById("title").textContent = "Colour #" + (i+1);\n  i++;\n});</code></pre>
</div>
""",
        'practice_json': json.dumps({"starter_html": "<h1 id=\"title\">Click the button!</h1>\n<button id=\"btn\">Change Me</button>", "starter_js": "// when the button is clicked, change the title's text and colour\n", "checks": [{"contains": "addeventlistener", "hint": "Use btn.addEventListener(\"click\", ...) to respond to the click."}, {"contains": "textcontent", "hint": "Change the title's textContent inside your click handler."}], "success_msg": "Click the button in the preview \u2014 your JavaScript just changed the page live!"}),
        'quiz_json': json.dumps([
            {"q": "What does document.getElementById('x') do?",
             "options": ["Deletes the element with id x","Creates an element with id x","Finds and returns the element with id x","Changes the element's id to x"],
             "answer": 2},
            {"q": "How do you change an element's text with JavaScript?",
             "options": ["element.text = 'new'","element.html = 'new'","element.textContent = 'new'","element.write = 'new'"],
             "answer": 2},
            {"q": "Which method listens for a button click?",
             "options": ["element.onClick()","element.listenClick()","element.addEventListener('click', fn)","element.onPress(fn)"],
             "answer": 2},
        ])
    },
    {
        'track': 'javascript', 'order': 5, 'title': 'Loops & Arrays', 'xp_reward': 15,
        'content': """
<p><strong>Arrays</strong> store lists of things. <strong>Loops</strong> repeat code.</p>
<h3>Arrays</h3>
<pre><code>let fruits = ["apple", "banana", "mango"];\nconsole.log(fruits[0]); // "apple"  (index starts at 0!)\nconsole.log(fruits.length); // 3\n\nfruits.push("pineapple"); // add to end\nfruits.pop();             // remove from end</code></pre>
<h3>For Loop</h3>
<pre><code>for (let i = 0; i &lt; 5; i++) {\n  console.log("Round " + i);\n}</code></pre>
<h3>For…of (easier for arrays)</h3>
<pre><code>for (let fruit of fruits) {\n  console.log("I love " + fruit);\n}</code></pre>
<div class="lesson-try-it">
  <p><i class="fas fa-pen"></i> <strong>Try it!</strong> Make a list appear on the page:</p>
  <pre><code>&lt;ul id="list"&gt;&lt;/ul&gt;</code></pre>
  <pre><code>let games = ["Snake", "Flappy Bird", "Pac-Man", "Tetris"];\nlet ul = document.getElementById("list");\nfor (let game of games) {\n  let li = document.createElement("li");\n  li.textContent = game;\n  ul.appendChild(li);\n}</code></pre>
</div>
""",
        'practice_json': json.dumps({
            'task': 'Use a for loop to print the numbers 1 to 5 into the output box below.',
            'starter_html': '<div id="output"></div>',
            'starter_js': 'let output = document.getElementById("output");\n\n// write your loop here — use output.innerHTML += ...\n',
            'checks': [
                {'contains': 'for', 'hint': 'Use a for loop: for (let i = 1; i <= 5; i++) { ... }'},
                {'contains': 'output', 'hint': "Update the output element so we can see the numbers appear."},
            ],
            'success_msg': 'Your loop ran — that\'s 5 lines of output from 2 lines of code!',
        }),
        'quiz_json': json.dumps([
            {"q": "What index does the FIRST item in an array have?",
             "options": ["1","0","-1","First"],
             "answer": 1},
            {"q": "Which method adds an item to the END of an array?",
             "options": ["array.add()","array.append()","array.push()","array.insert()"],
             "answer": 2},
            {"q": "What does a for loop do?",
             "options": ["Runs code once","Runs code a set number of times","Checks a condition once","Creates an array"],
             "answer": 1},
        ])
    },
    {
        'track': 'javascript', 'order': 6, 'title': 'Build a Clicker Game', 'xp_reward': 25,
        'content': """
<p>Let's put everything together and build a real game! A <strong>clicker game</strong> tracks how many times you click and rewards you with levels.</p>
<p>Here's the full game — read through each part and understand it:</p>
<pre><code>&lt;!-- HTML --&gt;\n&lt;div style="text-align:center; font-family:sans-serif; padding:30px;"&gt;\n  &lt;h1 id="level"&gt;Level 1: Rookie&lt;/h1&gt;\n  &lt;p id="score"&gt;Clicks: 0&lt;/p&gt;\n  &lt;button id="btn" style="font-size:1.4rem; padding:20px 40px; border:none; border-radius:16px; background:#9B7EDE; color:white; cursor:pointer;"&gt;Click me!&lt;/button&gt;\n  &lt;p id="msg"&gt;&lt;/p&gt;\n&lt;/div&gt;</code></pre>
<pre><code>// JavaScript\nlet clicks = 0;\nconst levels = [\n  { at: 0,   name: "Level 1: Rookie" },\n  { at: 10,  name: "Level 2: Builder" },\n  { at: 30,  name: "Level 3: Coder" },\n  { at: 60,  name: "Level 4: Hacker" },\n  { at: 100, name: "Level 5: Ultimate Coder" },\n];\n\ndocument.getElementById("btn").addEventListener("click", () => {\n  clicks++;\n  document.getElementById("score").textContent = "Clicks: " + clicks;\n\n  // Check for level up\n  for (let i = levels.length - 1; i &gt;= 0; i--) {\n    if (clicks &gt;= levels[i].at) {\n      document.getElementById("level").textContent = levels[i].name;\n      break;\n    }\n  }\n\n  if (clicks === 100) {\n    document.getElementById("msg").textContent = "YOU WIN! Ultimate Coder!";\n  }\n});</code></pre>
<div class="lesson-try-it">
  <p><i class="fas fa-flag-checkered"></i> <strong>Your challenge!</strong> Copy this into the Playground and then modify it: add a new level at 200 clicks, change the level names, or add a Reset button!</p>
</div>
""",
        'practice_json': json.dumps({"starter_html": "<h1 id=\"countDisplay\">0</h1>\n<button id=\"clickBtn\">Click me!</button>", "starter_js": "let count = 0;\nlet countDisplay = document.getElementById(\"countDisplay\");\nlet clickBtn = document.getElementById(\"clickBtn\");\n\n// when clickBtn is clicked: increase count by 1, then update countDisplay to show it\n", "checks": [{"contains": "addeventlistener", "hint": "Use clickBtn.addEventListener(\"click\", ...) to respond to clicks."}, {"contains": "textcontent", "hint": "Update the page to show the new count, e.g. countDisplay.textContent = count;"}], "success_msg": "You just built the core of a clicker game \u2014 every click updates in real time!"}),
        'quiz_json': json.dumps([
            {"q": "In the clicker game, what does the 'at' property in each level object mean?",
             "options": ["The emoji to show","The level name","The number of clicks needed to reach that level","The XP reward"],
             "answer": 2},
            {"q": "Why does the level-checking loop go backwards (from the end)?",
             "options": ["It's faster","To find the highest level the player has reached","Arrays must always be looped backwards","It doesn't matter"],
             "answer": 1},
            {"q": "What JavaScript method attaches the click handler to the button?",
             "options": ["btn.onClick()","btn.click()","btn.addEventListener('click', fn)","btn.on('click', fn)"],
             "answer": 2},
        ])
    },
]

GAME_TEMPLATES = [
    {
        'name': 'Snake Game',
        'description': 'Classic snake — eat food, grow longer, don\'t hit the walls!',
        'difficulty': 'intermediate',
        'icon': 'fa-worm',
        'color': '#1e5f4b',
        'category': 'game',
        'order': 10,
        'html_code': '<canvas id="c" width="400" height="400"></canvas>',
        'css_code': 'body{background:#1e2a3e;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;flex-direction:column;font-family:sans-serif;color:white} #c{border:4px solid #FFB347;border-radius:8px} #info{margin-top:10px;font-size:1.2rem;}',
        'js_code': '''const c=document.getElementById('c'),ctx=c.getContext('2d');
const SZ=20,COLS=20,ROWS=20;
let snake=[{x:10,y:10}],dir={x:1,y:0},food={},score=0,running=true;
function rndFood(){food={x:Math.floor(Math.random()*COLS),y:Math.floor(Math.random()*ROWS)};}
rndFood();
document.addEventListener('keydown',e=>{
  if(e.key==='ArrowUp'&&dir.y===0)dir={x:0,y:-1};
  if(e.key==='ArrowDown'&&dir.y===0)dir={x:0,y:1};
  if(e.key==='ArrowLeft'&&dir.x===0)dir={x:-1,y:0};
  if(e.key==='ArrowRight'&&dir.x===0)dir={x:1,y:0};
});
function draw(){
  ctx.fillStyle='#1e2a3e';ctx.fillRect(0,0,400,400);
  // food
  ctx.fillStyle='#FFB347';ctx.fillRect(food.x*SZ+2,food.y*SZ+2,SZ-4,SZ-4);
  // snake
  snake.forEach((s,i)=>{ctx.fillStyle=i===0?'#9B7EDE':'#5D9BEC';ctx.fillRect(s.x*SZ+1,s.y*SZ+1,SZ-2,SZ-2);});
  // score
  ctx.fillStyle='white';ctx.font='16px sans-serif';ctx.fillText('Score: '+score,8,20);
  if(!running){ctx.fillStyle='rgba(0,0,0,0.6)';ctx.fillRect(0,0,400,400);ctx.fillStyle='#FFB347';ctx.font='bold 32px sans-serif';ctx.textAlign='center';ctx.fillText('Game Over!',200,180);ctx.font='20px sans-serif';ctx.fillText('Score: '+score,200,220);ctx.fillText('Refresh to play again',200,260);}
}
function update(){
  if(!running)return;
  const head={x:snake[0].x+dir.x,y:snake[0].y+dir.y};
  if(head.x<0||head.x>=COLS||head.y<0||head.y>=ROWS){running=false;return;}
  if(snake.some(s=>s.x===head.x&&s.y===head.y)){running=false;return;}
  snake.unshift(head);
  if(head.x===food.x&&head.y===food.y){score++;rndFood();}
  else snake.pop();
}
setInterval(()=>{update();draw();},120);
'''
    },
    {
        'name': 'Memory Match',
        'description': 'Flip cards and find matching pairs — train your memory!',
        'difficulty': 'beginner',
        'icon': 'fa-brain',
        'color': '#9B7EDE',
        'category': 'game',
        'order': 11,
        'html_code': '<div id="grid"></div><div id="info">Pairs found: <span id="pairs">0</span>/8 &nbsp; Moves: <span id="moves">0</span></div>',
        'css_code': 'body{font-family:sans-serif;text-align:center;background:#f0f5ff;padding:20px} #grid{display:grid;grid-template-columns:repeat(4,90px);gap:10px;justify-content:center;margin:20px auto} .card{width:90px;height:90px;font-size:1.5rem;font-family:monospace;font-weight:700;display:flex;align-items:center;justify-content:center;background:#9B7EDE;color:white;border-radius:16px;cursor:pointer;border:4px solid #FFB347;box-shadow:0 6px 0 #6B4F9E;transition:.2s;user-select:none} .card.flipped{background:white;box-shadow:0 2px 0 #ccc} .card.matched{background:#1e5f4b;border-color:#1e5f4b;box-shadow:none;cursor:default} #info{font-size:1.2rem;font-weight:600;color:#1e3a5f;margin-top:10px}',
        'js_code': '''const symbols=['{ }','< >','( )','[ ]','#','&&','||','=='];
let cards=[...symbols,...symbols].sort(()=>Math.random()-.5);
let flipped=[],matched=0,moves=0,locked=false;
const grid=document.getElementById('grid');
cards.forEach((e,i)=>{
  const d=document.createElement('div');
  d.className='card';d.dataset.val=e;d.dataset.idx=i;
  d.addEventListener('click',()=>flip(d));
  grid.appendChild(d);
});
function flip(d){
  if(locked||d.classList.contains('flipped')||d.classList.contains('matched'))return;
  d.classList.add('flipped');d.textContent=d.dataset.val;
  flipped.push(d);
  if(flipped.length===2){
    moves++;document.getElementById('moves').textContent=moves;locked=true;
    if(flipped[0].dataset.val===flipped[1].dataset.val){
      flipped.forEach(c=>c.classList.add('matched'));
      matched++;document.getElementById('pairs').textContent=matched;
      flipped=[];locked=false;
      if(matched===8)setTimeout(()=>alert('You won in '+moves+' moves!'),200);
    } else {
      setTimeout(()=>{flipped.forEach(c=>{c.classList.remove('flipped');c.textContent='';});flipped=[];locked=false;},900);
    }
  }
}
'''
    },
    {
        'name': 'Catch the Stars',
        'description': 'Move your basket with arrow keys and catch falling stars!',
        'difficulty': 'beginner',
        'icon': 'fa-star',
        'color': '#FFB347',
        'category': 'game',
        'order': 12,
        'html_code': '<canvas id="c" width="400" height="500"></canvas>',
        'css_code': 'body{background:#1e2a3e;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;flex-direction:column;font-family:sans-serif;color:white}#c{border:4px solid #FFB347;border-radius:8px}',
        'js_code': '''const c=document.getElementById('c'),ctx=c.getContext('2d');
let basket={x:160,w:80,y:450,h:20},stars=[],score=0,lives=3,spd=2.5;
function addStar(){stars.push({x:Math.random()*360+20,y:-20,r:15,spd:spd+(Math.random()*2)});}
setInterval(addStar,1200);
document.addEventListener('keydown',e=>{if(e.key==='ArrowLeft')basket.x=Math.max(0,basket.x-30);if(e.key==='ArrowRight')basket.x=Math.min(320,basket.x+30);});
function drawStar(cx,cy,r){
  ctx.beginPath();
  for(let i=0;i<5;i++){
    const outer=-Math.PI/2+i*(2*Math.PI/5);
    const inner=outer+Math.PI/5;
    ctx.lineTo(cx+r*Math.cos(outer),cy+r*Math.sin(outer));
    ctx.lineTo(cx+r*0.45*Math.cos(inner),cy+r*0.45*Math.sin(inner));
  }
  ctx.closePath();ctx.fill();
}
function loop(){
  ctx.clearRect(0,0,400,500);
  // basket
  ctx.fillStyle='#FFB347';ctx.beginPath();ctx.roundRect(basket.x,basket.y,basket.w,basket.h,8);ctx.fill();
  // stars
  stars=stars.filter(s=>{
    s.y+=s.spd;
    ctx.fillStyle='#FFE347';drawStar(s.x,s.y,s.r);
    if(s.y>450&&s.x+15>basket.x&&s.x-15<basket.x+basket.w){score++;spd=2.5+score*0.05;return false;}
    if(s.y>510){lives--;return false;}
    return true;
  });
  ctx.fillStyle='white';ctx.font='18px sans-serif';ctx.fillText('Score: '+score,10,28);ctx.fillText('Lives: '+lives,320,28);
  if(lives<=0){ctx.fillStyle='rgba(0,0,0,.6)';ctx.fillRect(0,0,400,500);ctx.fillStyle='#FFB347';ctx.font='bold 32px sans-serif';ctx.textAlign='center';ctx.fillText('Game Over!',200,220);ctx.fillText('Score: '+score,200,268);return;}
  requestAnimationFrame(loop);
}
loop();
'''
    },
    {
        'name': 'Typing Speed Test',
        'description': 'How fast can you type? Race the clock and beat your high score!',
        'difficulty': 'beginner',
        'icon': 'fa-keyboard',
        'color': '#5D9BEC',
        'category': 'game',
        'order': 13,
        'html_code': '''<div id="app">
  <h2>Typing Speed Test</h2>
  <div id="wordDisplay"></div>
  <input id="typeInput" placeholder="Start typing to begin!" autocomplete="off">
  <div id="stats">Time: <span id="timer">30</span>s &nbsp; Score: <span id="score">0</span> &nbsp; WPM: <span id="wpm">0</span></div>
  <button id="restart"><i class="fas fa-rotate-right"></i> Restart</button>
</div>''',
        'css_code': '''body{font-family:sans-serif;background:#f0f5ff;display:flex;justify-content:center;padding:30px}
#app{text-align:center;max-width:500px;width:100%}
#wordDisplay{font-size:2rem;font-weight:700;margin:20px 0;padding:20px;background:white;border-radius:20px;border:4px solid #FFB347;min-height:80px;color:#1e3a5f}
#wordDisplay span.correct{color:#1e5f4b}#wordDisplay span.wrong{color:#e25c5c}
#typeInput{width:90%;padding:12px;font-size:1.2rem;border:4px solid #9B7EDE;border-radius:30px;text-align:center;outline:none;margin:10px}
#stats{font-size:1.1rem;font-weight:600;color:#3A6EA5;margin:15px}
#restart{background:#FFB347;border:none;border-bottom:5px solid #C17D2E;padding:10px 30px;font-size:1.1rem;font-weight:700;border-radius:30px;cursor:pointer}''',
        'js_code': '''const words="the quick brown fox jumps over the lazy dog code is fun stars shine bright make games learn python create art explore worlds".split(" ");
let timeLeft=30,score=0,timerRunning=false,timer,current="";
function getWord(){return words[Math.floor(Math.random()*words.length)];}
function newWord(){current=getWord();document.getElementById("wordDisplay").textContent=current;document.getElementById("typeInput").value="";}
newWord();
document.getElementById("typeInput").addEventListener("input",e=>{
  if(!timerRunning){timerRunning=true;timer=setInterval(tick,1000);}
  let val=e.target.value;
  let disp=current.split("").map((ch,i)=>{
    if(i>=val.length)return `<span>${ch}</span>`;
    return val[i]===ch?`<span class="correct">${ch}</span>`:`<span class="wrong">${ch}</span>`;
  }).join("");
  document.getElementById("wordDisplay").innerHTML=disp;
  if(val===current){score++;document.getElementById("score").textContent=score;let wpm=Math.round(score/(((30-timeLeft)||1)/60));document.getElementById("wpm").textContent=wpm;newWord();}
});
function tick(){
  timeLeft--;document.getElementById("timer").textContent=timeLeft;
  if(timeLeft<=0){clearInterval(timer);document.getElementById("typeInput").disabled=true;document.getElementById("wordDisplay").innerHTML=`<b>Time\'s up! Score: ${score} words</b>`;}
}
document.getElementById("restart").addEventListener("click",()=>{clearInterval(timer);timeLeft=30;score=0;timerRunning=false;document.getElementById("timer").textContent=30;document.getElementById("score").textContent=0;document.getElementById("wpm").textContent=0;document.getElementById("typeInput").disabled=false;document.getElementById("typeInput").value="";newWord();});
'''
    },
    {
        'name': 'Colour Mixer Lab',
        'description': 'Drag RGB sliders and mix your own colours — see the hex code live!',
        'difficulty': 'beginner',
        'icon': 'fa-palette',
        'color': '#FF8B94',
        'category': 'art',
        'order': 14,
        'html_code': '''<div id="app">
  <h2>Colour Mixer Lab</h2>
  <div id="preview"></div>
  <div id="hex">#000000</div>
  <div class="slider-row"><label>Red</label><input type="range" id="r" min="0" max="255" value="100"><span id="rv">100</span></div>
  <div class="slider-row"><label>Green</label><input type="range" id="g" min="0" max="255" value="150"><span id="gv">150</span></div>
  <div class="slider-row"><label>Blue</label><input type="range" id="b" min="0" max="255" value="200"><span id="bv">200</span></div>
  <button id="copy">Copy Hex Code</button>
</div>''',
        'css_code': '''body{font-family:sans-serif;background:#f0f5ff;display:flex;justify-content:center;padding:20px}
#app{text-align:center;width:100%;max-width:400px}
#preview{width:200px;height:200px;border-radius:50%;border:8px solid white;box-shadow:0 10px 30px rgba(0,0,0,0.2);margin:20px auto;transition:background .1s}
#hex{font-size:2rem;font-weight:700;margin:10px;letter-spacing:3px}
.slider-row{display:flex;align-items:center;gap:10px;margin:10px 0;background:white;padding:10px 15px;border-radius:20px;border:3px solid #FFB347}
label{font-weight:700;min-width:80px;text-align:left}
input[type=range]{flex:1;accent-color:#9B7EDE}
span{min-width:35px;font-weight:700;color:#3A6EA5}
button{background:#FFB347;border:none;border-bottom:5px solid #C17D2E;padding:12px 30px;font-size:1rem;font-weight:700;border-radius:30px;cursor:pointer;margin-top:15px}''',
        'js_code': '''function toHex(n){return n.toString(16).padStart(2,'0');}
function update(){
  let r=document.getElementById('r').value,g=document.getElementById('g').value,b=document.getElementById('b').value;
  document.getElementById('rv').textContent=r;document.getElementById('gv').textContent=g;document.getElementById('bv').textContent=b;
  let hex='#'+toHex(+r)+toHex(+g)+toHex(+b);
  document.getElementById('preview').style.background=hex;
  document.getElementById('hex').textContent=hex;
  document.getElementById('hex').style.color=hex;
}
['r','g','b'].forEach(id=>document.getElementById(id).addEventListener('input',update));
document.getElementById('copy').addEventListener('click',()=>{navigator.clipboard.writeText(document.getElementById('hex').textContent).then(()=>alert('Copied! '+document.getElementById('hex').textContent));});
update();
'''
    },
    {
        'name': 'Beat Maker',
        'description': 'Tap a 4-track loop sequencer and drop beats with your keyboard!',
        'difficulty': 'intermediate',
        'icon': 'fa-music',
        'color': '#6c5ce7',
        'category': 'art',
        'order': 15,
        'html_code': '''<div id="app">
  <h2>Beat Maker</h2>
  <div id="grid"></div>
  <div id="controls">
    <button id="play">Play</button>
    <button id="stop">Stop</button>
    <button id="clear">Clear</button>
    <label>BPM: <input type="range" id="bpm" min="60" max="200" value="120"><span id="bpmVal">120</span></label>
  </div>
  <p id="hint">Click cells to toggle beats, then hit Play!</p>
</div>''',
        'css_code': '''body{font-family:sans-serif;background:#1e2a3e;color:white;display:flex;justify-content:center;padding:20px}
#app{text-align:center;max-width:600px;width:100%}
#grid{display:grid;grid-template-columns:80px repeat(16,1fr);gap:4px;margin:20px 0}
.lbl{display:flex;align-items:center;justify-content:flex-end;padding-right:8px;font-weight:700;font-size:.85rem;color:#FFB347}
.cell{height:32px;border-radius:6px;background:#2d3f5a;cursor:pointer;transition:.1s;border:2px solid transparent}
.cell.on{background:#FFB347;border-color:#C17D2E}
.cell.active{border-color:#9B7EDE!important}
.cell:hover{opacity:.8}
#controls{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;align-items:center;margin:10px}
button{background:#9B7EDE;color:white;border:none;border-bottom:4px solid #6B4F9E;padding:10px 20px;font-size:1rem;font-weight:700;border-radius:20px;cursor:pointer}
label{color:#FFB347;font-weight:600}input[type=range]{accent-color:#FFB347;vertical-align:middle}
#hint{color:#5D9BEC;font-size:.9rem}''',
        'js_code': '''const tracks=[{name:'Kick',freq:60,type:'sine'},{name:'Snare',freq:200,type:'sawtooth'},{name:'Hi-Hat',freq:800,type:'square'},{name:'Bass',freq:100,type:'triangle'}];
const STEPS=16;
let grid=tracks.map(()=>Array(STEPS).fill(false));
let playing=false,step=0,intervalId=null;
const ctx2=new AudioContext();
function beep(freq,type,dur=0.1){
  let o=ctx2.createOscillator(),g=ctx2.createGain();
  o.connect(g);g.connect(ctx2.destination);
  o.type=type;o.frequency.value=freq;
  g.gain.setValueAtTime(.4,ctx2.currentTime);
  g.gain.exponentialRampToValueAtTime(.001,ctx2.currentTime+dur);
  o.start();o.stop(ctx2.currentTime+dur);
}
// build grid
const gridEl=document.getElementById('grid');
tracks.forEach((t,ti)=>{
  let lbl=document.createElement('div');lbl.className='lbl';lbl.textContent=t.name;gridEl.appendChild(lbl);
  for(let s=0;s<STEPS;s++){
    let cell=document.createElement('div');cell.className='cell';
    cell.id=`c${ti}_${s}`;
    cell.addEventListener('click',()=>{grid[ti][s]=!grid[ti][s];cell.classList.toggle('on',grid[ti][s]);});
    gridEl.appendChild(cell);
  }
});
function tick(){
  // clear last
  for(let ti=0;ti<tracks.length;ti++){let prev=(step-1+STEPS)%STEPS;document.getElementById(`c${ti}_${prev}`)?.classList.remove('active');}
  // play current
  tracks.forEach((t,ti)=>{
    document.getElementById(`c${ti}_${step}`)?.classList.add('active');
    if(grid[ti][step])beep(t.freq,t.type);
  });
  step=(step+1)%STEPS;
}
document.getElementById('play').addEventListener('click',()=>{if(playing)return;playing=true;ctx2.resume();let bpm=+document.getElementById('bpm').value;intervalId=setInterval(tick,60000/bpm/4);});
document.getElementById('stop').addEventListener('click',()=>{playing=false;clearInterval(intervalId);step=0;});
document.getElementById('clear').addEventListener('click',()=>{grid=tracks.map(()=>Array(STEPS).fill(false));document.querySelectorAll('.cell').forEach(c=>{c.classList.remove('on','active');});});
document.getElementById('bpm').addEventListener('input',e=>{document.getElementById('bpmVal').textContent=e.target.value;if(playing){clearInterval(intervalId);intervalId=setInterval(tick,60000/e.target.value/4);}});
'''
    },
]

def seed_database():
    # Project templates (basic ones + game templates)
    if ProjectTemplate.query.count() == 0:
        basics = [
            ('Starter Page', 'A blank page ready for your ideas', 'beginner', 'fa-file-code', '#5D9BEC', '<h1>My Webpage</h1>\n<p>Start editing here!</p>', 'body{font-family:sans-serif;padding:20px;background:#f0f5ff}h1{color:#FFB347}', '', 0, 'general'),
            ('Colour Mixer', 'Blend colours with code', 'beginner', 'fa-palette', '#5D9BEC', '<div id="mixBox">Click to mix!</div>', '#mixBox{width:200px;height:200px;background:linear-gradient(135deg,#FFB347,#9B7EDE);margin:auto;margin-top:50px;text-align:center;line-height:200px;border-radius:20px;color:white;font-weight:bold;cursor:pointer;font-family:sans-serif}', 'document.getElementById("mixBox").addEventListener("click",function(){this.style.background=`hsl(${Math.random()*360},70%,60%)`})', 1, 'general'),
            ('Quiz Maker', 'Build your own quiz game', 'intermediate', 'fa-question-circle', '#1e5f4b', '<h2 style="font-family:sans-serif;text-align:center">Quick Quiz!</h2><p id="q" style="text-align:center;font-family:sans-serif">What is 2 + 2?</p><div style="text-align:center"><button onclick="check(this)">4</button><button onclick="check(this)">5</button></div><p id="result" style="text-align:center;font-family:sans-serif;font-size:1.5rem"></p>', 'body{background:#f0f5ff}button{margin:5px;padding:10px 20px;border-radius:10px;border:none;background:#1e5f4b;color:white;cursor:pointer;font-size:1rem}', 'function check(btn){document.getElementById("result").textContent=btn.textContent==="4"?"Correct!":"Try again!"}', 2, 'general'),
        ]
        for name, desc, diff, icon, color, html, css, js, order, cat in basics:
            db.session.add(ProjectTemplate(name=name, description=desc, difficulty=diff, icon=icon, color=color, html_code=html, css_code=css, js_code=js, order=order, category=cat))

        for g in GAME_TEMPLATES:
            db.session.add(ProjectTemplate(**g))
        db.session.commit()

    # Lessons
    if Lesson.query.count() == 0:
        for ld in LESSON_DATA:
            db.session.add(Lesson(**ld))
        db.session.commit()

    # Interactive missions replace the old one-line practice checks. Runs on
    # every start so existing databases get upgraded without a re-seed.
    from lesson_missions import apply_missions
    apply_missions(db, Lesson)

    # Testimonials
    if Testimonial.query.count() == 0:
        for t, a, e in [('I made my first game in 1 hour!','Karabo, 10','fa-gamepad'),('Nexa Pals is my favourite!','Relebohile, 11','fa-star'),('I taught my little brother!','Lesedi, 12','fa-hand-fist')]:
            db.session.add(Testimonial(text=t, author=a, emoji=e))
        db.session.commit()

    # Users
    # The demo student account is only ever seeded outside production — it should
    # never exist on a real deployment with real users.
    if not IS_PROD and not User.query.filter_by(username='test').first():
        db.session.add(User(username='test', email='demo@nexapals.local', password_hash=generate_password_hash('test123'), role='student'))
    if not User.query.filter_by(username='admin').first():
        admin_password = os.getenv('ADMIN_PASSWORD')
        if not admin_password:
            if IS_PROD:
                raise RuntimeError('ADMIN_PASSWORD must be set in production — refusing to seed an admin account with a default password.')
            admin_password = 'nexa-admin-2026'  # dev-only fallback, never used in production
        db.session.add(User(username='admin', email='admin@nexapals.local', password_hash=generate_password_hash(admin_password), role='admin'))
    db.session.commit()

    # Badges
    if Badge.query.count() == 0:
        badges = [
            ('first-lesson',  'First Step',       'Completed your first lesson',          'fa-bullseye',      '5D9BEC'),
            ('five-lessons',  'On a Roll',         'Completed 5 lessons',                  'fa-fire',          'FFB347'),
            ('all-lessons',   'Lesson Legend',     'Completed ALL 15 lessons',             'fa-crown',         'FFB347'),
            ('first-project', 'Maker',             'Saved your first project',             'fa-screwdriver-wrench', '9B7EDE'),
            ('maker',         'Prolific Builder',  'Saved 5 or more projects',             'fa-trowel-bricks', '1e5f4b'),
            ('century',       'Century Coder',     'Earned 100+ XP',                       'fa-hundred-points','5D9BEC'),
            ('power-coder',   'Power Coder',       'Earned 500+ XP',                       'fa-bolt',          '9B7EDE'),
            ('streak-3',      '3-Day Streak',      'Logged in 3 days in a row',            'fa-fire',          'e25c5c'),
            ('streak-7',      'Weekly Warrior',    'Logged in 7 days in a row',            'fa-calendar-check','FFB347'),
        ]
        for slug, name, desc, emoji, color in badges:
            db.session.add(Badge(slug=slug, name=name, description=desc, emoji=emoji, color=color))
        db.session.commit()

    # Daily challenge (today)
    if not DailyChallenge.query.filter_by(date=date.today()).first():
        db.session.add(DailyChallenge(
            date=date.today(),
            title='Rainbow Button',
            description='Create a button that changes to a random rainbow colour every time you click it. Use JavaScript to change the background colour!',
            xp_reward=25,
            html_start='<button id="rainbowBtn">Click me!</button>',
            css_start='body{display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#1e2a3e}\n#rainbowBtn{font-size:1.5rem;padding:1rem 2rem;border:none;border-radius:30px;cursor:pointer;font-weight:700;transition:0.3s}',
            js_start='document.getElementById("rainbowBtn").addEventListener("click", function() {\n  // Your code here — change this.style.background to a random colour!\n});'
        ))
        db.session.commit()

with app.app_context():
    db.create_all()
    seed_database()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== AUTH ROUTES ====================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        ip = request.remote_addr or 'unknown'
        if _is_action_rate_limited('signup', ip, SIGNUP_MAX_PER_WINDOW, SIGNUP_WINDOW_SECONDS):
            flash('Too many accounts created from this connection recently. Please try again later.')
            return redirect(url_for('signup'))
        username = sanitize(request.form.get('username',''), 30).strip()
        email    = sanitize(request.form.get('email',''), 120).strip().lower()
        password = request.form.get('password','')
        is_minor = bool(request.form.get('is_minor'))
        parent_email = sanitize(request.form.get('parent_email',''), 120).strip().lower()
        terms_accepted = bool(request.form.get('terms_accepted'))
        if len(username) < 3: flash('Username must be at least 3 characters'); return redirect(url_for('signup'))
        if not username.replace('_','').replace('-','').isalnum(): flash('Username can only have letters, numbers, - and _'); return redirect(url_for('signup'))
        if '@' not in email or '.' not in email.split('@')[-1]: flash('Please enter a valid email'); return redirect(url_for('signup'))
        if len(password) < 6: flash('Password must be at least 6 characters'); return redirect(url_for('signup'))
        if not terms_accepted:
            flash('You need to agree to the Terms of Service and Privacy Policy to sign up.')
            return redirect(url_for('signup'))
        if is_minor and ('@' not in parent_email or '.' not in parent_email.split('@')[-1]):
            flash('Please enter a valid parent or guardian email — we need it to let them know about this account.')
            return redirect(url_for('signup'))
        if User.query.filter_by(username=username).first(): flash('Username taken'); return redirect(url_for('signup'))
        if User.query.filter_by(email=email).first(): flash('Email already registered'); return redirect(url_for('signup'))

        now = datetime.utcnow()
        new_user = User(username=username, email=email, password_hash=generate_password_hash(password),
                         is_minor=is_minor, terms_accepted_at=now, consent_recorded_at=now)
        if is_minor:
            new_user.parent_email = parent_email
            new_user.parent_verified = False
            new_user.parent_verify_token = secrets.token_urlsafe(32)
        db.session.add(new_user)
        db.session.commit()
        _log_event('signup', user_id=new_user.id, meta={'is_minor': is_minor})

        if is_minor:
            verify_url = url_for('verify_parent', token=new_user.parent_verify_token, _external=True)
            sent, _err_msg = _send_parent_verification_email(parent_email, username, verify_url)
            if sent:
                flash('Account created! We\'ve emailed your parent or guardian to confirm the account — please log in.')
            else:
                flash('Account created! Please log in. (We couldn\'t email your parent/guardian automatically — an admin will follow up.)')
        else:
            flash('Account created! Please log in.')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/verify-parent/<token>')
def verify_parent(token):
    user = User.query.filter_by(parent_verify_token=token).first()
    if not user:
        flash('This verification link is invalid or has already been used.')
        return redirect(url_for('index'))
    user.parent_verified = True
    user.parent_verify_token = None
    if not user.parent_manage_token:
        user.parent_manage_token = secrets.token_urlsafe(32)
    db.session.commit()
    _log_event('parent_verified', user_id=user.id)
    flash(f'Thank you! {user.username}\'s account is now confirmed.')
    return redirect(url_for('parent_manage', token=user.parent_manage_token))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('website', ''):  # honeypot — bots fill hidden fields
            return redirect(url_for('index'))
        ip = request.remote_addr or 'unknown'
        if _is_rate_limited(ip): flash('Too many failed attempts. Please wait 5 minutes.'); return render_template('login.html')
        username = sanitize(request.form.get('username',''), 80).strip()
        password = request.form.get('password','')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            _award_badges(user)
            _log_event('login', user_id=user.id)
            flash(f'Welcome back, {user.username}!')
            return redirect(url_for('index'))
        _record_failed_login(ip)
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ── Badge awarding helper ─────────────────────────────────────────────────
def _award_badges(user):
    already = {ub.badge.slug for ub in UserBadge.query.filter_by(user_id=user.id).all()}
    earned  = []
    def _give(slug):
        if slug in already: return
        b = Badge.query.filter_by(slug=slug).first()
        if b:
            db.session.add(UserBadge(user_id=user.id, badge_id=b.id))
            earned.append(b)
    completed = LessonProgress.query.filter_by(user_id=user.id, completed=True).count()
    projects  = UserProject.query.filter_by(user_id=user.id).count()
    if completed >= 1:          _give('first-lesson')
    if completed >= 5:          _give('five-lessons')
    if completed >= 15:         _give('all-lessons')
    if projects >= 1:           _give('first-project')
    if projects >= 5:           _give('maker')
    if user.xp >= 100:          _give('century')
    if user.xp >= 500:          _give('power-coder')
    if user.streak_days >= 3:   _give('streak-3')
    if user.streak_days >= 7:   _give('streak-7')
    if earned:
        db.session.commit()
        for b in earned:
            _log_event('badge_earned', user_id=user.id, meta={'badge': b.slug})
    return earned

# ==================== PAGE ROUTES ====================
@app.route('/')
def index():
    templates    = ProjectTemplate.query.filter_by(category='general').order_by(ProjectTemplate.order).limit(6).all()
    testimonials = Testimonial.query.filter_by(is_approved=True).all()
    daily        = DailyChallenge.query.filter_by(date=date.today()).first()
    top_users    = User.query.filter(User.role != 'admin').order_by(User.xp.desc()).limit(5).all()
    return render_template('index.html', templates=templates, testimonials=testimonials,
                           daily=daily, top_users=top_users)

@app.route('/leaderboard')
def leaderboard():
    users = User.query.filter(User.role != 'admin').order_by(User.xp.desc()).limit(50).all()

    # Lazily roll every non-admin user's week over before computing this
    # week's league standings, so an inactive student's league reflects last
    # week's result rather than showing stale data from weeks ago.
    all_users = User.query.filter(User.role != 'admin').all()
    changed = False
    for u in all_users:
        before_league, before_week = u.league, u.week_start
        u._sync_week()
        if u.week_start != before_week:
            changed = True
            if u.league != before_league:
                idx_before = User.LEAGUES.index(before_league) if before_league in User.LEAGUES else 0
                idx_after = User.LEAGUES.index(u.league)
                _log_event('league_promotion' if idx_after > idx_before else 'league_demotion',
                           user_id=u.id, meta={'from': before_league, 'to': u.league})
    if changed:
        db.session.commit()

    my_league = current_user.league if current_user.is_authenticated else 'bronze'
    league_users = (User.query.filter(User.role != 'admin', User.league == my_league)
                    .order_by(User.weekly_xp.desc()).limit(30).all())
    promote_xp = (current_user.league_promote_xp if current_user.is_authenticated
                  else User.LEAGUE_PROMOTE_THRESHOLDS['bronze'])
    return render_template('leaderboard.html', users=users, league_users=league_users,
                            my_league=my_league, promote_xp=promote_xp,
                            leagues=User.LEAGUES)

@app.route('/profile')
@login_required
def profile():
    badges   = UserBadge.query.filter_by(user_id=current_user.id).order_by(UserBadge.earned_at.desc()).all()
    projects = UserProject.query.filter_by(user_id=current_user.id).order_by(UserProject.updated_at.desc()).all()
    progress = LessonProgress.query.filter_by(user_id=current_user.id, completed=True).all()
    return render_template('profile.html', badges=badges, projects=projects, progress=progress)

# ==================== TEACHER / CLASSROOM ====================
def _generate_join_code():
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # no 0/O/1/I — easier to read aloud/type
    for _ in range(20):
        code = ''.join(secrets.choice(alphabet) for _ in range(6))
        if not Classroom.query.filter_by(join_code=code).first():
            return code
    raise RuntimeError('Could not generate a unique classroom join code')

@app.route('/teacher')
@login_required
def teacher_dashboard():
    classroom = Classroom.query.filter_by(teacher_id=current_user.id).first()
    students = []
    summaries, stuck_rows = {}, []
    if classroom:
        students = (User.query.filter_by(classroom_id=classroom.id)
                    .order_by(User.xp.desc()).all())
        for s in students:
            s.lessons_completed = LessonProgress.query.filter_by(user_id=s.id, completed=True).count()
        ids = [s.id for s in students]
        step_ev = _events(ids, _STEP_EVENTS)
        mis_ev = _events(ids, ('mission_complete',))
        for s in students:
            summaries[s.id] = la.learner_summary([e for e in step_ev if e['user_id'] == s.id],
                                                 [e for e in mis_ev if e['user_id'] == s.id])
        lesson_titles = {l.id: l.title for l in Lesson.query.all()}
        for f in la.stubborn_steps(step_ev, min_learners=3):
            f['lesson'] = lesson_titles.get(f['lesson_id'], 'Lesson ' + str(f['lesson_id']))
            f['skill_label'] = lm.SKILL_LABELS.get(f['skill'], f['skill'])
            stuck_rows.append(f)
    return render_template('teacher.html', classroom=classroom, students=students, summaries=summaries,
                           stuck_rows=stuck_rows, skill_labels=lm.SKILL_LABELS)

@app.route('/teacher/create-classroom', methods=['POST'])
@login_required
def create_classroom():
    if Classroom.query.filter_by(teacher_id=current_user.id).first():
        flash('You already have a classroom.')
        return redirect(url_for('teacher_dashboard'))
    name = sanitize(request.form.get('name', ''), 100).strip() or f"{current_user.username}'s Classroom"
    classroom = Classroom(name=name, teacher_id=current_user.id, join_code=_generate_join_code())
    if current_user.role == 'student':
        current_user.role = 'teacher'
    db.session.add(classroom)
    db.session.commit()
    _log_event('classroom_created', user_id=current_user.id, meta={'classroom_id': classroom.id})
    flash(f'Classroom "{classroom.name}" created! Share the join code {classroom.join_code} with your students.')
    return redirect(url_for('teacher_dashboard'))

@app.route('/join-classroom', methods=['GET', 'POST'])
@login_required
def join_classroom():
    if request.method == 'POST':
        code = sanitize(request.form.get('join_code', ''), 10).strip().upper()
        classroom = Classroom.query.filter_by(join_code=code).first()
        if not classroom:
            flash('That join code doesn\'t match a classroom — double-check it with your teacher.')
            return redirect(url_for('join_classroom'))
        current_user.classroom_id = classroom.id
        db.session.commit()
        _log_event('classroom_joined', user_id=current_user.id, meta={'classroom_id': classroom.id})
        flash(f'You\'ve joined "{classroom.name}"!')
        return redirect(url_for('profile'))
    return render_template('join_classroom.html')

@app.route('/teacher/remove-student/<int:user_id>', methods=['POST'])
@login_required
def remove_student(user_id):
    classroom = Classroom.query.filter_by(teacher_id=current_user.id).first()
    student = User.query.get(user_id)
    if classroom and student and student.classroom_id == classroom.id:
        student.classroom_id = None
        db.session.commit()
        flash(f'{student.username} removed from your classroom.')
    return redirect(url_for('teacher_dashboard'))

@app.route('/profile/set-avatar', methods=['POST'])
@login_required
def set_avatar():
    allowed = ['fa-egg','fa-dove','fa-crow','fa-kiwi-bird','fa-rocket','fa-robot',
               'fa-hat-wizard','fa-cat','fa-dragon','fa-star','fa-gem','fa-bolt']
    avatar = request.form.get('avatar', 'fa-egg')
    if avatar in allowed:
        current_user.avatar = avatar
        db.session.commit()
    return redirect(url_for('profile'))

# ── LEARN ────────────────────────────────────────────────────────────────────
@app.route('/learn')
def learn():
    tracks = {'html': [], 'css': [], 'javascript': []}
    progress_map = {}
    if current_user.is_authenticated:
        progs = LessonProgress.query.filter_by(user_id=current_user.id).all()
        progress_map = {p.lesson_id: p for p in progs}
    for track in tracks:
        lessons = Lesson.query.filter_by(track=track).order_by(Lesson.order).all()
        tracks[track] = [(l, progress_map.get(l.id)) for l in lessons]
    total_lessons = sum(len(v) for v in tracks.values())
    completed = sum(1 for p in progress_map.values() if p.completed)
    return render_template('learn.html', tracks=tracks, completed=completed, total_lessons=total_lessons)

@app.route('/learn/<track>/<int:lesson_id>')
@login_required
def lesson(track, lesson_id):
    lesson_obj = Lesson.query.filter_by(id=lesson_id, track=track).first_or_404()
    progress = LessonProgress.query.filter_by(user_id=current_user.id, lesson_id=lesson_id).first()
    all_track_lessons = Lesson.query.filter_by(track=track).order_by(Lesson.order).all()
    idx = next((i for i,l in enumerate(all_track_lessons) if l.id == lesson_id), 0)
    prev_lesson = all_track_lessons[idx-1] if idx > 0 else None
    next_lesson = all_track_lessons[idx+1] if idx < len(all_track_lessons)-1 else None
    quiz = json.loads(lesson_obj.quiz_json) if lesson_obj.quiz_json else []
    practice = json.loads(lesson_obj.practice_json) if lesson_obj.practice_json else None
    return render_template('lesson.html', lesson=lesson_obj, progress=progress,
                           prev_lesson=prev_lesson, next_lesson=next_lesson,
                           track=track, quiz=quiz, practice=practice)

def _mission_done(user_id, lesson_id):
    """True if this learner has finished the lesson's mission (logged by the
    mission engine through /api/mission/complete)."""
    return AnalyticsEvent.query.filter(
        AnalyticsEvent.event_type == 'mission_complete',
        AnalyticsEvent.user_id == user_id,
        AnalyticsEvent.meta.like('%"lesson_id": ' + str(int(lesson_id)) + ',%')
    ).first() is not None

@app.route('/api/mission/complete', methods=['POST'])
@login_required
def complete_mission():
    data = request.get_json(silent=True) or {}
    try:
        lesson_id = int(data.get('lesson_id'))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Bad lesson'}), 400
    if not Lesson.query.get(lesson_id):
        return jsonify({'success': False, 'message': 'Lesson not found'}), 404
    def n(k):
        try: return max(0, min(int(data.get(k, 0)), 999))
        except (TypeError, ValueError): return 0
    _log_event('mission_complete', user_id=current_user.id,
               meta={'lesson_id': lesson_id, 'attempts': n('attempts'), 'hints': n('hints'), 'assisted': n('assisted')})
    return jsonify({'success': True})

# ── Learning analytics: skills, warm-up, practice, capstones ─────────────────
import learning_analytics as la
import lesson_missions as lm

_STEP_EVENTS = ('mission_step', 'mission_stuck')

def _events(user_ids, types, since=None):
    """AnalyticsEvent rows as plain dicts (meta parsed) for learning_analytics."""
    if not user_ids:
        return []
    q = AnalyticsEvent.query.filter(AnalyticsEvent.event_type.in_(types), AnalyticsEvent.user_id.in_(user_ids))
    if since:
        q = q.filter(AnalyticsEvent.created_at >= since)
    out = []
    for e in q.all():
        try:
            meta = json.loads(e.meta) if e.meta else {}
        except ValueError:
            meta = {}
        out.append({'event_type': e.event_type, 'user_id': e.user_id, 'created_at': e.created_at, 'meta': meta})
    return out

@app.route('/api/mission/step', methods=['POST'])
@login_required
def mission_step():
    d = request.get_json(silent=True) or {}
    def n(k, hi=99):
        try: return max(0, min(int(d.get(k, 0)), hi))
        except (TypeError, ValueError): return 0
    skill = d.get('skill') if d.get('skill') in lm.SKILL_LABELS else ''
    lesson_id = d.get('lesson_id')
    lesson_id = int(lesson_id) if isinstance(lesson_id, int) or (isinstance(lesson_id, str) and lesson_id.isdigit()) else None
    stuck = bool(d.get('stuck'))
    _log_event('mission_stuck' if stuck else 'mission_step', user_id=current_user.id,
               meta={'lesson_id': lesson_id, 'step': n('step', 20), 'skill': skill, 'checks': n('checks'),
                     'hints': n('hints'), 'assisted': n('assisted'), 'stuck': stuck, 'done': not stuck})
    return jsonify({'success': True})

@app.route('/api/learning/done', methods=['POST'])
@login_required
def learning_done():
    """Logs warm-up and capstone completions."""
    d = request.get_json(silent=True) or {}
    kind = d.get('kind')
    if kind == 'warmup':
        _log_event('warmup_done', user_id=current_user.id,
                   meta={'track': str(d.get('track', ''))[:20], 'order': int(d.get('order', 0) or 0)})
    elif kind == 'precode':
        _log_event('precode_done', user_id=current_user.id)
    elif kind == 'intro':
        _log_event('intro_done', user_id=current_user.id)
    elif kind == 'capstone' and d.get('track') in lm.CAPSTONES:
        _log_event('capstone_complete', user_id=current_user.id, meta={'track': d['track']})
    else:
        return jsonify({'success': False}), 400
    return jsonify({'success': True})

def _mission_page(mission, heading, sub, mode, accent='#9B7EDE', extra=None):
    return render_template('mission_page.html', mission=mission, heading=heading, sub=sub, mode=mode,
                           accent=accent, extra=extra or {})

TRACK_ACCENT = {'html': '#2f6fc0', 'css': '#a35f10', 'javascript': '#6c4bb8'}

@app.route('/start')
def start_here():
    """Public "Before you code" experience for kids who know nothing yet: tap-only robot levels, no typing."""
    return _mission_page(lm.PRECODE, 'New to coding? Start here',
                         'No typing and no experience needed. You will tell a robot what to do, and that is real programming.', 'precode', '#6c4bb8')

@app.route('/start/code')
def start_code():
    """Second step: the first lines of real code."""
    return _mission_page(lm.INTRO, 'Your first real code',
                         'Five short steps. You will change, fix and write real code. Hints are always there.', 'intro', '#6c4bb8')

@app.route('/my-skills')
@login_required
def my_skills():
    strengths = la.skill_strengths(_events([current_user.id], _STEP_EVENTS))
    rows = []
    for key in lm.SKILL_LABELS:
        if key.startswith('capstone-'):
            continue
        s = strengths.get(key)
        rows.append({'key': key, 'label': lm.SKILL_LABELS[key], 'strength': s['strength'] if s else None,
                     'band': la.skill_band(s['strength']) if s else 'new', 'steps': s['steps'] if s else 0})
    summary = la.learner_summary(_events([current_user.id], _STEP_EVENTS), _events([current_user.id], ('mission_complete',)))
    return render_template('skills.html', rows=rows, summary=summary, labels=lm.SKILL_LABELS,
                           weakest=la.weakest_skills(strengths))

@app.route('/practice/<skill>')
@login_required
def practice_skill(skill):
    if skill not in lm.SKILL_LABELS or skill.startswith('capstone-'):
        abort(404)
    track = (lm.LESSON_BY_SKILL.get(skill) or ('html',))[0]
    return _mission_page(lm.practice_mission(skill), 'Practise: ' + lm.SKILL_LABELS[skill],
                         'Short extra steps on one skill. Each one makes it stronger.', 'practice', TRACK_ACCENT.get(track, '#6c4bb8'))

@app.route('/warmup')
@login_required
def warmup():
    done = (db.session.query(LessonProgress, Lesson).join(Lesson, Lesson.id == LessonProgress.lesson_id)
            .filter(LessonProgress.user_id == current_user.id, LessonProgress.completed == True).all())  # noqa: E712
    completed = [{'track': l.track, 'order': l.order, 'completed_at': p.completed_at, 'title': l.title} for p, l in done]
    reviews = {}
    for e in _events([current_user.id], ('warmup_done',)):
        k = (e['meta'].get('track'), e['meta'].get('order'))
        if k not in reviews or e['created_at'] > reviews[k]:
            reviews[k] = e['created_at']
    pick = la.pick_warmup(completed, reviews)
    if not pick or pick not in lm.MISSIONS:
        return _mission_page(None, 'Warm-up', 'Nothing is due for review right now. Finish a lesson and come back in two days.', 'warmup')
    steps = [s for s in lm.build_mission(pick)['steps'] if s['type'] in ('predict', 'order')] or lm.build_mission(pick)['steps'][:1]
    title = next((c['title'] for c in completed if (c['track'], c['order']) == pick), 'an earlier lesson')
    mission = {'title': 'Warm-up: ' + title, 'success_msg': 'Warm-up done. Remembering it again makes it stick.',
               'skill': lm.SKILL_BY_LESSON.get(pick), 'steps': steps[:1]}
    return _mission_page(mission, 'Warm-up', 'One quick question from a lesson you finished a few days ago.', 'warmup',
                         TRACK_ACCENT.get(pick[0], '#6c4bb8'), {'track': pick[0], 'order': pick[1]})

@app.route('/capstone/<track>')
@login_required
def capstone(track):
    if track not in lm.CAPSTONES:
        abort(404)
    lessons = Lesson.query.filter_by(track=track).all()
    done_ids = {p.lesson_id for p in LessonProgress.query.filter_by(user_id=current_user.id, completed=True).all()}
    unlocked = la.capstone_unlocked(track, [l.order for l in lessons if l.id in done_ids], [l.order for l in lessons])
    if not unlocked:
        return _mission_page(None, 'Capstone locked', 'Finish every ' + track.upper() + ' lesson to unlock the capstone project.', 'capstone')
    return _mission_page(lm.CAPSTONES[track], lm.CAPSTONES[track]['title'], 'Build it yourself. No worked example, and the hints wait until you have tried.',
                         'capstone', TRACK_ACCENT.get(track, '#6c4bb8'), {'track': track})

@app.route('/api/lesson/complete', methods=['POST'])
@login_required
def complete_lesson():
    data = request.get_json(silent=True) or {}
    lesson_id = data.get('lesson_id')
    answers = data.get('answers', [])
    lesson_obj = Lesson.query.get(lesson_id)
    if not lesson_obj:
        return jsonify({'success': False, 'message': 'Lesson not found'}), 404
    # A lesson with a mission must have its mission finished before the quiz counts.
    existing = LessonProgress.query.filter_by(user_id=current_user.id, lesson_id=lesson_id).first()
    if lesson_obj.practice_json and '"steps"' in lesson_obj.practice_json \
            and not (existing and existing.completed) and not _mission_done(current_user.id, lesson_id):
        return jsonify({'success': False, 'needs_mission': True,
                        'message': 'Finish the mission first, then take the quiz.'}), 403
    quiz = json.loads(lesson_obj.quiz_json) if lesson_obj.quiz_json else []
    correct = sum(1 for i, q in enumerate(quiz) if i < len(answers) and answers[i] == q['answer'])
    score = round((correct / len(quiz)) * 100) if quiz else 100
    passed = score >= 70
    prog = LessonProgress.query.filter_by(user_id=current_user.id, lesson_id=lesson_id).first()
    xp_earned = 0
    already_completed = bool(prog and prog.completed)
    level_before = current_user.level['num']
    if not prog:
        prog = LessonProgress(user_id=current_user.id, lesson_id=lesson_id)
        db.session.add(prog)
    if not prog.completed and passed:
        prog.completed = True
        prog.completed_at = datetime.utcnow()
        prog.quiz_passed = True
        prog.score = score
        current_user.add_xp(lesson_obj.xp_reward)
        xp_earned = lesson_obj.xp_reward
        current_user.update_streak()
    elif passed and score > (prog.score or 0):
        prog.score = score
    db.session.commit()
    new_badges = _award_badges(current_user) if passed and not already_completed else []
    if passed:
        _log_event('lesson_complete', user_id=current_user.id,
                    meta={'lesson_id': lesson_id, 'score': score, 'first_time': not already_completed})
    badge_data = [{'name': b.name, 'emoji': b.emoji} for b in new_badges]
    level_after = current_user.level
    leveled_up = level_after['num'] > level_before
    return jsonify({'success': True, 'score': score, 'correct': correct, 'total': len(quiz),
                    'passed': passed, 'xp_earned': xp_earned, 'new_badges': badge_data,
                    'leveled_up': leveled_up, 'new_level_name': level_after['name'] if leveled_up else None})

# ── GAMES ────────────────────────────────────────────────────────────────────
@app.route('/games')
def games():
    arcade = ProjectTemplate.query.filter_by(category='game').order_by(ProjectTemplate.order).all()
    art    = ProjectTemplate.query.filter_by(category='art').order_by(ProjectTemplate.order).all()
    return render_template('games.html', arcade=arcade, art=art)

@app.route('/games/play/<int:template_id>')
def play_game(template_id):
    template = ProjectTemplate.query.get_or_404(template_id)
    return render_template('arcade.html', template=template)

# ── EXISTING PAGES ───────────────────────────────────────────────────────────
@app.route('/play')
@login_required
def play():
    user_projects = UserProject.query.filter_by(user_id=current_user.id).order_by(UserProject.updated_at.desc()).all()
    return render_template('play.html', user_projects=user_projects, active_project=None)

@app.route('/play/<int:project_id>')
@login_required
def play_project(project_id):
    project = UserProject.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash("That project doesn't belong to you")
        return redirect(url_for('play'))
    user_projects = UserProject.query.filter_by(user_id=current_user.id).order_by(UserProject.updated_at.desc()).all()
    return render_template('play.html', user_projects=user_projects, active_project=project)

@app.route('/my-projects')
@login_required
def my_projects():
    user_projects = UserProject.query.filter_by(user_id=current_user.id).order_by(UserProject.updated_at.desc()).all()
    return render_template('my_projects.html', user_projects=user_projects)

@app.route('/create')
def create():
    templates = ProjectTemplate.query.order_by(ProjectTemplate.order).all()
    return render_template('create.html', templates=templates)

@app.route('/buddies')
def buddies():
    testimonials = Testimonial.query.filter_by(is_approved=True).all()
    return render_template('buddies.html', testimonials=testimonials)

@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        flash('Admin access only'); return redirect(url_for('index'))
    users = User.query.all()
    projects = UserProject.query.all()
    templates = ProjectTemplate.query.all()
    lessons = Lesson.query.order_by(Lesson.track, Lesson.order).all()

    from datetime import timedelta
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    today_start = datetime.combine(date.today(), datetime.min.time())
    non_admin = User.query.filter(User.role != 'admin')

    eligible_for_d7 = non_admin.filter(User.created_at <= week_ago).all()
    d7_retained = sum(1 for u in eligible_for_d7
                       if u.last_active and (u.last_active - u.created_at.date()).days >= 7)
    d7_pct = round(100 * d7_retained / len(eligible_for_d7)) if eligible_for_d7 else None

    event_counts = dict(
        db.session.query(AnalyticsEvent.event_type, db.func.count(AnalyticsEvent.id))
        .filter(AnalyticsEvent.created_at >= week_ago)
        .group_by(AnalyticsEvent.event_type).all()
    )
    analytics = {
        'signups_today': non_admin.filter(User.created_at >= today_start).count(),
        'signups_week':  non_admin.filter(User.created_at >= week_ago).count(),
        'total_users':   non_admin.count(),
        'active_today':  non_admin.filter(User.last_active == date.today()).count(),
        'd7_retention_pct': d7_pct,
        'd7_cohort_size': len(eligible_for_d7),
        'events_this_week': event_counts,
    }
    recent_errors = ErrorLog.query.order_by(ErrorLog.created_at.desc()).limit(15).all()

    return render_template('admin.html', users=users, projects=projects, templates=templates,
                           lessons=lessons, analytics=analytics, recent_errors=recent_errors)

def _require_admin():
    if current_user.role != 'admin':
        flash('Admin access only'); return False
    return True

@app.route('/admin/lessons/new', methods=['GET', 'POST'])
@login_required
def admin_lesson_new():
    if not _require_admin(): return redirect(url_for('index'))
    if request.method == 'POST':
        quiz_raw = request.form.get('quiz_json', '').strip() or '[]'
        practice_raw = request.form.get('practice_json', '').strip()
        try:
            json.loads(quiz_raw)
            if practice_raw:
                json.loads(practice_raw)
        except json.JSONDecodeError as e:
            flash(f'That JSON is invalid: {e}'); return redirect(url_for('admin_lesson_new'))
        lesson = Lesson(
            track=request.form.get('track', 'html'),
            order=int(request.form.get('order') or 0),
            title=sanitize(request.form.get('title', ''), 150),
            content=request.form.get('content', ''),  # trusted admin-authored HTML, rendered with |safe
            quiz_json=quiz_raw,
            practice_json=practice_raw or None,
            xp_reward=int(request.form.get('xp_reward') or 10),
        )
        db.session.add(lesson)
        db.session.commit()
        flash(f'Lesson "{lesson.title}" created.')
        return redirect(url_for('admin'))
    return render_template('admin_lesson_form.html', lesson=None)

@app.route('/admin/lessons/<int:lesson_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_lesson_edit(lesson_id):
    if not _require_admin(): return redirect(url_for('index'))
    lesson = Lesson.query.get_or_404(lesson_id)
    if request.method == 'POST':
        quiz_raw = request.form.get('quiz_json', '').strip() or '[]'
        practice_raw = request.form.get('practice_json', '').strip()
        try:
            json.loads(quiz_raw)
            if practice_raw:
                json.loads(practice_raw)
        except json.JSONDecodeError as e:
            flash(f'That JSON is invalid: {e}'); return redirect(url_for('admin_lesson_edit', lesson_id=lesson_id))
        lesson.track = request.form.get('track', lesson.track)
        lesson.order = int(request.form.get('order') or lesson.order)
        lesson.title = sanitize(request.form.get('title', ''), 150)
        lesson.content = request.form.get('content', '')
        lesson.quiz_json = quiz_raw
        lesson.practice_json = practice_raw or None
        lesson.xp_reward = int(request.form.get('xp_reward') or lesson.xp_reward)
        db.session.commit()
        flash(f'Lesson "{lesson.title}" updated.')
        return redirect(url_for('admin'))
    return render_template('admin_lesson_form.html', lesson=lesson)

@app.route('/admin/lessons/<int:lesson_id>/delete', methods=['POST'])
@login_required
def admin_lesson_delete(lesson_id):
    if not _require_admin(): return redirect(url_for('index'))
    lesson = Lesson.query.get_or_404(lesson_id)
    LessonProgress.query.filter_by(lesson_id=lesson_id).delete()
    title = lesson.title
    db.session.delete(lesson)
    db.session.commit()
    flash(f'Lesson "{title}" deleted.')
    return redirect(url_for('admin'))

# ==================== ERROR HANDLERS ====================
@app.errorhandler(404)
def not_found(e): return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    db.session.rollback()
    try:
        db.session.add(ErrorLog(message=str(e), path=request.path))
        db.session.commit()
    except Exception:
        db.session.rollback()
    return render_template('500.html'), 500

# ==================== API ENDPOINTS ====================
@app.route('/api/save_project', methods=['POST'])
@login_required
def save_project():
    data = request.get_json(silent=True) or {}
    project_id = data.get('project_id')
    title = (data.get('title') or 'My Project').strip()[:100] or 'My Project'
    html_code = data.get('html_code', '')
    css_code  = data.get('css_code', '')
    js_code   = data.get('js_code', '')

    SHIP_BONUS_XP = 5
    ship_xp_earned = 0
    today = date.today()
    if current_user.last_ship_bonus_date != today:
        current_user.add_xp(SHIP_BONUS_XP)
        current_user.last_ship_bonus_date = today
        ship_xp_earned = SHIP_BONUS_XP
        _log_event('ship_bonus', user_id=current_user.id)
    current_user.update_streak()

    if project_id:
        project = UserProject.query.get(project_id)
        if not project or project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Project not found'}), 404
        project.title = title; project.html_code = html_code; project.css_code = css_code
        project.js_code = js_code; project.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Updated', 'project_id': project.id, 'xp_earned': ship_xp_earned})
    new = UserProject(user_id=current_user.id, title=title, html_code=html_code, css_code=css_code, js_code=js_code)
    db.session.add(new); db.session.commit()
    return jsonify({'success': True, 'message': 'Saved', 'project_id': new.id, 'xp_earned': ship_xp_earned})

@app.route('/api/load_project/<int:project_id>')
@login_required
def load_project(project_id):
    project = UserProject.query.get(project_id)
    if project and project.user_id == current_user.id:
        return jsonify({'success': True, 'project_id': project.id, 'title': project.title, 'html_code': project.html_code, 'css_code': project.css_code, 'js_code': project.js_code})
    return jsonify({'success': False, 'message': 'Project not found'}), 404

@app.route('/api/delete_project/<int:project_id>', methods=['POST'])
@login_required
def delete_project(project_id):
    project = UserProject.query.get(project_id)
    if not project or project.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Project not found'}), 404
    db.session.delete(project); db.session.commit()
    return jsonify({'success': True, 'message': 'Project deleted'})

@app.route('/api/load_template/<int:template_id>')
def load_template(template_id):
    t = ProjectTemplate.query.get(template_id)
    if t: return jsonify({'success': True, 'name': t.name, 'html_code': t.html_code, 'css_code': t.css_code, 'js_code': t.js_code})
    return jsonify({'success': False, 'message': 'Template not found'}), 404

@app.route('/api/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if current_user.role != 'admin': return jsonify({'success': False, 'message': 'Admin access only'}), 403
    if user_id == current_user.id: return jsonify({'success': False, 'message': "Can't delete yourself here"}), 400
    user = User.query.get(user_id)
    if not user: return jsonify({'success': False, 'message': 'User not found'}), 404
    UserProject.query.filter_by(user_id=user.id).delete()
    db.session.delete(user); db.session.commit()
    return jsonify({'success': True, 'message': f'User {user.username} deleted'})

@app.route('/api/admin/delete_project/<int:project_id>', methods=['POST'])
@login_required
def admin_delete_project(project_id):
    if current_user.role != 'admin': return jsonify({'success': False, 'message': 'Admin access only'}), 403
    project = UserProject.query.get(project_id)
    if not project: return jsonify({'success': False, 'message': 'Project not found'}), 404
    db.session.delete(project); db.session.commit()
    return jsonify({'success': True, 'message': 'Project deleted'})

@app.route('/healthz')
def health_check(): return jsonify({'status': 'ok'})

# ==================== ABOUT & CONTACT ====================
CONTACT_EMAIL = os.getenv('CONTACT_EMAIL') or 'info@nexapals.co.za'

def _send_contact_email(sender_name, sender_email, subject, message):
    """Send contact form submission to info@nexapals.co.za via Gmail SMTP."""
    smtp_user = os.getenv('SMTP_USER', '')
    smtp_pass = os.getenv('SMTP_PASS', '')
    if not smtp_user or not smtp_pass:
        return False, 'Email not configured'
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'[Nexa Pals Contact] {subject}'
        msg['From']    = smtp_user
        msg['To']      = CONTACT_EMAIL
        msg['Reply-To'] = f'{sender_name} <{sender_email}>'
        body = (
            f'Name: {sender_name}\n'
            f'Email: {sender_email}\n'
            f'Subject: {subject}\n\n'
            f'Message:\n{message}\n\n'
            f'---\nSent via nexapals.co.za contact form'
        )
        msg.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, CONTACT_EMAIL, msg.as_string())
        return True, 'Sent'
    except Exception as e:
        return False, str(e)

def _send_parent_verification_email(parent_email, child_username, verify_url):
    """Sent when a student signs up marked as under 18. Lets the parent/
    guardian confirm the account with one click. If SMTP isn't configured
    (e.g. local dev), this fails quietly and the account is flagged for
    manual admin review instead — see the parent_verified column."""
    smtp_user = os.getenv('SMTP_USER', '')
    smtp_pass = os.getenv('SMTP_PASS', '')
    if not smtp_user or not smtp_pass:
        return False, 'Email not configured'
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Please confirm your child\'s Nexa Pals account'
        msg['From']    = smtp_user
        msg['To']      = parent_email
        body = (
            f'Hi,\n\n'
            f'{child_username} just signed up for a free Nexa Pals account (a coding site for kids) '
            f'and told us you are their parent or guardian.\n\n'
            f'To confirm you are aware of and approve this account, please click the link below:\n'
            f'{verify_url}\n\n'
            f'If you did not expect this, you can ignore this email or contact us at {CONTACT_EMAIL} '
            f'and we will remove the account.\n\n'
            f'You can read our Privacy Policy at any time to see exactly what information we collect '
            f'and how to request it be deleted.\n\n'
            f'— Nexa Pals'
        )
        msg.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, parent_email, msg.as_string())
        return True, 'Sent'
    except Exception as e:
        return False, str(e)

def _send_parent_digest_email(parent_email, digest):
    """Sends one weekly progress digest to an opted-in parent. Reuses the
    same SMTP pattern as the other two email helpers — fails quietly (and
    tells the caller why) if SMTP isn't configured."""
    smtp_user = os.getenv('SMTP_USER', '')
    smtp_pass = os.getenv('SMTP_PASS', '')
    if not smtp_user or not smtp_pass:
        return False, 'Email not configured'
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"{digest['username']}'s Nexa Pals week"
        msg['From']    = smtp_user
        msg['To']      = parent_email
        lines = [
            f"Hi,\n",
            f"Here's what {digest['username']} did on Nexa Pals this week:\n",
            f"  - Lessons completed: {digest['lessons_completed']}",
            f"  - XP earned: {digest['xp_earned']}",
            f"  - Current level: {digest['level_name']}",
            f"  - Current league: {digest['league'].title()}",
            f"  - Ship Streak: {digest['streak_days']} day(s)",
        ]
        if digest['badges_earned']:
            lines.append(f"  - New badges: {', '.join(digest['badges_earned'])}")
        lines.append(
            f"\nYou're getting this because you opted in to weekly updates. "
            f"You can turn this off any time: {digest['manage_url']}\n"
        )
        lines.append('— Nexa Pals')
        msg.attach(MIMEText('\n'.join(lines), 'plain'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, parent_email, msg.as_string())
        return True, 'Sent'
    except Exception as e:
        return False, str(e)

def _build_parent_digest(user):
    """Builds a weekly progress summary for one student. Returns None if the
    student had no activity this week — an opted-in parent still shouldn't
    get an empty, slightly guilt-tripping "your kid did nothing" email."""
    from datetime import timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    completed_rows = (LessonProgress.query
                       .filter(LessonProgress.user_id == user.id,
                               LessonProgress.completed == True,
                               LessonProgress.completed_at != None,
                               LessonProgress.completed_at >= week_ago)
                       .all())
    if not completed_rows and (user.weekly_xp or 0) == 0:
        return None
    badge_rows = (UserBadge.query
                  .filter(UserBadge.user_id == user.id, UserBadge.earned_at >= week_ago)
                  .all())
    return {
        'username': user.username,
        'lessons_completed': len(completed_rows),
        'xp_earned': user.weekly_xp or 0,
        'level_name': user.level['name'],
        'league': user.league,
        'streak_days': user.streak_days or 0,
        'badges_earned': [ub.badge.name for ub in badge_rows if ub.badge],
        'manage_url': url_for('parent_manage', token=user.parent_manage_token, _external=True) if user.parent_manage_token else '',
    }

@app.route('/parent/manage/<token>', methods=['GET', 'POST'])
def parent_manage(token):
    """A login-free preferences page for a verified parent — reached from the
    verification email or any digest email. Lets them opt in/out of the
    weekly digest at any time without needing an account of their own."""
    user = User.query.filter_by(parent_manage_token=token).first()
    if not user:
        flash('This link is invalid or has expired.')
        return redirect(url_for('index'))
    if request.method == 'POST':
        user.parent_digest_opt_in = bool(request.form.get('digest_opt_in'))
        db.session.commit()
        _log_event('parent_digest_opt_in' if user.parent_digest_opt_in else 'parent_digest_opt_out',
                    user_id=user.id)
        flash('Your preferences have been saved.')
        return redirect(url_for('parent_manage', token=token))
    return render_template('parent_manage.html', student=user, contact_email=CONTACT_EMAIL)

@app.cli.command('send-parent-digests')
def send_parent_digests_command():
    """Flask CLI command: `flask send-parent-digests`. Sends the weekly
    progress digest to every parent who has opted in. Intended to be run
    once a week by an external scheduler (cron, a platform's scheduled-jobs
    feature, etc.) — this app has no built-in scheduler of its own."""
    candidates = User.query.filter(
        User.role != 'admin',
        User.parent_verified == True,
        User.parent_digest_opt_in == True,
        User.parent_email.isnot(None),
    ).all()
    sent, skipped, failed = 0, 0, 0
    for user in candidates:
        digest = _build_parent_digest(user)
        if not digest:
            skipped += 1
            continue
        ok, err = _send_parent_digest_email(user.parent_email, digest)
        if ok:
            user.last_digest_sent_at = datetime.utcnow()
            _log_event('parent_digest_sent', user_id=user.id)
            sent += 1
        else:
            print(f'  FAILED for {user.username}: {err}')
            failed += 1
    db.session.commit()
    print(f'Parent digests: {sent} sent, {skipped} skipped (no activity), {failed} failed.')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html', contact_email=CONTACT_EMAIL)

@app.route('/terms')
def terms():
    return render_template('terms.html', contact_email=CONTACT_EMAIL)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name    = request.form.get('name', '').strip()[:100]
        email   = request.form.get('email', '').strip()[:100]
        subject = request.form.get('subject', '').strip()[:200]
        message = request.form.get('message', '').strip()[:2000]
        if not all([name, email, message]):
            flash('Please fill in all required fields.')
            return redirect(url_for('contact'))
        ok, err = _send_contact_email(name, email, subject or 'General Enquiry', message)
        if ok:
            flash(f"Thanks {name}! We'll get back to you at {email} soon.")
        else:
            # Still show success to user — log the error server-side
            print(f'[CONTACT EMAIL ERROR] {err}')
            flash(f"Thanks {name}! We received your message and will get back to you soon.")
        return redirect(url_for('contact'))
    return render_template('contact.html')

# ==================== AI PROVIDERS ====================
# Architecture:
#   Default    -> Groq (llama-3.3-70b-versatile) for everything: fast chat AND
#                 structured JSON (quiz/project generation), via the json-mode
#                 helper below. Groq is the only provider this app calls
#                 unless ENABLE_GEMINI=true is explicitly set.
#   Fallback   -> Gemini, ONLY if ENABLE_GEMINI=true. Off by default because
#                 Gemini's terms prohibit use in an app aimed at under-18s —
#                 see the Provider policy note further down this file.
#
# API keys never touch the browser — all calls are server-side proxies.

from groq import Groq as _GroqClient
from google import genai as _genai
from google.genai import types as _genai_types

GROQ_MODEL   = 'llama-3.3-70b-versatile'
GEMINI_MODEL = 'gemini-2.5-flash'

# ── Provider policy ────────────────────────────────────────────────────────
# Google's Gemini API Additional Terms of Service prohibit use in an
# application "directed towards or is likely to be accessed by individuals
# under the age of 18" (https://ai.google.dev/gemini-api/terms). Nexa Pals is
# a kids' coding platform, so Gemini is OFF by default and must be turned on
# explicitly — and only once that's been checked against Google's current
# terms for your use case (e.g. a separate adult-only track). Groq's own
# terms require the ACCOUNT HOLDER to be 18+ (which the school/organisation
# running this deployment is) and Groq does not retain inference data by
# default, so it is the default and — unless ENABLE_GEMINI is set — the only
# provider this app will call.
ENABLE_GEMINI       = os.getenv('ENABLE_GEMINI', 'false').strip().lower() == 'true'
# Global kill switch — flip to 'false' in .env to instantly disable every AI
# feature (e.g. if a provider changes terms, or during an incident) without
# a code change or redeploy.
AI_FEATURES_ENABLED = os.getenv('AI_FEATURES_ENABLED', 'true').strip().lower() == 'true'

_KID_SAFE = (
    'You are a friendly, encouraging coding tutor for kids aged 10–14 on Nexa Pals. '
    'Never just give the answer — guide the student to understand the concept themselves. '
    'Use simple language, short sentences, and relatable analogies (sport, food, games). '
    'Celebrate effort: phrases like "Great question!", "You\'re so close!", "Nice thinking!". '
    'Keep responses concise (4–7 sentences) unless writing code. '
    'Never produce content that is violent, adult, political, or unrelated to coding. '
    'If asked anything off-topic, warmly redirect back to coding.'
)

# ── Core provider functions ───────────────────────────────────────────────────

def _chat_groq(system: str, messages: list, max_tokens: int = 700) -> str:
    """
    Fast chat via Groq (llama-3.3-70b-versatile).
    messages: list of {'role': 'user'|'assistant', 'content': str}
    Raises groq.RateLimitError on 429, groq.APIStatusError on other API errors.
    """
    api_key = os.getenv('GROQ_API_KEY', '')
    if not api_key:
        raise ValueError('GROQ_API_KEY not set')
    client = _GroqClient(api_key=api_key)
    full_messages = [{'role': 'system', 'content': system}] + messages
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=full_messages,
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return completion.choices[0].message.content

def _chat_groq_json(system: str, prompt: str, max_tokens: int = 1200) -> str:
    """
    Structured JSON generation via Groq (default provider — see the Provider
    policy note above). Uses response_format json_object so the model is
    constrained to emit valid JSON; the system prompt still spells out the
    exact shape we need since json_object mode only guarantees *valid* JSON,
    not a particular schema.
    """
    api_key = os.getenv('GROQ_API_KEY', '')
    if not api_key:
        raise ValueError('GROQ_API_KEY not set')
    client = _GroqClient(api_key=api_key)
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {'role': 'system', 'content': system + ' Respond with a single JSON object or array only — no markdown fences, no commentary.'},
            {'role': 'user', 'content': prompt},
        ],
        max_tokens=max_tokens,
        temperature=0.5,
    )
    raw = completion.choices[0].message.content or ''
    return raw.strip().strip('`').lstrip('json').strip('`').strip()

def _chat_gemini(system: str, messages: list, max_tokens: int = 700) -> str:
    """
    Fallback chat via Gemini (gemini-2.5-flash).
    Converts message history to Gemini's Content format.
    """
    api_key = os.getenv('GEMINI_API_KEY', '')
    if not api_key:
        raise ValueError('GEMINI_API_KEY not set')
    client = _genai.Client(api_key=api_key)
    # Gemini takes history as list of Content objects; last user turn is the prompt
    history = []
    for msg in messages[:-1]:
        role = 'user' if msg['role'] == 'user' else 'model'
        history.append(_genai_types.Content(role=role, parts=[_genai_types.Part(text=msg['content'])]))
    last_msg = messages[-1]['content'] if messages else ''
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=history + [_genai_types.Content(role='user', parts=[_genai_types.Part(text=last_msg)])],
        config=_genai_types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=0.7,
        ),
    )
    return response.text

def _quiz_gemini(system: str, prompt: str, max_tokens: int = 1000) -> str:
    """
    Structured JSON quiz generation via Gemini with enforced JSON output.
    Uses responseMimeType='application/json' so the response is always
    valid JSON — no markdown fences to strip.
    """
    api_key = os.getenv('GEMINI_API_KEY', '')
    if not api_key:
        raise ValueError('GEMINI_API_KEY not set')
    client = _genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[_genai_types.Content(role='user', parts=[_genai_types.Part(text=prompt)])],
        config=_genai_types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=0.4,
            response_mime_type='application/json',
        ),
    )
    return response.text

# ── Fallback wrapper ──────────────────────────────────────────────────────────

import groq as _groq_module

def _chat_with_fallback(system: str, messages: list, max_tokens: int = 700) -> tuple[str, str]:
    """
    Try Groq first (fast, and our only provider by default — see the
    Provider policy note above). If ENABLE_GEMINI is set, fall back to
    Gemini on rate-limit (429) or outage; otherwise a Groq failure just
    raises, and the route returns a friendly "try again" message.
    Returns (reply_text, provider_used) so callers can log which path was taken.
    """
    try:
        reply = _chat_groq(system, messages, max_tokens)
        return reply, 'groq'
    except ValueError:
        # Groq key missing
        if not ENABLE_GEMINI:
            raise
    except _groq_module.RateLimitError:
        # 429 — Groq quota hit
        if not ENABLE_GEMINI:
            raise
    except _groq_module.APIStatusError as e:
        # 5xx outage or other server error
        if e.status_code < 500 and e.status_code != 429:
            raise  # 4xx that isn't rate-limit: re-raise (bad request etc.)
        if not ENABLE_GEMINI:
            raise
    except Exception:
        if not ENABLE_GEMINI:
            raise  # Any unexpected Groq error, no fallback configured

    # Gemini fallback — only reached when ENABLE_GEMINI is true
    reply = _chat_gemini(system, messages, max_tokens)
    return reply, 'gemini'

# ── Route helpers ─────────────────────────────────────────────────────────────

def _err(msg, code=503):
    return jsonify({'success': False, 'message': msg}), code

def _ai_gate(user):
    """
    Returns an error Response to short-circuit an AI route, or None if the
    request may proceed. Two checks, in order:
      1. The global kill switch (AI_FEATURES_ENABLED) — off means off for
         everyone, instantly, no redeploy needed.
      2. Minors need a verified parent email before AI features unlock —
         the AI tutor talks with a child one-on-one, so a parent should have
         confirmed they know their child is using it before that starts.
    """
    if not AI_FEATURES_ENABLED:
        return _err('AI features are temporarily unavailable.', 503)
    if getattr(user, 'is_minor', False) and not getattr(user, 'parent_verified', True):
        return _err(
            "AI features unlock once a parent verifies your account — check "
            "the email we sent them, or ask them to check their inbox.",
            403,
        )
    return None

def _weak_topics_for(user, exclude_title=None, limit=3):
    """Pull real signal from this student's own quiz history — lessons they
    passed but scored under 90% on — so the AI tutor can quietly give extra
    scaffolding on topics that have actually tripped them up before, instead
    of treating every student identically."""
    rows = (LessonProgress.query
            .filter(LessonProgress.user_id == user.id,
                    LessonProgress.completed == True,
                    LessonProgress.score < 90)
            .order_by(LessonProgress.score.asc())
            .limit(limit + 1)
            .all())
    titles = []
    for r in rows:
        lesson = Lesson.query.get(r.lesson_id)
        if lesson and lesson.title != exclude_title:
            titles.append(lesson.title)
        if len(titles) >= limit:
            break
    return titles

# ── 1. Code Explainer ─────────────────────────────────────────────────────────
@app.route('/api/ai/explain', methods=['POST'])
@login_required
def ai_explain():
    _gate = _ai_gate(current_user)
    if _gate:
        return _gate
    if _is_action_rate_limited('ai', str(current_user.id), AI_MAX_PER_WINDOW, AI_WINDOW_SECONDS):
        return _err('Too many AI requests — please wait a few minutes and try again.', 429)
    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip()[:2000]
    lang = data.get('lang', 'code')
    if not code:
        return _err('No code provided', 400)
    system = (
        _KID_SAFE +
        'You explain code in plain English for a 10-year-old. '
        'Start with "Here\'s what this code does:" then explain each important part. '
        'Use bullet points. Use simple analogies — compare code to things kids know. '
        'Highlight any cool or clever parts to build excitement about coding.'
    )
    try:
        reply, _ = _chat_with_fallback(
            system,
            [{'role': 'user', 'content': f'Please explain this {lang} code:\n\n```{lang}\n{code}\n```'}]
        )
        return jsonify({'success': True, 'reply': reply})
    except ValueError as e:
        return _err(str(e))
    except Exception:
        return _err('AI unavailable right now — please try again in a moment')

# ── 2. Code Helper (Playground) ───────────────────────────────────────────────
@app.route('/api/ai/help', methods=['POST'])
@login_required
def ai_help():
    _gate = _ai_gate(current_user)
    if _gate:
        return _gate
    if _is_action_rate_limited('ai', str(current_user.id), AI_MAX_PER_WINDOW, AI_WINDOW_SECONDS):
        return _err('Too many AI requests — please wait a few minutes and try again.', 429)
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()[:500]
    html = (data.get('html') or '')[:1500]
    css  = (data.get('css')  or '')[:1000]
    js   = (data.get('js')   or '')[:1000]
    if not question:
        return _err('Please type a question', 400)
    system = (
        _KID_SAFE +
        'You are helping a kid debug or improve their HTML/CSS/JavaScript project. '
        'Do NOT just give the fixed code — first ask "What do you think is happening?" '
        'or explain the concept behind the bug so they learn. '
        'Then show the corrected code wrapped in ```html, ```css, or ```js fences. '
        'Always explain WHY the fix works. End with an encouraging line.'
    )
    context = f'HTML:\n```html\n{html}\n```\nCSS:\n```css\n{css}\n```\nJS:\n```js\n{js}\n```'
    user_msg = f"Here's my current code:\n\n{context}\n\nMy question: {question}"
    try:
        reply, _ = _chat_with_fallback(system, [{'role': 'user', 'content': user_msg}], max_tokens=900)
        return jsonify({'success': True, 'reply': reply})
    except ValueError as e:
        return _err(str(e))
    except Exception:
        return _err('AI unavailable right now — please try again in a moment')

# ── 3. Lesson Tutor (multi-turn, with history) ────────────────────────────────
@app.route('/api/ai/tutor', methods=['POST'])
@login_required
def ai_tutor():
    _gate = _ai_gate(current_user)
    if _gate:
        return _gate
    if _is_action_rate_limited('ai', str(current_user.id), AI_MAX_PER_WINDOW, AI_WINDOW_SECONDS):
        return _err('Too many AI requests — please wait a few minutes and try again.', 429)
    data = request.get_json(silent=True) or {}
    question     = (data.get('question') or '').strip()[:500]
    lesson_title = (data.get('lesson_title') or 'this lesson')[:100]
    track        = (data.get('track') or 'web coding')[:20]
    history      = data.get('history', [])[:8]
    if not question:
        return _err('Please type a question', 400)
    weak_topics = _weak_topics_for(current_user, exclude_title=lesson_title)
    weak_context = ''
    if weak_topics:
        weak_context = (
            f' This student has previously scored under 90% on: {", ".join(weak_topics)}. '
            'If today\'s question touches on similar ideas, give a little extra scaffolding '
            'and a simpler example first — but don\'t mention their past scores directly.'
        )
    system = (
        _KID_SAFE +
        f'You are tutoring a student on the lesson "{lesson_title}" in the {track} track. '
        'Stay focused on THIS lesson topic only — gently redirect if they go off-topic. '
        'Guide with questions: "What do you think would happen if…?", "Can you spot the pattern?". '
        'Give one clear example when helpful, using the lesson\'s own code snippets. '
        'NEVER directly give quiz answers — guide understanding instead. '
        'Remember what the student said earlier in this conversation.' + weak_context
    )
    messages = []
    for turn in history:
        role    = turn.get('role')
        content = (turn.get('content') or '')[:400]
        if role in ('user', 'assistant') and content:
            messages.append({'role': role, 'content': content})
    messages.append({'role': 'user', 'content': question})
    try:
        reply, _ = _chat_with_fallback(system, messages, max_tokens=700)
        return jsonify({'success': True, 'reply': reply})
    except ValueError as e:
        return _err(str(e))
    except Exception:
        return _err('AI unavailable right now — please try again in a moment')

# ── 4. Project Idea → Code Generator ─────────────────────────────────────────
@app.route('/api/ai/generate', methods=['POST'])
@login_required
def ai_generate():
    _gate = _ai_gate(current_user)
    if _gate:
        return _gate
    if _is_action_rate_limited('ai', str(current_user.id), AI_MAX_PER_WINDOW, AI_WINDOW_SECONDS):
        return _err('Too many AI requests — please wait a few minutes and try again.', 429)
    data = request.get_json(silent=True) or {}
    idea = (data.get('idea') or '').strip()[:400]
    if not idea:
        return _err('Please describe your idea', 400)
    # Deliberately NOT "generate a finished project": handing a kid working
    # code for the whole idea teaches them to click Generate, not to code.
    # The model is asked for a starter with exactly one clearly-marked gap
    # left for the student to write themselves — see the research note in
    # UPGRADE_NOTES.md on generative-AI risk for novice programmers.
    system = (
        _KID_SAFE +
        'You generate STARTER HTML/CSS/JS projects for kids, based on their idea — never a finished, '
        'fully-working project. The point is for the student to write the last piece themselves. '
        'Build working, interactive code for most of the idea, but leave exactly ONE clearly-marked gap '
        'for the student to complete — one function left unfinished, one event handler missing its body, '
        'or one calculation not yet written. Mark the gap with a comment: "// TODO: your code here" (or '
        '"/* TODO: your code here */" in CSS). Everything else must run without errors with the gap left '
        'in place — the one incomplete feature can simply do nothing yet; nothing else should break. '
        'Output ONLY valid JSON with exactly these keys: '
        '"title" (short project name, max 40 chars), '
        '"html" (complete HTML body content, no <html>/<head>/<body> tags), '
        '"css" (all CSS), '
        '"js" (all JavaScript, containing exactly one TODO gap as described above), '
        '"todo" (one encouraging sentence telling the student exactly what to write in the gap, e.g. '
        '"Finish the addScore() function so clicking the button adds 10 points"), '
        '"hint" (one small nudge if they get stuck — never the full answer). '
        'Code must be beginner-friendly, well-commented, and interactive. '
        'Keep total code under 80 lines. '
        'Output raw JSON only — no markdown fences, no explanation.'
    )
    prompt = f'Create a fun starter web project (with one gap left for me to finish) for this idea: {idea}'
    required_keys = {'title', 'html', 'css', 'js', 'todo'}
    def _shape(parsed):
        return {
            'title': parsed['title'], 'html': parsed['html'], 'css': parsed['css'], 'js': parsed['js'],
            'todo': parsed['todo'], 'hint': parsed.get('hint', ''),
        }
    try:
        # Groq primary (default provider — see Provider policy note above)
        raw = _chat_groq_json(system, prompt, max_tokens=1400)
        parsed = json.loads(raw)
        if not required_keys.issubset(parsed.keys()):
            raise ValueError('Missing keys in AI response')
        return jsonify({'success': True, **_shape(parsed)})
    except (json.JSONDecodeError, ValueError) as e:
        if not ENABLE_GEMINI:
            return _err('AI returned unexpected format — try rephrasing your idea', 500)
        # Gemini fallback — only reached when ENABLE_GEMINI is true
        try:
            raw2 = _quiz_gemini(system, prompt, max_tokens=1400)
            parsed2 = json.loads(raw2)
            if not required_keys.issubset(parsed2.keys()):
                raise ValueError('Missing keys')
            return jsonify({'success': True, **_shape(parsed2)})
        except Exception:
            return _err('AI returned unexpected format — try rephrasing your idea', 500)
    except Exception:
        return _err('AI unavailable right now — please try again in a moment')

# ── 5. Admin Quiz Generator (Groq by default, JSON mode) ─────────────────────
@app.route('/api/ai/quiz', methods=['POST'])
@login_required
def ai_quiz():
    if current_user.role != 'admin':
        return _err('Admin access only', 403)
    if not AI_FEATURES_ENABLED:
        return _err('AI features are temporarily unavailable.', 503)
    data  = request.get_json(silent=True) or {}
    topic = (data.get('topic') or '').strip()[:200]
    track = (data.get('track') or 'web coding')[:30]
    count = min(int(data.get('count', 3)), 6)
    if not topic:
        return _err('Please provide a topic', 400)
    system = (
        f'You generate multiple-choice quiz questions about web coding for kids aged 10–14. '
        f'Output ONLY a JSON array of exactly {count} question objects. '
        'Each object must have: '
        '"q" (question string), '
        '"options" (array of exactly 4 answer strings), '
        '"answer" (0-based integer index of the correct option). '
        'Questions must test understanding, not just memorisation. '
        'Language must be simple and age-appropriate. '
        'Output a raw JSON array only.'
    )
    prompt = f'Generate {count} quiz questions about: {topic} (track: {track})'
    try:
        # Groq primary (default provider — see Provider policy note above)
        raw = _chat_groq_json(system, prompt, max_tokens=1000)
        questions = json.loads(raw)
        if not isinstance(questions, list):
            raise ValueError('Expected a JSON array')
        for q in questions:
            if not {'q', 'options', 'answer'}.issubset(q.keys()):
                raise ValueError('Missing question fields')
            if len(q['options']) != 4:
                raise ValueError('Each question must have exactly 4 options')
        return jsonify({'success': True, 'questions': questions})
    except (json.JSONDecodeError, ValueError) as e:
        if not ENABLE_GEMINI:
            return _err(f'AI returned unexpected format — try again: {e}', 500)
        # Gemini fallback — only reached when ENABLE_GEMINI is true
        try:
            raw2 = _quiz_gemini(system, prompt, max_tokens=1000)
            questions2 = json.loads(raw2)
            if not isinstance(questions2, list):
                raise ValueError('Expected array')
            return jsonify({'success': True, 'questions': questions2})
        except Exception:
            return _err(f'AI returned unexpected format — try again: {e}', 500)
    except Exception:
        return _err('AI unavailable right now — please try again in a moment')

if __name__ == '__main__':
    # Never run with the interactive debugger enabled in production — it allows
    # arbitrary code execution to anyone who can reach an error page.
    app.run(debug=not IS_PROD, host='0.0.0.0', port=5000)
