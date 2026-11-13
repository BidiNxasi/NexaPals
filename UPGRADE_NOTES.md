# Upgrade notes — this pass

## Do this first
1. **Rotate every credential in your old `.env`.** It was included in the zip
   you shared, which means `SECRET_KEY`, `ADMIN_PASSWORD`, `SMTP_USER`/`SMTP_PASS`,
   `GROQ_API_KEY`, and `GEMINI_API_KEY` should all be treated as compromised.
   Generate new values and put them in a fresh `.env` based on `.env.example`.
2. Set `FLASK_ENV=production` on your real deployment. Without it:
   - the site refuses to boot unless `ADMIN_PASSWORD` is set (no more default
     admin password),
   - the interactive debugger stays off,
   - HTTPS/HSTS enforcement stays off.
3. Delete `instance/database.db` before your next deploy so it reseeds with
   the new (non-emoji) badge/avatar/testimonial values and the env-aware
   demo-account logic. If you need to keep existing production data, you'll
   need a small manual migration for the `avatar`/`emoji` column values
   instead (see "Data note" below).

## Bugs fixed
- `complete_lesson()` crashed with a `NameError` on every first-time lesson
  pass (`already_completed` was referenced but never defined) — this broke
  the entire XP/badge-award flow. Fixed.
- The Werkzeug debug server was hardcoded on (`debug=True`) — this would
  expose remote code execution if the app were ever run directly instead of
  through gunicorn. Now gated by `FLASK_ENV`.
- The code preview iframe (`/play`) had **no sandbox attribute at all** —
  the most permissive state possible for arbitrary user JS. Now
  `sandbox="allow-scripts"`. The arcade game iframe had
  `allow-scripts allow-same-origin` together, a known combination that lets
  sandboxed `srcdoc` content reach back into the parent's origin — the
  `allow-same-origin` flag has been removed.
- Signup and all four user-facing AI endpoints (`explain`, `help`, `tutor`,
  `generate`) had no rate limiting, so a bored kid — or a bot — could run up
  your Groq/Gemini bill or mass-create accounts. Added a sliding-window
  limiter (reusing the pattern your login route already had).
- The demo account (`test`/`test123`) and the default admin password
  (`nexa-admin-2026`) no longer seed in production.

## Emoji removed, site-wide
Every emoji across `app.py`, all 19 templates, and `script.js` has been
replaced — with Font Awesome icons where something visual still belongs
there, and with plain text where it doesn't. This wasn't just find-and-delete:
- `User.avatar`, `Badge.emoji`, and `Testimonial.emoji` now store Font Awesome
  icon class names (e.g. `fa-rocket`) instead of emoji characters. Every
  template that renders them was updated to render `<i class="fas ...">`.
- Memory Match's tile set is now coding symbols (`{ }`, `< >`, `#`, `&&`, …)
  instead of emoji.
- Catch the Stars now draws an actual star shape on the canvas instead of
  rendering a star emoji character as text.
- The "Build a Clicker Game" lesson's example code was rewritten to level up
  through text labels (Rookie → Builder → Coder → Hacker → Ultimate Coder)
  instead of an emoji progression, since the emoji were the actual subject
  of that code sample, not decoration.
- Along the way in `script.js`, I found and removed a chunk of genuinely
  dead code (a `DOMContentLoaded` handler wired to element IDs — `buddyAvatar`,
  `clickCounter`, `testimonialBox`, etc. — that don't exist in any current
  template) which was also silently overriding the real, working
  `showMessage` function. Only the parts that actually run (`.project-card`,
  `.feature-card` handlers) were kept.

## Data note
Because `avatar`/`emoji` columns changed from emoji characters to Font
Awesome class names, any **existing** rows in a production database (real
users' saved avatars, existing badges/testimonials) still hold the old emoji
values and will render blank icons until reseeded or manually updated. For a
brand-new deploy this is a non-issue. For an existing one with real users,
either reseed from scratch or write a short one-off script mapping the old
emoji values to the new class names before deploying this version.

## Roadmap items now implemented (this pass)

**Ship Streak** — the streak no longer advances on login (that rewarded
attendance, not output). It now only advances when a student ships
something: completing a lesson or saving a project. Saving a project also
earns a one-time-per-day 5 XP "ship bonus."

**Weekly Leagues** — `User` gained `weekly_xp`, `league`
(bronze/silver/gold/diamond), and `week_start`. All XP now goes through
`User.add_xp()`, which keeps all-time and weekly XP in sync and lazily rolls
a student's league over when a new week starts (promote at 100+ weekly XP,
demote if fully inactive the week before). The leaderboard page now has two
tabs: "This Week's League" (small-cohort, resets every Monday) and the
original all-time leaderboard. This is a simplified, threshold-based version
of Duolingo-style leagues — true relative-cohort ranking (30 students
competing head-to-head, moved as a synchronized batch) needs a real
scheduled job (Celery beat / cron), which this app doesn't have yet. Worth
revisiting once there's real deployment infrastructure and a large enough
user base for cohorts to be meaningful.

