/**
 * Tests for the client-side auto-check logic used by the "Try It Live"
 * practice widget in templates/lesson.html (see checkPractice() there).
 *
 * This is plain Node with no framework/dependency, matching the rest of
 * this project's JS, which has no build step. Run with:
 *
 *   node tests/test_practice_checks.js
 *
 * NOTE: this file re-implements the same check logic as a pure function so
 * it can run outside a browser. If you change the matching logic inside
 * checkPractice() in templates/lesson.html, update runChecks() below to
 * match, or better, extract both into one shared function.
 */

function runChecks(html, js, checks, css = '') {
  const combined = (html + '\n' + css + '\n' + js).toLowerCase();
  for (const check of checks) {
    const needle = check.contains.toLowerCase();
    const count = combined.split(needle).length - 1;
    const minCount = check.min_count || 1;
    if (count < minCount) {
      return { pass: false, hint: check.hint };
    }
  }
  return { pass: true };
}

let failures = 0;
function assertEqual(actual, expected, label) {
  if (actual !== expected) {
    console.error(`FAIL: ${label} — expected ${expected}, got ${actual}`);
    failures++;
  } else {
    console.log(`ok   ${label}`);
  }
}

// --- Lists & Tables: needs at least 3 <li> ---
const listsChecks = [{ contains: '<li>', min_count: 3, hint: 'need 3 li' }];
assertEqual(
  runChecks('<ul>\n  <li>Pizza</li>\n  <li>Ice cream</li>\n</ul>', '', listsChecks).pass,
  false,
  'Lists & Tables: unsolved starter (only 2 <li>) must fail'
);
assertEqual(
  runChecks('<ul>\n  <li>Pizza</li>\n  <li>Ice cream</li>\n  <li>Fries</li>\n</ul>', '', listsChecks).pass,
  true,
  'Lists & Tables: 3 <li> items must pass'
);

// --- Functions: needs "function sayhi", "return", and sayhi( called (2 occurrences: def + call) ---
const functionsChecks = [
  { contains: 'function sayhi', hint: 'a' },
  { contains: 'return', hint: 'b' },
  { contains: 'sayhi(', min_count: 2, hint: 'c' },
];
assertEqual(
  runChecks('', 'function sayHi() {\n  // your code here\n}\n\n// now call your function inside an alert() below\n', functionsChecks).pass,
  false,
  'Functions: unsolved starter must fail (no return, no call)'
);
assertEqual(
  runChecks('', 'function sayHi() {\n  return "Hello, pal!";\n}\nalert(sayHi());', functionsChecks).pass,
  true,
  'Functions: a real solution (defined + returns + called) must pass'
);
assertEqual(
  runChecks('', 'function sayHi() {\n  return "Hello, pal!";\n}\n// forgot to call it', functionsChecks).pass,
  false,
  'Functions: defining but never calling the function must still fail'
);

// --- Loops & Arrays: needs "for" and "output", but the starter's own comment
//     must NOT accidentally satisfy "for" (this was a real bug caught while
//     building this feature — the starter comment used to say "write your
//     for loop here", which contains the substring "for" on its own). ---
const loopsChecks = [
  { contains: 'for', hint: 'a' },
  { contains: 'output', hint: 'b' },
];
assertEqual(
  runChecks('', 'let output = document.getElementById("output");\n\n// write your loop here — use output.innerHTML += ...\n', loopsChecks).pass,
  false,
  'Loops & Arrays: unsolved starter must fail (regression test for the "for" substring bug)'
);
assertEqual(
  runChecks('', 'let output = document.getElementById("output");\nfor (let i=1;i<=5;i++){ output.innerHTML += i + "<br>"; }', loopsChecks).pass,
  true,
  'Loops & Arrays: a real for-loop solution must pass'
);

// --- CSS: Flexbox Layout (uses the CSS field, added when the practice
//     widget was extended to support CSS-only challenges) ---
const flexChecks = [
  { contains: 'display', hint: 'a' },
  { contains: 'flex', hint: 'b' },
];
assertEqual(
  runChecks('<div class="row"></div>', '', flexChecks, '.row {\n  /* make these cards line up neatly in a row, evenly spaced */\n}').pass,
  false,
  'Flexbox: unsolved starter must fail'
);
assertEqual(
  runChecks('<div class="row"></div>', '', flexChecks, '.row { display: flex; }').pass,
  true,
  'Flexbox: display: flex must pass'
);

// --- JS: If Statements & Logic — regression test for the starter comment
//     accidentally containing "if" as a substring of "different" (the same
//     class of bug as the "for"/"different" case above, caught the same way:
//     simulate the unsolved starter and require it to fail). ---
const ifChecks = [
  { contains: 'if', hint: 'a' },
  { contains: 'else', hint: 'b' },
];
assertEqual(
  runChecks('', 'let score = 85;\n\n// look at the score and pop up a message that depends on how good it is\n', ifChecks).pass,
  false,
  'If Statements: unsolved starter must fail (regression test for the "if"-inside-"different" substring bug)'
);
assertEqual(
  runChecks('', 'let score = 85;\nif (score >= 90) { alert("A"); } else { alert("B"); }', ifChecks).pass,
  true,
  'If Statements: a real if/else solution must pass'
);

// --- JS: DOM — Changing the Page ---
const domChecks = [
  { contains: 'addeventlistener', hint: 'a' },
  { contains: 'textcontent', hint: 'b' },
];
assertEqual(
  runChecks('<h1 id="title">Click the button!</h1>\n<button id="btn">Change Me</button>',
             '// when the button is clicked, change the title\'s text and colour\n', domChecks).pass,
  false,
  'DOM: unsolved starter must fail'
);
assertEqual(
  runChecks('<h1 id="title">Click the button!</h1>\n<button id="btn">Change Me</button>',
             'btn.addEventListener("click", () => { title.textContent = "New"; });', domChecks).pass,
  true,
  'DOM: a real click handler that updates textContent must pass'
);

if (failures > 0) {
  console.error(`\n${failures} check(s) failed.`);
  process.exit(1);
} else {
  console.log('\nAll practice-check tests passed.');
}
