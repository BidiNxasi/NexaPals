# Tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

`conftest.py` points the app at a temporary SQLite file before importing
`app.py`, so these tests never touch your real `database.db`.

There's also a standalone Node test for the client-side "Try It Live"
practice-challenge auto-checker (no framework, matches the rest of the
project's JS):

```bash
node tests/test_practice_checks.js
```

## What's covered

- `test_gamification.py` — levels, the Ship Streak, weekly league
  promotion/demotion, badge awarding. Includes a regression test for a real
  bug found while building this suite: the top level ("Master") was
  mathematically unreachable due to an off-by-one in the level-threshold
  loop — fixed in `app.py`, and tested here so it can't quietly come back.
- `test_routes.py` — signup validation (terms acceptance, parental consent
  for minors, duplicate usernames), the parent-verification link, login,
  and the 404/healthz/legal-page routes.
- `test_classroom.py` — teacher classroom creation (including the
  auto-upgrade from student to teacher role and the one-classroom-per-teacher
  limit), the student join-code flow (case-insensitive), and that removing a
  student only works for the teacher who actually owns that classroom.
- `test_parent_digest.py` — the login-free parent preferences page (opt-in
  toggle by token), and the digest builder (summarises a real week, returns
  `None` for a quiet week so opted-in parents never get an empty email,
  ignores lesson completions from before the current week).
- `test_practice_checks.js` — the embedded lesson practice-challenge
  auto-checker for all 15 lessons' starter/solved code, including two
  regression tests for the same bug class: a starter's own comment text
  accidentally satisfying its own check (first found in "Loops & Arrays" —
  the word "for" inside "your **for** loop"; found again in "If Statements"
  — the word "if" inside "**dif**ferent"). **This file is actually executed**
  (not just reasoned through) — see the Honesty note below.

## What's NOT covered yet

AI endpoints (would need mocking the Groq/Gemini clients — including the new
`ENABLE_GEMINI`/`AI_FEATURES_ENABLED` gating and the minor `_ai_gate()`
check), the admin dashboard/CMS, and the `flask send-parent-digests` CLI
command's email-sending path (the digest *builder* is tested; the SMTP send
itself isn't, same as the other two email helpers). Worth adding as those
surfaces stabilize.

## Honesty note

The Python suite (`test_*.py`) was written without network access to
actually install Flask, pytest, etc. in the authoring environment, so it has
been reasoned through line-by-line and partially verified with standalone
logic replication, but **has not been executed end-to-end**. Run it yourself
once dependencies are installed, and treat the first run as the real
verification step.

`test_practice_checks.js`, by contrast, **was actually run** in the
authoring environment (plain Node, no install needed) — all 13 assertions
pass as of this round, including both substring-self-match regression
tests described above.
