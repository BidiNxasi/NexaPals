// Drafts survive a refresh, Ctrl+Enter checks, and a passed step clears its draft.
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path');
const all = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const js = fs.readFileSync(path.join(__dirname, '../static/js/mission.js'), 'utf8');
let bad = 0; const ok = (c, m) => { console.log(c ? 'ok  ' : 'FAIL', m); if (!c) bad++; };
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  await p.route('**/*', r => { const u = new URL(r.request().url());
    if (u.pathname === '/t') return r.fulfill({ contentType: 'text/html', body: '<div id="r"></div>' });
    if (u.pathname === '/m.js') return r.fulfill({ contentType: 'application/javascript', body: js });
    r.fulfill({ status: 204, body: '' }); });
  const m0 = all['lesson:css:1']; const m = { ...m0, worked: null, steps: m0.steps.filter(s => s.type === 'code') };
  const mount = async () => { await p.goto('http://nexa.test/t'); await p.addScriptTag({ url: 'http://nexa.test/m.js' });
    await p.evaluate(m => NexaMission.mount(document.getElementById('r'), m, { lessonId: 'draft-test', forceReplay: true }), m); };
  await mount();
  await p.locator('.nm-ed[data-f=css]').fill('h1 { color: purple; }');
  await mount();
  ok((await p.locator('.nm-ed[data-f=css]').inputValue()) === 'h1 { color: purple; }', 'draft restored after reload');
  await p.locator('.nm-ed[data-f=css]').fill('h1 { color: purple; text-align: center; }');
  await p.locator('.nm-ed[data-f=css]').press('Control+Enter'); await p.waitForTimeout(700);
  ok(await p.locator('[data-act=next]').count() === 1, 'Ctrl+Enter ran the check and the step passed');
  await mount();
  ok((await p.locator('.nm-ed[data-f=css]').inputValue()).includes('/* style this heading'), 'draft cleared after the step passed (starter back)');
  await b.close(); process.exit(bad ? 1 : 0);
})();
