"""Browser test for the lesson quiz: pick-one/pick-several labels, un-picking an
answer, a missing answer, a failing attempt (wrong answers cleared and NOT
revealed), retrying, and a passing attempt (answers shown).

Flask is not needed: the lesson template is rendered with jinja2 and the
/api/lesson/complete call is answered by a stub that uses the real scoring
function copied out of app.py.

Run:  python tests/test_quiz_ui.py      (needs jinja2 and playwright)
"""
import ast, json, os, sys, tempfile
import jinja2
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(ROOT, 'app.py')).read()
tree = ast.parse(src)
ns = {}
for node in tree.body:
    if (isinstance(node, ast.FunctionDef) and node.name == '_quiz_is_correct') or \
       (isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == 'QUIZ_PASS_MARK'):
        exec(compile(ast.Module([node], []), 'app', 'exec'), ns)
is_ok, PASS = ns['_quiz_is_correct'], ns['QUIZ_PASS_MARK']

QUIZ = [
    {"q": "Pick one", "options": ["a", "b", "c"], "answer": 1},
    {"q": "Pick two", "options": ["a", "b", "c", "d"], "answers": [0, 3]},
    {"q": "Pick one again", "options": ["x", "y"], "answer": 0},
]
# scoring unit checks
assert is_ok(QUIZ[0], 1) and not is_ok(QUIZ[0], 2)
assert is_ok(QUIZ[1], [3, 0]) and not is_ok(QUIZ[1], [0]) and not is_ok(QUIZ[1], [0, 1, 3]) and not is_ok(QUIZ[1], 0)

base = "<html><head><meta name='csrf-token' content='t'></head><body>{% block content %}{% endblock %}{% block scripts %}{% endblock %}</body></html>"
env = jinja2.Environment(loader=jinja2.DictLoader({'base.html': base, 'lesson.html': open(os.path.join(ROOT, 'templates/lesson.html')).read()}), autoescape=True)
env.globals['url_for'] = lambda e, **k: ('/static/' + k['filename']) if e == 'static' else '/x?' + '&'.join(f'{a}={b}' for a, b in k.items())
class O: pass
l = O(); l.id = 7; l.title = 'T'; l.order = 1; l.xp_reward = 10; l.content = '<p>hi</p>'; l.track = 'html'
html = env.get_template('lesson.html').render(lesson=l, progress=None, prev_lesson=None, next_lesson=None,
                                              track='html', quiz=QUIZ, practice=None, pass_mark=PASS)
page_file = os.path.join(tempfile.mkdtemp(), 'lesson.html')
open(page_file, 'w').write(html)

fails = []
def check(cond, msg):
    print(('  ok   ' if cond else '  FAIL ') + msg)
    if not cond: fails.append(msg)

def handler(route):
    body = json.loads(route.request.post_data)
    flags = [is_ok(q, body['answers'][i]) for i, q in enumerate(QUIZ)]
    score = round(100 * sum(flags) / len(QUIZ))
    route.fulfill(status=200, content_type='application/json', body=json.dumps(
        {'success': True, 'score': score, 'correct': sum(flags), 'total': len(QUIZ), 'passed': score >= PASS,
         'pass_mark': PASS, 'results': flags, 'xp_earned': 0, 'new_badges': [], 'leveled_up': False}))

with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.route('**/api/lesson/complete', handler)
    pg.route('**/static/**', lambda r: r.abort())
    pg.route('http://nexa.test/lesson', lambda r: r.fulfill(status=200, content_type='text/html', body=html))
    pg.goto('http://nexa.test/lesson')
    pg.wait_for_selector('#quizSection')

    hows = pg.locator('.quiz-how').all_inner_texts()
    check('ONE' in hows[0] and 'ONE' in hows[2], 'single questions say "Pick ONE answer"')
    check('2 answers' in hows[1], 'multi question says how many to pick')
    check(pg.locator('input[name=q1]').first.get_attribute('type') == 'checkbox', 'multi question uses checkboxes')

    # click to pick, click again to un-pick
    pg.locator('input[name=q0]').nth(1).locator('xpath=..').click()
    check(pg.locator('input[name=q0]:checked').count() == 1, 'clicking an option picks it')
    pg.locator('input[name=q0]').nth(1).locator('xpath=..').click()
    check(pg.locator('input[name=q0]:checked').count() == 0, 'clicking it again un-picks it')
    pg.locator('input[name=q0]').nth(2).locator('xpath=..').click()
    pg.click('.quiz-clear[data-q="0"]')
    check(pg.locator('input[name=q0]:checked').count() == 0, '"Clear my answer" works')

    # missing answer -> inline message, nothing submitted
    pg.click('#submitQuiz')
    check('Question 1' in pg.inner_text('#quizMsg'), 'missing answer shows an inline message')

    # fail: q0 wrong, q1 wrong, q2 right  (1/3 = 33% < 60)
    pg.locator('input[name=q0]').nth(2).locator('xpath=..').click()
    pg.locator('input[name=q1]').nth(0).locator('xpath=..').click()
    pg.locator('input[name=q2]').nth(0).locator('xpath=..').click()
    pg.click('#submitQuiz'); pg.wait_for_selector('#fb0', state='visible')
    check(pg.locator('input[name=q0]:checked').count() == 0 and pg.locator('input[name=q1]:checked').count() == 0, 'wrong answers are cleared')
    check(pg.locator('input[name=q2]:checked').count() == 1 and pg.locator('input[name=q2]').first.is_disabled(), 'right answer stays locked in')
    check(pg.locator('#q0 .quiz-opt.correct, #q1 .quiz-opt.correct').count() == 0, 'a failing attempt does not reveal the right answers to missed questions')
    check('Try Again' in pg.inner_text('#submitQuiz'), 'button says Try Again')
    check(pg.locator('#submitQuiz').is_enabled(), 'Try Again is clickable')

    # retry: answer q0 right, q1 with only one of two (still wrong) -> 2/3 = 67% passes at 60
    pg.locator('input[name=q0]').nth(1).locator('xpath=..').click()
    pg.locator('input[name=q1]').nth(0).locator('xpath=..').click()
    pg.click('#submitQuiz'); pg.wait_for_function("document.querySelector('#resultText')?.textContent.includes('Nice work')")
    check('Nice work' in pg.inner_text('#resultText'), 'two of three passes (pass mark %d)' % PASS)
    check(pg.locator('.quiz-opt.correct').count() >= 2, 'a passing attempt shows the right answers')
    check('The answer was' in pg.inner_text('#fb1'), 'the missed multi-answer question explains the answer')
    check(not errs, 'no page errors: %s' % errs)
    b.close()

print('\n%d failure(s)' % len(fails)); sys.exit(1 if fails else 0)
