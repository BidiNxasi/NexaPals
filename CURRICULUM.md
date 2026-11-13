# Nexa Pals Curriculum — Audit & Plan

## Where the curriculum stood

15 lessons across 3 tracks (HTML x4, CSS x5, JavaScript x6), each with a short
reading, a "Try it!" prompt pointing at the Playground, and a 3-question
multiple-choice quiz gating completion (70%+ to pass). Strong bones — clear
progression, age-appropriate language, real code in every example — but only
3 of the 15 lessons (Lists & Tables, Functions, Loops & Arrays) had an
embedded "Try It Live" practice challenge. The other 12 relied entirely on
reading + multiple choice, which tests recognition, not the ability to
actually write code — the gap called out when this round of work started.

## What changed this round

**All 15 lessons now have an embedded practice challenge** — a real,
auto-checked coding gap the student fills in and gets instant pass/fail
feedback on, right inside the lesson (see `templates/lesson.html`'s "Try It
Live" widget). This was the single highest-leverage curriculum fix available:
CodeCombat's own pedagogy research is explicit that "the code you write IS
the move" beats quiz recognition for retention, and it was true for less
than a fifth of the curriculum before this pass.

Along the way, the practice widget itself was extended to support a
**CSS field** (`starter_css`), not just HTML/JS — it only supported two of
the three languages before, which meant a CSS lesson literally couldn't get
a practice challenge without this change. All 5 CSS lessons now have one.

Every new challenge was verified two ways before being trusted (see
`tests/test_practice_checks.js`, actually executed, 13/13 passing):
1. The **unsolved starter must fail** its own check — this project already
   found one real bug this way (a starter comment containing the literal
   substring "for", making the unsolved code accidentally pass a `contains:
   'for'` check). A second instance of the same bug class was caught and
   fixed in this round: the new "If Statements" starter comment used the
   word "different", which contains "if" as a substring, and would have
   silently pre-passed the check for writing an `if` statement.
2. A **realistic solved version must pass**.

## Lesson-by-lesson audit (what practice challenge was added, and why)

| Track | Lesson | Gap the student fills in |
|---|---|---|
| HTML | What is HTML? | Add a `<p>` paragraph next to a heading |
| HTML | Links & Images | Add `href=` to a bare `<a>` tag |
| HTML | Lists & Tables | *(existing)* extend a list to 3 items |
| HTML | Forms & Inputs | Add a submit `<input>` to a form |
| CSS | What is CSS? | Add a `color` rule to a heading |
| CSS | Colours & Backgrounds | Add a `background` to the page |
| CSS | Fonts, Size & Spacing | Add `padding` to a squished paragraph |
| CSS | Flexbox Layout | Turn a row of cards into `display: flex` |
| CSS | Animations & Transitions | Add a `transition` so a hover isn't instant |
| JS | Variables & Data Types | Use `alert()` with a variable |
| JS | If Statements & Logic | Write an `if`/`else` that branches on a score |
| JS | Functions | *(existing)* define, return from, and call a function |
| JS | DOM — Changing the Page | Wire up `addEventListener` + `textContent` |
| JS | Loops & Arrays | *(existing)* write a `for` loop that builds output |
| JS | Build a Clicker Game | Wire a click counter end to end |

## What's next (not done in this round — sizing for a follow-up)

These are recommendations, not started:

1. **A 4th track.** Three tracks (HTML/CSS/JS) covers web basics well but
   competitors increasingly offer a visible "next step" (Python, or a
   block-to-text bridge) so a student who finishes the web track has
   somewhere to go instead of hitting a wall. Given the DBE's 2024
   Coding & Robotics curriculum gazette for Grades R-9, a track that maps
   loosely onto that syllabus would also make the "aligned with what your
   child is learning at school" pitch to parents concrete instead of vague.
2. **Difficulty ramp within tracks.** All 15 lessons are currently a flat
   10-15-25 XP curve with no branching — every student takes the same path
   in the same order. A stronger v2 would let a student who's clearly ahead
   (consistently 100% on quizzes, fast lesson completion) skip into harder
   optional lessons instead of grinding through material they've already
   demonstrated mastery of.
3. **More than one practice challenge per lesson.** Right now each lesson
   has exactly one embedded gap. Lessons with more surface area (Flexbox,
   DOM, the Clicker Game) could reasonably support two smaller challenges
   instead of one, for more repetition without lengthening the reading.
4. **Project-based capstones between tracks.** A short "build something that
   uses everything from this track" capstone between HTML->CSS and CSS->JS
   would give students a portfolio piece earlier, which matters for the
   "kids build real things" positioning against competitors who are mostly
   drag-and-drop.

None of these were started — sizing them accurately needs usage data (which
lessons students actually get stuck on) that doesn't exist yet without the
analytics now in place (see `UPGRADE_NOTES.md`) collecting a few weeks of
real signal.