**AI tutor personalization** — the lesson tutor (`/api/ai/tutor`) now pulls
a student's own quiz history (lessons passed but scored under 90% on) via
`_weak_topics_for()` and quietly feeds it into the system prompt as
scaffolding guidance. No schema change — it reads data you already had. The
tutor never reveals past scores to the student directly.

**Embedded live-practice challenges** — added a `practice_json` column to
`Lesson` and built a full "Try It Live" widget in `lesson.html`: a
starter-code editor, a sandboxed live preview, and a "Check My Code" button
that pattern-matches the student's code against required substrings (e.g.
"must contain a `for` loop and update `output`"), giving real pass/fail
feedback instead of a multiple-choice question about the concept. Implemented
end-to-end for **3 pilot lessons** (HTML: Lists & Tables · JS: Functions ·
JS: Loops & Arrays) to prove the mechanism works; the other 12 lessons still
use quiz-only assessment. Adding practice to another lesson just means
adding a `practice_json` dict with `starter_html`/`starter_js`, `checks`
(substring + optional `min_count` + hint), and `success_msg` — no template
changes needed.

**Still not done**: capstone projects for the HTML/CSS tracks, the combined
"Build a Real Website" track, XP for game high scores (no score-persistence
model exists yet), more badges, level-locked avatar unlocks, and the "Ship
Streak → visible portfolio timeline" idea discussed but not built. These are
still the right next moves — this pass focused on proving each of the four
strategic pillars (ship-based streak, cohort competition, adaptive AI,
practice-not-quiz) actually works end-to-end rather than spreading thin
across all of them at once.

Also still outstanding from earlier passes:
- A custom mascot/icon set to replace Font Awesome's generic icons with
  something visually distinct to Nexa Pals — needs real design work, not code.
- The all-ages / dual-track architecture (branching the AI tutor's tone and
  adding a portfolio-style view for older learners).
- POPIA/child-data compliance review (parental consent flow, data deletion
  path) — worth a real conversation with a lawyer, not just an engineering fix.

## Data note (updated)
Because of the new `weekly_xp`, `league`, `week_start`, `last_ship_bonus_date`
columns on `User` and the new `practice_json` column on `Lesson`, an existing
production database needs `instance/database.db` deleted and reseeded (or a
manual `ALTER TABLE` migration) before this version will run against it.

## This pass: the 7 launch-readiness items

This pass worked through the full analyst checklist in priority order —
launch blockers first, then things that break under real load, then the
strategic gaps. Every item below adds new `User`/`Classroom` columns, so
the same "delete and reseed `instance/database.db`" note above applies.

**1. Legal & parental consent** — real Privacy Policy and Terms of Service
pages (`/privacy`, `/terms`, linked in the footer), explicitly flagged as
"not lawyer-reviewed, get that checked." Signup now requires agreeing to
both, plus an "I am under 18" checkbox that requires a parent/guardian
email and sends them a real verification email with a one-click confirm
link. A minor's account works immediately (doesn't hard-block on
verification) but shows a small pending banner until confirmed.

**2. Analytics & error tracking (self-hosted stand-in)** — `AnalyticsEvent`
and `ErrorLog` tables, logged from every key funnel point (signup, login,
lesson completion, ship bonus, badge earned, league promotion/demotion,
classroom created/joined) plus unhandled exceptions. The admin dashboard
now shows real D7 retention, signups today/this week, active-today, and a
7-day event breakdown. Explicitly a placeholder for real Sentry/PostHog/GA
once there's network access and API keys — the `_log_event()` call sites
won't need to change when you swap it in.

