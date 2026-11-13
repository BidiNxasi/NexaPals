"""Dump every mission variant (lessons, practice, capstones) to JSON for the browser test."""
import json, sys
sys.path.insert(0, '.')
import lesson_missions as lm
out = {}
for k in lm.MISSIONS: out['lesson:%s:%s' % k] = lm.build_mission(k)
for sk in lm.PRACTICE: out['practice:' + sk] = lm.practice_mission(sk)
for t, m in lm.CAPSTONES.items(): out['capstone:' + t] = m
out['intro'] = lm.INTRO
out['precode'] = lm.PRECODE
json.dump(out, open(sys.argv[1], 'w'))
print(len(out), 'missions')
