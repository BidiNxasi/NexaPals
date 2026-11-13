// New engine behaviour: error translation, hint fading, symbol bar, worked example, step events, mastery.
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path');
const all = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const js = fs.readFileSync(path.join(__dirname, '../static/js/mission.js'), 'utf8');
let bad = 0; const ok = (c, m) => { console.log(c ? 'ok  ' : 'FAIL', m); if (!c) bad++; };
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  // (pageerror is not asserted here: the test deliberately runs broken learner code inside the sandbox iframe)
  await p.setContent('<div id="r"></div>'); await p.addScriptTag({ content: js });
  // friendly errors
  const fe = await p.evaluate(() => [NexaMission.friendlyError('ReferenceError: foo is not defined'), NexaMission.friendlyError("Cannot set properties of null (setting 'textContent')"), NexaMission.friendlyError('SyntaxError: Unexpected token }'), NexaMission.friendlyError('weird')]);
  ok(/foo/.test(fe[0]) && /spelling/.test(fe[0]), 'not-defined error explained'); ok(/getElementById/.test(fe[1]), 'null element error explained'); ok(/bracket/.test(fe[2]), 'syntax error explained'); ok(/weird/.test(fe[3]), 'unknown error shown raw');
  // lesson with level 6: hint locked until 2 checks; worked example first; step events
  const m0 = all['lesson:javascript:6']; const m = { ...m0, steps: m0.steps.filter(s => s.type === 'code') }; // the three build-it steps
  await p.evaluate(([m]) => { window.EV = []; NexaMission.mount(document.getElementById('r'), m, { lessonId: 'f', level: 6, onStep: d => EV.push(d) }); }, [m]);
  ok(await p.locator('.nm-worked').count() === 1, 'worked example shown first');
  await p.locator('[data-act=start]').click();
  ok(await p.locator('.nm-sym button').count() >= 12, 'symbol bar present');
  const hint = p.locator('[data-act=hint]');
  ok(await hint.isDisabled(), 'hint locked before trying (level 6)');
  await p.locator('.nm-ed[data-f=js]').click(); await p.locator('.nm-sym button', { hasText: '{' }).first().click();
  ok((await p.locator('.nm-ed[data-f=js]').inputValue()).includes('{'), 'symbol key inserts into editor');
  await p.locator('[data-act=check]').click(); await p.waitForTimeout(500);
  ok(await hint.isDisabled(), 'hint still locked after 1 check');
  await p.locator('[data-act=check]').click(); await p.waitForTimeout(500);
  ok(await hint.isEnabled(), 'hint unlocked after 2 checks');
  // keyboard-less friendly error: break the JS
  await p.locator('.nm-ed[data-f=js]').fill('let x = ;'); await p.locator('[data-act=check]').click(); await p.waitForTimeout(600);
  ok(/bracket|missing/i.test(await p.locator('[data-area=msg]').innerText()), 'syntax error shown in kid language on the page');
  // finish all steps quickly with solutions (one step used show-me style = assisted)
  for (let i = 0; i < m.steps.length; i++) {
    await p.locator('.nm-ed[data-f=js]').fill(m.steps[i].solution.js); await p.locator('[data-act=check]').click(); await p.waitForTimeout(700); await p.locator('[data-act=next]').click();
  }
  const ev = await p.evaluate(() => EV);
  const done = ev.filter(e => !e.stuck);
  ok(done.length === 3 && ev.every(e => e.skill === 'state-game'), 'step events carry the skill: ' + done.length + ' completed');
  ok(ev.some(e => e.stuck && e.index === 0), 'stuck event emitted while struggling on step 1');
  ok(done[0].checks === 4 && done[0].hints === 0, 'first step recorded its 4 checks, 0 hints');
  ok(await p.locator('.nm-stat', { hasText: /Mastered|Solid|practising/ }).count() === 1, 'mastery chip on finish screen');
  // stuck event after 3 failed checks
  await p.evaluate(([m]) => { window.EV = []; document.getElementById('r').innerHTML = ''; NexaMission.mount(document.getElementById('r'), { ...m, worked: null }, { lessonId: 'g2', forceReplay: true, onStep: d => EV.push(d) }); }, [m]);
  for (let i = 0; i < 3; i++) { await p.locator('[data-act=check]').click(); await p.waitForTimeout(500); }
  const ev2 = await p.evaluate(() => EV);
  ok(ev2.length === 1 && ev2[0].stuck === true, 'one stuck event after 3 failed checks');
  ok(await p.locator('[data-act=show]').isEnabled(), 'Show me unlocked after 3 failures');
  await b.close(); process.exit(bad ? 1 : 0);
})();