**3. Infrastructure config** — `DATABASE_URL` is now env-configurable
(defaults to SQLite, ready for Postgres with no code change), and
production now refuses to boot without a real `SECRET_KEY` (same pattern as
the `ADMIN_PASSWORD` gate). The in-memory rate limiter's per-worker-process
limitation is now documented directly in the code with a fix path (a shared
store like Redis) rather than left as a silent trap for whoever scales this
to multiple gunicorn workers.

**4. Automated test suite** — `tests/` now has a real pytest suite
(gamification logic, routes, classroom flow) plus a standalone Node test
for the lesson practice-check logic. Writing it surfaced a real pre-existing
bug: the top level ("Master") was mathematically unreachable due to an
off-by-one in the level-threshold loop — fixed in `app.py` and covered by a
regression test. **Honesty note**: this environment has no network access to
install Flask/pytest, so the suite is carefully reasoned through and the
Node portion was actually run (7/7 passing), but the Python suite itself
has not been executed end-to-end — run it yourself as the real verification
step (`tests/README.md` has the exact commands).

**5. Admin CMS for lessons** — full create/edit/delete UI at
`/admin/lessons/*` with JSON validation on save (a malformed quiz or
practice payload gets caught with a clear error, not a silently broken
lesson). Content no longer requires editing `app.py`.

**6. Teacher/classroom MVP** — a `Classroom` model, a teacher dashboard
(`/teacher`) showing student XP/level/streak/lessons-completed, and a
student join-code flow (`/join-classroom`). Deliberately simple for a first
version: one classroom per teacher, no bulk CSV import, no LMS integration.
This is the distribution-channel feature flagged as the highest-leverage
growth lever several turns ago — now it actually exists.

**7. Monetization thesis** — written up in `MONETIZATION.md` rather than
built, since there was no decision to build code against yet. The
recommendation: keep the child-facing product free permanently, and monetize
via a future "Classroom Pro" tier sold to schools (not kids) and a
separate paid tier on the future adult/all-ages track — plus grants/CSR
sponsorship as near-term bridge funding. Explicitly recommends against any
purchase flow reachable from a student account.

## Still not done after this pass
- Capstone projects for HTML/CSS, the combined "Build a Real Website" track,
  XP for game high scores, more badges, level-locked avatar unlocks.
- The custom mascot/icon identity (needs design work, not code).
- The all-ages dual-track architecture itself (this pass built the teacher
  channel, not the adult-track content/tone fork).
