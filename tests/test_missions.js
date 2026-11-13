// Runs every mission in a real browser: the starter must NOT pass, the solution MUST.
// usage: node tests/test_missions.js path/to/missions.json
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const missions = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const js = fs.readFileSync(path.join(__dirname, '../static/js/mission.js'), 'utf8');
(async () => {
  const browser = await chromium.launch();
  let fails = 0, steps = 0;
  const bad = (m) => { fails++; console.log('  FAIL', m); };
  for (const [key, mission] of Object.entries(missions)) {
    const page = await browser.newPage();
    await page.setContent('<html><body><div id="r"></div></body></html>');
    await page.addScriptTag({ content: js });
    await page.evaluate(() => { window.__perr = []; window.addEventListener('error', e => __perr.push(e.message)); });
    await page.evaluate(([m]) => { NexaMission.mount(document.getElementById('r'), m, { lessonId: 'T' }); }, [mission]);
    console.log(key, mission.title);
    if (mission.words && !(await page.locator('#r .nm-words').count())) bad(key + ' words panel missing');
    if (mission.worked) { await page.waitForTimeout(300); await page.locator('#r [data-act=start]').click(); }
    for (let i = 0; i < mission.steps.length; i++) {
      const s = mission.steps[i]; steps++;
      const tag = `${key} step ${i + 1} (${s.type})`;
      const root = page.locator('#r');
      if (s.type === 'code' || s.type === 'fix') {
        await page.waitForTimeout(150);
        await root.locator('[data-act=check]').click();
        await page.waitForTimeout(500);
        if (await root.locator('[data-act=next]').count()) bad(tag + ' starter already passes!');
        // set solution
        for (const [f, v] of Object.entries(s.solution)) await root.locator(`.nm-ed[data-f=${f}]`).fill(v);
        await root.locator('[data-act=check]').click();
        await page.waitForTimeout(700);
        const ok = await root.locator('[data-act=next]').count();
        if (!ok) {
          const lis = await root.locator('.nm-tests li.no span').allInnerTexts();
          bad(tag + ' solution fails: ' + lis.join(' | '));
          const m = await root.locator('[data-area=msg]').innerText(); console.log('   msg:', m);
        } else console.log('  ok', tag);
        if (ok) await root.locator('[data-act=next]').click();
        else break;
      } else if (s.type === 'predict') {
        await root.locator('#nmAns').fill('zzz definitely wrong');
        await root.locator('[data-act=check]').click();
        if (await root.locator('.nm-msg.good').count()) bad(tag + ' wrong answer accepted');
        const ans = Array.isArray(s.answer) ? s.answer[0] : s.answer;
        await root.locator('#nmAns').fill(ans);
        await root.locator('[data-act=check]').click();
        await page.waitForTimeout(500);
        if (!(await root.locator('.nm-msg.good').count())) { bad(tag + ' right answer rejected'); break; }
        // does the revealed run really print the first accepted answer? compare to iframe output
        const frame = page.frames().find(f => f !== page.mainFrame() && f.url() === 'about:srcdoc');
        const out = frame ? await frame.evaluate(() => (document.getElementById('out') || {}).textContent || '') : '';
        const vis = frame ? await frame.evaluate(() => document.body.innerText) : '';
        console.log('  ok', tag, '| real output:', JSON.stringify((out || vis).replace(/\s+/g, ' ').trim().slice(0, 60)));
        await root.locator('[data-area=next] button').click();
      } else if (s.type === 'anatomy') {
        const n = await root.locator('.nm-part').count();
        for (let k = 0; k < n; k++) await root.locator('.nm-part').nth(k).click();
        if (!(await root.locator('[data-area=next] button').count())) { bad(tag + ' exploring every part did not unlock Next'); break; }
        console.log('  ok', tag, '(' + n + ' parts)');
        await root.locator('[data-area=next] button').click();
      } else if (s.type === 'blank') {
        await page.waitForTimeout(150);
        await root.locator('[data-act=check]').click(); await page.waitForTimeout(500);
        if (await root.locator('[data-act=next]').count()) bad(tag + ' empty gaps already pass!');
        const gaps = root.locator('.nm-gap');
        if ((await gaps.count()) !== s.gaps_solution.length) bad(tag + ' gap count mismatch');
        for (let k = 0; k < s.gaps_solution.length; k++) await gaps.nth(k).fill(s.gaps_solution[k]);
        await root.locator('[data-act=check]').click(); await page.waitForTimeout(700);
        if (!(await root.locator('[data-act=next]').count())) { bad(tag + ' gap answers fail: ' + (await root.locator('.nm-tests li.no span').allInnerTexts()).join(' | ')); break; }
        console.log('  ok', tag);
        await root.locator('[data-act=next]').click();
      } else if (s.type === 'robot') {
        const tap = async (it) => { await root.locator(typeof it === 'object' ? `.nm-blk[data-r="${it.r}"]` : `.nm-blk[data-c=${it}]`).click(); };
        await tap('left'); await root.locator('[data-act=run]').click(); await page.waitForTimeout(900);
        if (await root.locator('[data-area=next] button').count()) bad(tag + ' a wrong program (Left) was accepted');
        await root.locator('[data-act=clear]').click();
        for (const it of s.solution) await tap(it);
        await root.locator('[data-act=run]').click();
        try { await root.locator('[data-area=next] button').waitFor({ timeout: 8000 }); console.log('  ok', tag); }
        catch (e) { bad(tag + ' correct program did not reach the star: ' + (await root.locator('[data-area=msg]').innerText())); break; }
        await root.locator('[data-area=next] button').click();
      } else if (s.type === 'order') {
        await root.locator('[data-act=check]').click();
        // bubble sort by moving lines
        const want = s.lines;
        for (let pass = 0; pass < 40; pass++) {
          const cur = await root.locator('.nm-line code').allInnerTexts();
          const idx = cur.findIndex((c, k) => c !== want[k]);
          if (idx < 0) break;
          const from = cur.findIndex((c, k) => k > idx && c === want[idx]);
          await root.locator('.nm-line').nth(from).locator('.nm-mv').first().click();
        }
        await root.locator('[data-act=check]').click();
        if (!(await root.locator('.nm-msg.good').count())) { bad(tag + ' order not accepted'); break; }
        console.log('  ok', tag);
        await root.locator('[data-area=next] button').click();
      }
    }
    const perr = await page.evaluate(() => __perr); if (perr.length) bad(key + ' errors in the Nexa page itself: ' + perr.join('; '));
    const done = await page.locator('#r .nm-done h3').innerText().catch(() => '');
    if (!done) bad(key + ' never reached the finish screen'); else console.log('  finished:', done);
    await page.close();
  }
  await browser.close();
  console.log(`\n${steps} steps, ${fails} failures`);
  process.exit(fails ? 1 : 0);
})();
