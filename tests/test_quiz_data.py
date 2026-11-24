"""Every built-in quiz must be sound: answer indexes in range, no duplicate options."""
import ast, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lesson_missions as lm

def test_seed_quizzes_are_sound():
    src = open(os.path.join(ROOT, 'app.py')).read()
    found = 0
    for m in re.finditer(r"'track': '(\w+)', 'order': (\d+),.*?'quiz_json': json\.dumps\((\[.*?\n        \])\)", src, re.S):
        quiz = ast.literal_eval(m.group(3)); key = (m.group(1), int(m.group(2)))
        for i, q in lm.QUIZ_FIXES.get(key, {}).items():
            quiz[i] = q
        assert lm.quiz_problems(quiz) == [], key
        found += 1
    assert found >= 15

def test_quiz_problems_catches_bad_keys():
    assert lm.quiz_problems([{"q": "a", "options": ["x", "y"], "answer": 2}])
    assert lm.quiz_problems([{"q": "a", "options": ["x", "y"], "answer": "1"}])
    assert lm.quiz_problems([{"q": "a", "options": ["x", "x"], "answer": 0}])
    assert lm.quiz_problems([{"q": "a", "options": ["x", "y", "z"], "answers": [0]}])
    assert not lm.quiz_problems([{"q": "a", "options": ["x", "y", "z"], "answers": [0, 2]}])
