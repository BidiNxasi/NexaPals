// Cheating attempts that the OLD substring checker accepted. All must fail now.
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const missions = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const js = fs.readFileSync(path.join(__dirname, '../static/js/mission.js'), 'utf8');
const cases = [
  ['javascript:1', 0, { js: '// alert(myName + myAge)\nlet myName = "x";' }, 'alert only in a comment'],
  ['javascript:2', 0, { js: 'function grade(s){ return "Great"; }' }, 'hard-coded answer'],
  ['javascript:3', 0, { js: 'function twice(n){return 8;}\nfunction greet(n){return "Hello, Sam";}' }, 'hard-coded returns'],
  ['javascript:4', 0, { js: '// btn.addEventListener("click") textContent' }, 'keywords in comment'],
  ['javascript:5', 0, { js: '// for\nlet list=document.getElementById("list");list.innerHTML="<li>apple</li><li>banana</li><li>cherry</li>";' }, 'no real loop'],
  ['javascript:6', 2, { js: 'document.getElementById("msg").textContent="You win!";' }, 'win message always shown'],
  ['css:4', 0, { css: '/* display: flex */ .row{}' }, 'flex only in a comment'],
  ['html:1', 0, { html: '<h1>My name is ...</h1><p>hi</p>' }, 'dots left in heading'],
  ['capstone:javascript', 0, { js: 'document.getElementById("list").innerHTML="<li>Milk</li><li>Eggs</li>";' }, 'hard-coded list items'],
  ['capstone:javascript', 0, { js: 'document.getElementById("add").onclick=function(){var li=document.createElement("li");li.textContent=document.getElementById("item").value;document.getElementById("list").appendChild(li);};' }, 'adds empty items, no clear'],
  ['capstone:css', 0, { css: '/* display:flex; gap:10px; padding:20px; border-radius:9px; transition: all .3s; */' }, 'capstone rules only in a comment'],
  ['capstone:html', 0, { html: '<h1>Hi</h1><p>a</p><img src="x"><ul><li>1</li><li>2</li><li>3</li></ul><a href="#">x</a>' }, 'missing 2nd paragraph / alt / real link'],
  ['html:2', 1, { html: '<img src="" alt="">' }, 'empty src/alt'],
];
(async () => {
  const b = await chromium.launch(); let bad = 0;
  for (const [key, si, fields, why] of cases) {
    const p = await b.newPage(); const m0 = missions[key.startsWith('capstone') ? key : 'lesson:' + key]; const m = { ...m0, worked: null, steps: m0.steps.filter(s => !['anatomy', 'blank'].includes(s.type)) };
    await p.setContent('<div id="r"></div>'); await p.addScriptTag({ content: js });
    await p.evaluate(([m]) => NexaMission.mount(document.getElementById('r'), { ...m, steps: [m.steps[0]] }, { lessonId: 'c' }), [{ ...m, steps: [m.steps[si]] }]);
    for (const [f, v] of Object.entries(fields)) await p.locator(`.nm-ed[data-f=${f}]`).fill(v);
    await p.locator('[data-act=check]').click(); await p.waitForTimeout(600);
    const passed = await p.locator('[data-act=next]').count();
    console.log(passed ? 'LEAK ' : 'blocked', key, '-', why); if (passed) bad++;
    await p.close();
  }
  await b.close(); process.exit(bad ? 1 : 0);
})();