- Actually running the Python test suite for the first time (see #4 above).
- A real analytics/error-tracking service once there's network + API keys.
- A shared (Redis-backed) rate limiter before running multiple gunicorn workers.
- A scheduler to actually fire the weekly parent digest (see below) — the
  command exists, nothing calls it on a schedule yet.

## This pass: AI-provider safety, kinder gamification, parent digest, curriculum

Prompted by research into ed-tech trends, SA curriculum/connectivity policy,
and — the most consequential finding — Gemini's own API terms of service.

1. **AI provider policy.** Google's Gemini API Additional Terms of Service
   prohibit use in an app "directed towards or is likely to be accessed by
   individuals under the age of 18." Nexa Pals is a kids' coding platform, so
   this was a real compliance problem: Gemini was wired in as a fallback/
   primary provider for the AI tutor, code helper, project generator, and
   admin quiz builder. Fixed by:
   - `ENABLE_GEMINI` (default `false` in `.env.example`) — Gemini is now
     opt-in and off by default. Groq (whose account-holder-must-be-18+ terms
     fit an organisation running this deployment, and which doesn't retain
     inference data by default) is the sole provider unless explicitly
     turned on.
   - `_chat_groq_json()` — a new Groq-based JSON-mode helper so the project
     generator and admin quiz builder don't need Gemini at all for their
     structured-output use case; they only fall back to Gemini if
     `ENABLE_GEMINI=true`.
   - `AI_FEATURES_ENABLED` — a global kill switch (`.env.example`), checked
     first in every AI route.
   - `_ai_gate()` — minors can't reach any AI feature until their parent has
     verified the account (`parent_verified`). An AI conversation with a
     child never starts without a parent knowing the account exists.
   - `templates/privacy.html` updated to reflect Groq as the actual default
     provider and describe the minor-gating behaviour.
2. **Kinder streak & league rules.** Punitive streak-reset-to-1 and weekly
   league demotion are documented manipulative-design patterns that make
   sense for adults who opted into them and don't belong in a kids' product.
   - `User.streak_freezes` — a banked "miss one day, keep your streak" token
     (new accounts start with 1; earn one back every 7-day milestone, capped
     at 3). A single missed day now auto-spends a freeze instead of
     resetting the streak.
   - Leagues (`User._sync_week()`) no longer demote on a quiet week — they
     only ever go up or stay the same.
   - Promotion thresholds now escalate per league (100 / 150 / 200 weekly
     XP for bronze/silver/gold) instead of a flat 100 for every tier.
   - `templates/leaderboard.html` and `templates/profile.html` copy updated
     to match (no more "finish with 0 XP and you'll drop back down").
3. **Opt-in weekly parent digest.** Self-paced kids' platforms benefit from
   more parental visibility, not less — but a digest nobody asked for is
   noise, so this is opt-in only.
   - `User.parent_digest_opt_in`, `parent_manage_token`,
     `last_digest_sent_at` — new columns. The manage token is a standing
     (non-expiring) login-free link, issued when a parent verifies the
     account.
   - `/parent/manage/<token>` (new route + `templates/parent_manage.html`)
     — a parent toggles the digest on/off any time, no account needed.
   - `_build_parent_digest(user)` — returns `None` for a quiet week (no
     activity, no email) or a summary (lessons completed, XP, level,
     league, streak, new badges) for an active one.
   - `flask send-parent-digests` — a new CLI command (`@app.cli.command`)
     that emails every opted-in, parent-verified user's digest. **Nothing
     schedules this yet** — wire it to a weekly cron job (or your host's
     scheduled-jobs feature) once you deploy.
4. **AI project generator now leaves a gap.** Generating a fully finished
   project handed a kid working code for the whole idea and taught them to
   click Generate, not to code — a documented risk of generative AI for
   novice programmers. `ai_generate()`'s system prompt now asks for a
   starter with exactly one clearly-marked `// TODO` gap, plus a `todo` and
   `hint` field in the JSON response. `templates/play.html` shows the
   TODO/hint in a new "Your turn" panel and switches to the JS tab (where
   the gap usually lives) after generating.
5. **Curriculum: all 15 lessons now have an embedded practice challenge**
   (previously 3 of 15). See `CURRICULUM.md` for the full lesson-by-lesson
   audit and what's recommended next. The practice widget itself
   (`templates/lesson.html`) was extended to support a `starter_css` field
   — it only supported HTML/JS before, which meant a CSS lesson literally
   couldn't get a practice challenge without this change.
6. **A second instance of the "starter text accidentally satisfies its own
   check" bug class was found and fixed** while building the "If Statements"
   practice challenge — the draft starter comment used the word
   "different," which contains the substring "if," so an unsolved starter
   would have silently passed the `if`-statement check. Caught the same way
   as the original ("for"/"for loop") instance: simulate the unsolved
   starter against its own checks before trusting it. Now a permanent
   regression test in `tests/test_practice_checks.js`.
7. **A wider emoji sweep caught glyphs the original scan's regex missed** —
   the standing "zero emoji anywhere" rule is not new, but the regex used to
   verify it only covered a few Unicode blocks. Widening it turned up an
   hourglass, a keyboard, an alarm clock, a stop/play button pair, and a
   lightning bolt across `app.py`, `templates/`, and `static/css/style.css`
   that earlier passes had missed. Re-verified at 0 with the wider regex
   after fixing.

## Round 2 — making the app feel alive instead of static

This round followed a strategy conversation about the curriculum and UI
feeling flat. Curriculum expansion (more lessons, more languages, quests)
is intentionally out of scope for this round and stays on the roadmap in
`CURRICULUM.md` — what shipped here is the "make it fun" half:

1. **You already had a mascot — it just wasn't rendering.** The nav logo,
   footer logo, and favicon were all pointing at `NexaLogo.png`, a wide
   1536x1024 image with a solid white background, force-cropped into small
   circular slots via `object-fit: contain` on a dark navbar. The result
   was an almost-invisible white blob. Fixed by cropping two new assets out
   of the original artwork with a flood-fill (not a naive color-threshold)
   transparency pass, so the character's own near-white shading survives
   while the true background is removed:
   - `static/images/mascot_icon.png` — square headshot crop, used in the
     nav, footer, favicon, 404 page, and empty states.
   - `static/images/mascot_full.png` — full-body crop, used in the
     homepage hero and the AI tutor/Code Helper chat bubbles.
2. **The mascot now shows up where a kid is actually interacting with the
   app**, not just the logo slot: next to every AI Lesson Tutor and AI Code
   Helper reply (`.ai-row`/`.ai-avatar` in `templates/lesson.html` and
   `templates/play.html`), in the "no badges yet" and "no projects yet"
   empty states, and on the 404 page.
3. **Sound effects**, synthesized in-browser with the Web Audio API — no
   audio files to download, which matters given SA mobile data costs
   (`static/js/sounds.js`, `window.NexaSound`): a click tick, a
   correct-answer chime, a wrong-answer buzz, a badge jingle, and a
   level-up fanfare. A mute toggle (`#soundToggle` in the nav, persisted to
   `localStorage`) is in `base.html`. Sounds are wired into quiz answers,
   practice-challenge pass/fail, XP toasts, badge unlocks, and level-ups.
4. **Celebration animations.** `window.showConfetti()` in `script.js` is a
   CSS/vanilla-JS confetti burst (no canvas, no library) that respects
   `prefers-reduced-motion`. It fires on quiz pass and, bigger, on level-up.
   `/api/lesson/complete` now also reports `leveled_up`/`new_level_name` so
   `lesson.html` can show a dedicated level-up message instead of treating
   it as just another XP toast.
5. **A no-login "Try It Right Now" widget on the homepage** — a live
   HTML/JS editor with a sandboxed-iframe preview, pre-filled with a small
   working example, auto-run on page load, for a visitor who hasn't signed
   up yet. Gated to logged-out visitors only.

Bugs caught and fixed against myself this round, not flagged by you:
- An early attempt at the transparent mascot crop used a global
  white-threshold instead of a flood-fill, which correctly stripped the
  background but also partially grayed out the character's own white
  shading against the dark navbar. Switched to seeding transparency from
  the border pixels inward (flood fill) instead, which only removes the
  connected background region.
- While drafting the "Try It Now" starter code I wrote a literal emoji
  into an example string (`"You're coding! [emoji]".replace(...)`), which
  would have broken the standing zero-emoji rule. Caught on re-read before
  it was ever shown to you, rewritten as plain text.
- One more emoji slipped through in `UPGRADE_NOTES.md` itself (this file),
  in a sentence describing an earlier fix, not in any shipped code — found
  during this round's final regex sweep and reworded.

Verification this round: `py_compile` on `app.py`, a Jinja2 parse of every
template, `node --check` on `sounds.js` and `script.js`, the full
`tests/test_practice_checks.js` suite (13/13, unaffected by this round's
changes), a Playwright screenshot of the new homepage widget to confirm it
actually renders, and a full-codebase emoji regex sweep (0 matches after
the `UPGRADE_NOTES.md` fix above).

Deliberately not done this round (still on the table from the strategy
discussion, not part of this instruction): the 31-lesson curriculum
expansion, a Python or block-based track, quest/narrative framing of lesson
copy, difficulty branching, capstone projects, a classroom project gallery,
and a full onboarding walkthrough.

One open question: I used "Nexa" as a placeholder name for the mascot in
one `alt` attribute (`templates/index.html`). If the character has an
official name, tell me and I'll make it consistent everywhere.

## Interactive missions (Nov 2026)
- `static/js/mission.js` runs learner code in a sandboxed iframe and tests behaviour (clicks, return values, DOM, styles). No eval; works under the CSP.
- `lesson_missions.py` holds a 3-step mission for every lesson (code / fix / predict / order). `apply_missions()` upgrades existing databases on start.
- Quiz is locked until the mission is done; `/api/mission/complete` logs it and `/api/lesson/complete` returns 403 without it.
- Tests: `NODE_PATH=$(npm root -g) node tests/test_missions.js missions.json` (solutions pass, starters fail) and `tests/test_cheats.js` (old substring cheats are blocked).
- Not run end-to-end against Flask in the build sandbox. Try one lesson locally before the demo.

## Assessment and learning upgrades (Nov 2026, round 2)
- Mission scoring: each lesson is Mastered / Solid / Still practising from checks and solution reveals (`learning_analytics.mastery_level`, mirrored in mission.js).
- Skill tags on every step; `/my-skills` shows strength per skill and links to `/practice/<skill>` (extra steps for that skill).
- `/warmup`: one review question from a lesson finished 2 to 45 days ago.
- `/capstone/<track>`: free-build project per track, unlocked when the track is complete. The checklist is the rubric.
- Teacher dashboard: per-student mastery and weakest skill, plus "Where the class is stuck" (steps where 40%+ of students struggled; needs 3+ students).
- Learning experience: kid-language error messages, hints that unlock after more tries in later lessons, worked example before every mission, symbol keys for phones, Listen button (browser text-to-speech), 44px touch targets, contrast-checked colours.
- Not built: Sesotho / isiZulu text. The hook exists (`prompt_i18n` on a step and `lang` option) but translations need a fluent teacher to write and review them.
- Tests: `tests/test_learning_analytics.py` (ran), `tests/test_missions.js` (108 steps, ran), `tests/test_cheats.js`, `tests/test_engine_features.js` (ran), `tests/test_learning_routes.py` (NOT run: Flask cannot be installed in the build sandbox, run it first).

## "Meet code" introduction (Nov 2026)
- `/start` is a public 5-step hands-on intro (order the steps, predict output, change CSS, fix a typo, write a first page), then asks which track to start with. Content is `INTRO` in `lesson_missions.py`.
- Linked from the home page ("Try coding in 5 minutes") and as a banner on `/learn` for anyone with no completed lessons. Completion is logged as `intro_done` for signed-in users.

## Polish round (Nov 2026)
- Images compressed: 968 KB to 316 KB (logo 530 to 58 KB, hero mascot 356 to 214 KB, icon 83 to 32 KB), same look at the sizes the site shows them.
- Contrast: `--smoke` grey text darkened from 4.2:1 to 5.2:1 on white (WCAG AA needs 4.5).
- Accessibility: skip-to-content link, `<main>` landmark, visible keyboard focus on every control.
- Missions save a learner's draft in the browser, so a refresh or a dropped connection no longer loses their code. Ctrl/Cmd+Enter runs the check.
- `apply_missions` logs a warning if a lesson (track + order) is missing, so you can tell if a mission failed to attach.

## For kids who know nothing yet (Nov 2026)
- `/start` is now "Program a robot": 4 tap-only levels (move, order, a bug to fix, Repeat as a loop) then one step that shows the same idea as real code. No typing, no jargon. `/start/code` is the first real-code intro (5 steps); a "skip" link is there for kids who already know some.
- New `robot` step type in `mission.js`. Programs are simulated, so only a program that really reaches the star passes (and respects the block limit).
- Every lesson mission has a "Code words" panel (plain definitions of tag, variable, function and so on). Intro prompts no longer assume words like alert, console.log or CSS.
- Not built: typing practice for kids who have never used a keyboard, and local-language text. Both are worth testing with the pilot group first.

## Teaching from zero: explore, fill, then build (Nov 2026)
- Every lesson mission now opens with the idea shown before it is asked for. New step types in `mission.js`:
  - `anatomy`: a code snippet whose parts are tappable (opening tag, closing tag with the slash, attribute, selector, property, variable, function...). Each part explains itself. Next unlocks when every part has been explored.
  - `blank`: a snippet with gaps (`___`) so the learner types one word, not a whole program. It is checked by RUNNING the completed code, like every other step.
- Content is `LEARN` in `lesson_missions.py`: 11 explore steps and 15 fill-the-gaps steps, placed in front of the existing build steps. Missions are now 4 to 6 steps. Each lesson goes explore, fill, build, then predict or order.
- The long reading text on each lesson page is unchanged. Consider shortening it, since the missions now do the teaching.
- Test suite: 144 steps run in a browser (starters fail, solutions pass), plus cheat, engine and draft tests.

## Round: "learn everything from zero" gap-fill
- Audit found 24 places where kids met a concept (ol, table, form, class, hex colours, padding, gradient, :hover, else if, classList.toggle, arrays, createElement ...) without an introduction. Added ~14 explore/fill steps plus anatomy steps so every lesson mission introduces what it uses.
- Blank steps now fail when the gaps are left empty (JS2 `else if` also checks the code shape).
- Browser suite: 163 steps, 0 failures. Flask app and tests/test_learning_routes.py still not run in this environment.
