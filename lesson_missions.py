"""Interactive missions for every Nexa Pals lesson.

Each mission is a list of steps (code / fix / predict / order). Code and fix
steps are verified by RUNNING the learner's code in a sandboxed iframe and
testing what it does (see static/js/mission.js), not by searching for words.

Key = (track, order). `apply_missions()` writes them into Lesson.practice_json.
"""
import json
import logging

def T(id, label, kind, **kw):
    d = {"id": id, "label": label, "kind": kind}
    d.update(kw)
    return d

MISSIONS = {}

# ───────────────────────────── HTML ─────────────────────────────
MISSIONS[("html", 1)] = {
    "title": "Build your profile page",
    "success_msg": "You wrote real HTML, put it in order, and predicted how browsers read it!",
    "steps": [
        {"type": "code",
         "prompt": "Replace the dots in the heading with your real name, then add a <code>&lt;p&gt;</code> paragraph with a sentence about yourself.",
         "starter_html": "<h1>My name is ...</h1>\n<!-- add your paragraph below -->",
         "tests": [
             T("h1", "A heading <h1> shows your name (no dots left)", "text", selector="h1", regex=r"^(?!.*\.\.\.)\s*\S{2,}"),
             T("p", "A paragraph <p> has a sentence of at least 3 words", "text", selector="p", regex=r"\S+\s+\S+\s+\S+"),
         ],
         "hints": ["Type your name between <code>&lt;h1&gt;</code> and <code>&lt;/h1&gt;</code>.",
                   "A paragraph looks like <code>&lt;p&gt;I love building games.&lt;/p&gt;</code>"],
         "solution": {"html": "<h1>My name is Thandi</h1>\n<p>I love building games and drawing robots.</p>"},
         "success_msg": "That is a real web page: one heading and one paragraph."},
        {"type": "order",
         "prompt": "Every page has the same skeleton. Drag these lines (with the arrows) into the order a browser expects.",
         "lines": ["<!DOCTYPE html>", "<html>", "<body>", "<h1>Hello!</h1>", "</body>", "</html>"],
         "hints": ["The first line tells the browser it is HTML.", "Tags close in the reverse order they opened."],
         "explain": "Tags nest like boxes: html contains body, body contains your content."},
        {"type": "predict", "lang": "html",
         "prompt": "Read the HTML. What exact words will the person see on the page?",
         "code": "<h2>Welcome</h2>\n<!-- <h2>Secret</h2> -->\n<p>Enjoy!</p>",
         "answer": ["Welcome Enjoy!", "welcome enjoy", "Welcome\nEnjoy!", "Welcome, Enjoy!", "Welcome and Enjoy!"],
         "hints": ["Text inside <code>&lt;!-- --&gt;</code> is a comment."],
         "explain": "Comments are notes for people. The browser skips them, so only Welcome and Enjoy! appear."},
    ],
}

MISSIONS[("html", 2)] = {
    "title": "Make links and pictures work",
    "success_msg": "Your links go somewhere and your images are accessible to everyone!",
    "steps": [
        {"type": "fix",
         "prompt": "This link goes nowhere. Fix it so it points to a website.",
         "starter_html": "<a>Visit Wikipedia</a>",
         "tests": [T("a", "The link has an href that is a real address", "attr", selector="a", attr="href", not_empty=True),
                   T("t", "The link text still says Visit Wikipedia", "text", selector="a", contains="Visit Wikipedia")],
         "hints": ["Links need an <code>href</code> attribute inside the opening tag.", "Try <code>&lt;a href=\"https://wikipedia.org\"&gt;</code>."],
         "solution": {"html": "<a href=\"https://wikipedia.org\">Visit Wikipedia</a>"}},
        {"type": "code",
         "prompt": "Add a picture. Use <code>&lt;img&gt;</code> with a <code>src</code> and an <code>alt</code> that describes it for people who cannot see it.",
         "starter_html": "<h2>My pet</h2>\n",
         "tests": [T("img", "An <img> tag exists", "exists", selector="img"),
                   T("src", "It has a src (where the picture lives)", "attr", selector="img", attr="src", not_empty=True),
                   T("alt", "It has alt text describing the picture", "attr", selector="img", attr="alt", not_empty=True)],
         "hints": ["<code>&lt;img src=\"cat.jpg\" alt=\"A grey cat\"&gt;</code>", "img has no closing tag."],
         "solution": {"html": "<h2>My pet</h2>\n<img src=\"cat.jpg\" alt=\"A grey cat sleeping on a sofa\">"}},
        {"type": "predict", "lang": "html",
         "prompt": "Which words can the person click?",
         "code": "<p>Read <a href=\"https://nexapals.example\">the lesson</a> now.</p>",
         "answer": ["the lesson", "lesson", "the lesson."],
         "explain": "Only the text between the opening and closing a tags is clickable."},
    ],
}

MISSIONS[("html", 3)] = {
    "title": "Organise information",
    "success_msg": "Lists and tables are how real websites organise everything!",
    "steps": [
        {"type": "code",
         "prompt": "Build a list of 3 favourite foods using <code>&lt;ul&gt;</code> and <code>&lt;li&gt;</code>.",
         "starter_html": "<h2>My favourite foods</h2>\n",
         "tests": [T("ul", "A <ul> list exists", "exists", selector="ul"),
                   T("li", "It has at least 3 <li> items inside", "count", selector="ul li", min=3),
                   T("txt", "Every item has real text", "text", selector="ul li", regex=r"\S{2,}")],
         "hints": ["Each item goes inside <code>&lt;li&gt;...&lt;/li&gt;</code>.", "All the li tags sit between <code>&lt;ul&gt;</code> and <code>&lt;/ul&gt;</code>."],
         "solution": {"html": "<h2>My favourite foods</h2>\n<ul>\n  <li>Pap</li>\n  <li>Chicken</li>\n  <li>Mango</li>\n</ul>"}},
        {"type": "code",
         "prompt": "Make a table with a header row (<code>&lt;th&gt;</code> for Name and Score) and at least 2 rows of data.",
         "starter_html": "<table>\n  \n</table>",
         "tests": [T("th", "At least 2 header cells <th>", "count", selector="table th", min=2),
                   T("rows", "At least 3 rows <tr> (1 header + 2 data)", "count", selector="table tr", min=3),
                   T("td", "At least 4 data cells <td>", "count", selector="table td", min=4)],
         "hints": ["A row is <code>&lt;tr&gt;</code>. Inside it, headers are <code>&lt;th&gt;</code> and data is <code>&lt;td&gt;</code>."],
         "solution": {"html": "<table>\n  <tr><th>Name</th><th>Score</th></tr>\n  <tr><td>Thandi</td><td>90</td></tr>\n  <tr><td>Sipho</td><td>85</td></tr>\n</table>"}},
        {"type": "predict", "lang": "html",
         "prompt": "How many numbered items will this list show? (type a number)",
         "code": "<ol>\n  <li>Wake up</li>\n  <li>Code</li>\n  <li>Sleep</li>\n</ol>",
         "answer": ["3", "three"],
         "explain": "ol numbers its items automatically: 1, 2, 3."},
    ],
}

MISSIONS[("html", 4)] = {
    "title": "Create a working sign-up form",
    "success_msg": "Your form is accessible, labelled, and ready for real users!",
    "steps": [
        {"type": "code",
         "prompt": "Build a form with a text box for a name (with a placeholder) and a submit button.",
         "starter_html": "<form>\n  <label>Your name:</label>\n  <input type=\"text\">\n  <br><br>\n  \n</form>",
         "tests": [T("txt", "A text input exists inside the form", "exists", selector="form input[type=text]"),
                   T("ph", "The text input has a placeholder", "attr", selector="input[type=text]", attr="placeholder", not_empty=True),
                   T("btn", "A submit button exists inside the form", "exists", selector="form input[type=submit], form button")],
         "hints": ["<code>&lt;input type=\"text\" placeholder=\"Type here\"&gt;</code>", "<code>&lt;input type=\"submit\" value=\"Send\"&gt;</code> or a <code>&lt;button&gt;</code>."],
         "solution": {"html": "<form>\n  <label>Your name:</label>\n  <input type=\"text\" placeholder=\"Type here\">\n  <br><br>\n  <input type=\"submit\" value=\"Send!\">\n</form>"}},
        {"type": "fix",
         "prompt": "A good form is easy to use: clicking the label should put the cursor in the box. Right now it does nothing. Fix it.",
         "starter_html": "<label for=\"username\">Username</label>\n<input type=\"text\" id=\"name\">",
         "tests": [T("focus", "Clicking the label puts the cursor in the input", "click", selector="label",
                     then=[T("f", "", "focused", selector="input")])],
         "hints": ["The label's <code>for</code> must match the input's <code>id</code> exactly.", "Change one of the two so they are the same word."],
         "solution": {"html": "<label for=\"name\">Username</label>\n<input type=\"text\" id=\"name\">"}},
        {"type": "predict", "lang": "html",
         "prompt": "Will this box show the word <code>Hello</code> as text the user can edit? Type yes or no.",
         "code": "<input type=\"text\" value=\"Hello\">",
         "answer": ["yes", "y"],
         "explain": "value sets what is already inside the box. The user can still edit it."},
    ],
}

# ───────────────────────────── CSS ─────────────────────────────
MISSIONS[("css", 1)] = {
    "title": "Style your first heading",
    "success_msg": "You controlled how a page looks with CSS rules!",
    "steps": [
        {"type": "code",
         "prompt": "Give the heading a colour (not black) and make it centered.",
         "starter_html": "<h1 id=\"title\">Hello!</h1>",
         "starter_css": "h1 {\n  /* style this heading */\n}",
         "tests": [T("c", "The heading is not black any more", "style", selector="h1", prop="color", not_equals="rgb(0, 0, 0)"),
                   T("a", "The heading is centered", "style", selector="h1", prop="text-align", equals="center")],
         "hints": ["Properties go inside the braces: <code>color: purple;</code>", "Add <code>text-align: center;</code> too."],
         "solution": {"css": "h1 {\n  color: purple;\n  text-align: center;\n}"}},
        {"type": "fix",
         "prompt": "This rule has a spelling mistake, so nothing happens. Find it and fix it so the paragraph turns blue.",
         "starter_html": "<p>I should be blue.</p>",
         "starter_css": "p {\n  colour: blue;\n}",
         "tests": [T("blue", "The paragraph is blue", "style", selector="p", prop="color", equals="rgb(0, 0, 255)")],
         "hints": ["CSS uses American spelling.", "The property is <code>color</code>."],
         "solution": {"css": "p {\n  color: blue;\n}"}},
        {"type": "order",
         "prompt": "Put this CSS rule back together.",
         "lines": ["p {", "  color: green;", "}"],
         "hints": ["The selector and opening brace come first."],
         "explain": "A rule = selector, then { declarations; }"},
    ],
}

MISSIONS[("css", 2)] = {
    "title": "Paint your page",
    "success_msg": "Colours and backgrounds are your superpower now!",
    "steps": [
        {"type": "code",
         "prompt": "Give the whole page a coloured background, and make the text white.",
         "starter_html": "<h2>Night mode</h2><p>Easy on the eyes.</p>",
         "starter_css": "body {\n  \n}",
         "tests": [T("bg", "The page background is not transparent", "style", selector="body", prop="background-color", not_equals="rgba(0, 0, 0, 0)"),
                   T("fg", "The text is white", "style", selector="p", prop="color", equals="rgb(255, 255, 255)")],
         "hints": ["<code>background-color: #1e3a5f;</code>", "<code>color: white;</code> on body is inherited by the text inside."],
         "solution": {"css": "body {\n  background-color: #1e3a5f;\n  color: white;\n}"}},
        {"type": "code",
         "prompt": "Make a badge: a <code>.badge</code> with a gradient background and rounded corners.",
         "starter_html": "<div class=\"badge\">Level 1</div>",
         "starter_css": ".badge {\n  display: inline-block;\n  padding: 10px 20px;\n  color: white;\n}",
         "tests": [T("g", "It has a gradient background", "style", selector=".badge", prop="background-image", contains="gradient"),
                   T("r", "Its corners are rounded", "style", selector=".badge", prop="border-top-left-radius", not_zero=True)],
         "hints": ["<code>background: linear-gradient(135deg, #FFB347, #9B7EDE);</code>", "<code>border-radius: 20px;</code>"],
         "solution": {"css": ".badge {\n  display: inline-block;\n  padding: 10px 20px;\n  color: white;\n  background: linear-gradient(135deg, #FFB347, #9B7EDE);\n  border-radius: 20px;\n}"}},
        {"type": "predict", "lang": "html",
         "prompt": "Which colour will the text be? (one word)",
         "html": "", "code": "<style>p { color: red; } p { color: blue; }</style><p>Which colour?</p>",
         "answer": ["blue"],
         "explain": "When two rules match equally, the LAST one wins. That is the 'cascade' in Cascading Style Sheets."},
    ],
}

MISSIONS[("css", 3)] = {
    "title": "Fix the squished text",
    "success_msg": "Spacing and type make pages readable. You have the eye for it!",
    "steps": [
        {"type": "code",
         "prompt": "Give the paragraph breathing room: add padding (at least 12px) and a lighter background so you can see it.",
         "starter_html": "<p>This text feels a bit squished against the edges.</p>",
         "starter_css": "p {\n  background: #eef3ff;\n}",
         "tests": [T("pad", "Padding is at least 12px on every side", "style", selector="p", prop="padding-left", min_px=12)],
         "hints": ["<code>padding: 16px;</code>"],
         "solution": {"css": "p {\n  background: #eef3ff;\n  padding: 16px;\n}"}},
        {"type": "code",
         "prompt": "Make the heading 32px, bold, and Arial.",
         "starter_html": "<h1>Big heading</h1>",
         "starter_css": "h1 {\n  \n}",
         "tests": [T("sz", "Font size is 32px", "style", selector="h1", prop="font-size", equals="32px"),
                   T("fam", "Font family is Arial", "style", selector="h1", prop="font-family", contains="arial")],
         "hints": ["<code>font-size: 32px;</code>", "<code>font-family: Arial, sans-serif;</code>"],
         "solution": {"css": "h1 {\n  font-size: 32px;\n  font-family: Arial, sans-serif;\n}"}},
        {"type": "predict", "lang": "html",
         "prompt": "<code>margin</code> is space OUTSIDE the box, <code>padding</code> is space INSIDE. If you add <code>padding: 20px</code> to a box that is 100px wide, is the text closer to or farther from the box edge? Type <em>farther</em> or <em>closer</em>.",
         "code": "<div style=\"padding:20px;background:#ddd\">Hi</div>", "answer": ["farther", "further"],
         "explain": "Padding pushes the content inward, away from the edge."},
    ],
}

MISSIONS[("css", 4)] = {
    "title": "Line things up with Flexbox",
    "success_msg": "Flexbox is how professionals lay out every modern page!",
    "steps": [
        {"type": "code",
         "prompt": "Make the three cards sit side by side in a row with space between them.",
         "starter_html": "<div class=\"row\">\n  <div class=\"card\">Games</div>\n  <div class=\"card\">Art</div>\n  <div class=\"card\">Robots</div>\n</div>",
         "starter_css": ".row {\n  \n}\n.card {\n  background: #9B7EDE;\n  color: white;\n  padding: 15px 25px;\n  border-radius: 16px;\n  font-weight: bold;\n}",
         "tests": [T("flex", "The row uses display: flex", "style", selector=".row", prop="display", equals="flex"),
                   T("space", "Cards are spread out with justify-content", "style", selector=".row", prop="justify-content", contains="space")],
         "hints": ["Put <code>display: flex;</code> on the PARENT (.row), not on the cards.", "Then add <code>justify-content: space-between;</code>."],
         "solution": {"css": ".row {\n  display: flex;\n  justify-content: space-between;\n}\n.card {\n  background: #9B7EDE;\n  color: white;\n  padding: 15px 25px;\n  border-radius: 16px;\n  font-weight: bold;\n}"}},
        {"type": "code",
         "prompt": "Centre the box in the middle of its container, both sideways and up/down.",
         "starter_html": "<div class=\"stage\"><div class=\"dot\">★</div></div>",
         "starter_css": ".stage {\n  height: 140px;\n  background: #eef3ff;\n}\n.dot {\n  font-size: 2rem;\n}",
         "tests": [T("d", "The stage is a flex container", "style", selector=".stage", prop="display", equals="flex"),
                   T("h", "Centred sideways (justify-content)", "style", selector=".stage", prop="justify-content", equals="center"),
                   T("v", "Centred up/down (align-items)", "style", selector=".stage", prop="align-items", equals="center")],
         "hints": ["Two properties centre things: <code>justify-content</code> and <code>align-items</code>."],
         "solution": {"css": ".stage {\n  height: 140px;\n  background: #eef3ff;\n  display: flex;\n  justify-content: center;\n  align-items: center;\n}\n.dot {\n  font-size: 2rem;\n}"}},
        {"type": "predict", "lang": "html",
         "prompt": "With <code>flex-direction: column</code>, will the cards sit <em>side by side</em> or <em>stacked</em>? (one word)",
         "code": "<div style=\"display:flex;flex-direction:column\"><div>A</div><div>B</div></div>",
         "answer": ["stacked", "stack", "column", "on top of each other", "vertical", "vertically"],
         "explain": "column turns the main direction vertical, so items stack."},
    ],
}

MISSIONS[("css", 5)] = {
    "title": "Bring it to life",
    "success_msg": "Smooth movement makes a site feel professional!",
    "steps": [
        {"type": "code",
         "prompt": "Hovering already makes the ball grow, but it snaps. Add a transition so it grows smoothly (over at least 0.2 seconds).",
         "starter_html": "<div class=\"ball\"></div>",
         "starter_css": ".ball {\n  width: 50px;\n  height: 50px;\n  background: #9B7EDE;\n  border-radius: 50%;\n  margin: 40px auto;\n}\n.ball:hover {\n  transform: scale(1.3);\n}",
         "tests": [T("t", "The ball has a transition lasting at least 0.2s", "style", selector=".ball", prop="transition-duration", min_s=0.2)],
         "hints": ["<code>transition: transform 0.3s;</code> goes on .ball, not on :hover."],
         "solution": {"css": ".ball {\n  width: 50px;\n  height: 50px;\n  background: #9B7EDE;\n  border-radius: 50%;\n  margin: 40px auto;\n  transition: transform 0.3s;\n}\n.ball:hover {\n  transform: scale(1.3);\n}"}},
        {"type": "code",
         "prompt": "Make the ball pulse forever. Create a <code>@keyframes pulse</code> that grows it and back, then apply it with <code>animation</code>.",
         "starter_html": "<div class=\"ball\"></div>",
         "starter_css": ".ball {\n  width: 50px;\n  height: 50px;\n  background: #FFB347;\n  border-radius: 50%;\n  margin: 40px auto;\n}",
         "tests": [T("k", "You defined @keyframes pulse", "code_has", text="@keyframes pulse", lang="css"),
                   T("n", "The ball uses the animation named pulse", "style", selector=".ball", prop="animation-name", equals="pulse"),
                   T("i", "It repeats forever (infinite)", "style", selector=".ball", prop="animation-iteration-count", equals="infinite")],
         "hints": ["<code>@keyframes pulse { 0% {transform: scale(1);} 50% {transform: scale(1.4);} 100% {transform: scale(1);} }</code>",
                   "Then on .ball: <code>animation: pulse 1.5s infinite;</code>"],
         "solution": {"css": ".ball {\n  width: 50px;\n  height: 50px;\n  background: #FFB347;\n  border-radius: 50%;\n  margin: 40px auto;\n  animation: pulse 1.5s infinite;\n}\n@keyframes pulse {\n  0% { transform: scale(1); }\n  50% { transform: scale(1.4); }\n  100% { transform: scale(1); }\n}"}},
        {"type": "order",
         "prompt": "Rebuild the keyframes block.",
         "lines": ["@keyframes spin {", "  from { transform: rotate(0deg); }", "  to { transform: rotate(360deg); }", "}"],
         "explain": "from is the start, to is the end; the browser fills in everything between."},
    ],
}

# ───────────────────────────── JavaScript ─────────────────────────────
MISSIONS[("javascript", 1)] = {
    "title": "Make the computer remember",
    "success_msg": "Variables are the memory of every program you will ever write!",
    "steps": [
        {"type": "code",
         "prompt": "Change <code>myName</code> to your real name, then pop up an <code>alert</code> that includes both your name and your age.",
         "starter_js": "let myName = \"Your name here\";\nlet myAge = 12;\n\n// pop up a message with your name and age\n",
         "tests": [T("a", "An alert pops up", "alert", min=1),
                   T("n", "It shows YOUR name, not the placeholder", "alert", not_contains="your name here"),
                   T("g", "It shows the age 12 (use the variable)", "alert", contains="12"),
                   T("e", "No errors", "no_errors")],
         "hints": ["Join text and variables with +: <code>alert(\"Hi \" + myName)</code>", "Use <code>alert(myName + \" is \" + myAge)</code>"],
         "solution": {"js": "let myName = \"Thandi\";\nlet myAge = 12;\nalert(myName + \" is \" + myAge);"}},
        {"type": "fix",
         "prompt": "A bug! We want to show next year's age (13) but it shows something strange. Fix it.",
         "starter_js": "let age = \"12\";\nlet next = age + 1;\nalert(next);",
         "tests": [T("a", "The alert says 13", "alert", contains="13"),
                   T("b", "It does not say 121", "alert", not_contains="121")],
         "hints": ["Quotes make \"12\" a piece of text, so + joins text.", "Remove the quotes so 12 is a number."],
         "solution": {"js": "let age = 12;\nlet next = age + 1;\nalert(next);"}},
        {"type": "predict", "lang": "js",
         "prompt": "What will be printed?",
         "code": "let a = 5;\nlet b = 3;\na = a + b;\nconsole.log(a);",
         "answer": ["8"],
         "explain": "a is changed to 5 + 3, so it holds 8."},
    ],
}

MISSIONS[("javascript", 2)] = {
    "title": "Teach code to decide",
    "success_msg": "Your code makes decisions. That is the heart of programming!",
    "steps": [
        {"type": "code",
         "prompt": "Write a function <code>grade(score)</code> that RETURNS <code>\"Great\"</code> for 90 or more, <code>\"Good\"</code> for 50 or more, otherwise <code>\"Try again\"</code>. We will test it with different scores.",
         "starter_js": "function grade(score) {\n  \n}",
         "tests": [T("a", "grade(95) gives Great", "call", fn="grade", args=[95], returns="Great"),
                   T("b", "grade(70) gives Good", "call", fn="grade", args=[70], returns="Good"),
                   T("c", "grade(20) gives Try again", "call", fn="grade", args=[20], returns="Try again"),
                   T("d", "grade(90) gives Great (edge case)", "call", fn="grade", args=[90], returns="Great")],
         "hints": ["Check the biggest first: <code>if (score >= 90) { return \"Great\"; }</code>", "Then <code>else if (score >= 50)</code>, then a plain <code>else</code>."],
         "solution": {"js": "function grade(score) {\n  if (score >= 90) {\n    return \"Great\";\n  } else if (score >= 50) {\n    return \"Good\";\n  } else {\n    return \"Try again\";\n  }\n}"}},
        {"type": "predict", "lang": "js",
         "prompt": "Which word is printed?",
         "code": "let x = 7;\nif (x > 10) {\n  console.log(\"big\");\n} else if (x > 5) {\n  console.log(\"medium\");\n} else {\n  console.log(\"small\");\n}",
         "answer": ["medium"],
         "explain": "7 is not above 10, but it is above 5, so the middle branch runs."},
        {"type": "order",
         "prompt": "Put this decision in order.",
         "lines": ["let temp = 30;", "if (temp > 25) {", "  console.log(\"hot\");", "} else {", "  console.log(\"cool\");", "}"],
         "explain": "if (...) { } else { } always keeps this shape."},
    ],
}

MISSIONS[("javascript", 3)] = {
    "title": "Write your own tools",
    "success_msg": "Functions let you build once and reuse forever!",
    "steps": [
        {"type": "code",
         "prompt": "Write <code>twice(n)</code> that returns n times 2, and <code>greet(name)</code> that returns <code>\"Hello, \"</code> followed by the name.",
         "starter_js": "function twice(n) {\n  \n}\n\nfunction greet(name) {\n  \n}",
         "tests": [T("a", "twice(4) returns 8", "call", fn="twice", args=[4], returns="8"),
                   T("b", "twice(10) returns 20", "call", fn="twice", args=[10], returns="20"),
                   T("c", "greet(\"Sam\") returns Hello, Sam", "call", fn="greet", args=["Sam"], returns="Hello, Sam")],
         "hints": ["Functions give answers back with <code>return</code>.", "<code>return \"Hello, \" + name;</code>"],
         "solution": {"js": "function twice(n) {\n  return n * 2;\n}\n\nfunction greet(name) {\n  return \"Hello, \" + name;\n}"}},
        {"type": "fix",
         "prompt": "This function calculates the answer but never hands it back. Fix <code>add</code>.",
         "starter_js": "function add(a, b) {\n  a + b;\n}",
         "tests": [T("a", "add(2, 3) returns 5", "call", fn="add", args=[2, 3], returns="5"),
                   T("b", "add(10, 5) returns 15", "call", fn="add", args=[10, 5], returns="15")],
         "hints": ["Without <code>return</code>, the answer is thrown away."],
         "solution": {"js": "function add(a, b) {\n  return a + b;\n}"}},
        {"type": "predict", "lang": "js",
         "prompt": "What will be printed?",
         "code": "function square(n) {\n  return n * n;\n}\nconsole.log(square(4));",
         "answer": ["16"],
         "explain": "square(4) returns 4 * 4 = 16."},
    ],
}

MISSIONS[("javascript", 4)] = {
    "title": "Make the page respond",
    "success_msg": "You just changed a web page with JavaScript, live!",
    "steps": [
        {"type": "code",
         "prompt": "When the button is clicked, change the heading's text. We will actually click your button to test it.",
         "starter_html": "<h1 id=\"title\">Click the button!</h1>\n<button id=\"btn\">Change Me</button>",
         "starter_js": "// find the elements, then listen for a click\n",
         "tests": [T("c", "Clicking #btn changes the heading", "changes_on_click", click="#btn", watch="#title", what="text", times=1),
                   T("e", "No errors", "no_errors")],
         "hints": ["<code>let btn = document.getElementById(\"btn\");</code>", "<code>btn.addEventListener(\"click\", function () { ... });</code>", "Inside, set <code>title.textContent = \"...\"</code>"],
         "solution": {"js": "let btn = document.getElementById(\"btn\");\nlet title = document.getElementById(\"title\");\nbtn.addEventListener(\"click\", function () {\n  title.textContent = \"You did it!\";\n});"}},
        {"type": "code",
         "prompt": "Build a dark-mode switch: clicking the button should add the class <code>dark</code> to the body, and clicking again should remove it.",
         "starter_html": "<button id=\"toggle\">Toggle dark mode</button>\n<p>Hello there.</p>",
         "starter_css": "body.dark { background: #1e3a5f; color: white; }",
         "starter_js": "",
         "tests": [T("on", "One click adds body.dark", "click", selector="#toggle", then=[T("x", "", "exists", selector="body.dark")]),
                   T("off", "A second click removes it", "click", selector="#toggle", then=[T("y", "", "count", selector="body.dark", equals=0)])],
         "hints": ["<code>document.body.classList.toggle(\"dark\")</code> does both jobs."],
         "solution": {"js": "document.getElementById(\"toggle\").addEventListener(\"click\", function () {\n  document.body.classList.toggle(\"dark\");\n});"}},
        {"type": "predict", "lang": "js",
         "prompt": "After this JavaScript runs, what does the paragraph say?",
         "html": "<p id=\"t\">Old</p>",
         "code": "document.getElementById(\"t\").textContent = \"New\";",
         "answer": ["New"], "explain": "textContent replaces whatever text was there."},
    ],
}

MISSIONS[("javascript", 5)] = {
    "title": "Repeat yourself (the smart way)",
    "success_msg": "Loops let ten lines of work become one!",
    "steps": [
        {"type": "code",
         "prompt": "Use a loop to turn every fruit in the array into a list item inside <code>#list</code>. Add a fourth fruit and it should still work.",
         "starter_html": "<ul id=\"list\"></ul>",
         "starter_js": "let fruits = [\"apple\", \"banana\", \"cherry\"];\nlet list = document.getElementById(\"list\");\n\n// loop over fruits and add one <li> for each\n",
         "tests": [T("n", "The list has one <li> per fruit (3)", "count", selector="#list li", equals=3),
                   T("t", "The items show the fruit names", "text", selector="#list li", contains="banana"),
                   T("l", "You used a loop (for / forEach / while)", "code_has", regex=r"\b(for|forEach|while)\b", lang="js"),
                   T("e", "No errors", "no_errors")],
         "hints": ["<code>for (let i = 0; i &lt; fruits.length; i++) { ... }</code>", "Inside: <code>let li = document.createElement(\"li\"); li.textContent = fruits[i]; list.appendChild(li);</code>"],
         "solution": {"js": "let fruits = [\"apple\", \"banana\", \"cherry\"];\nlet list = document.getElementById(\"list\");\nfor (let i = 0; i < fruits.length; i++) {\n  let li = document.createElement(\"li\");\n  li.textContent = fruits[i];\n  list.appendChild(li);\n}"}},
        {"type": "code",
         "prompt": "Write <code>sumAll(numbers)</code> that adds up every number in an array and returns the total. We will test several arrays, including an empty one.",
         "starter_js": "function sumAll(numbers) {\n  \n}",
         "tests": [T("a", "sumAll([1, 2, 3, 4]) is 10", "call", fn="sumAll", args=[[1, 2, 3, 4]], returns="10"),
                   T("b", "sumAll([5]) is 5", "call", fn="sumAll", args=[[5]], returns="5"),
                   T("c", "sumAll([]) is 0", "call", fn="sumAll", args=[[]], returns="0")],
         "hints": ["Start with <code>let total = 0;</code>", "Loop through, doing <code>total = total + numbers[i];</code>, then <code>return total;</code>"],
         "solution": {"js": "function sumAll(numbers) {\n  let total = 0;\n  for (let i = 0; i < numbers.length; i++) {\n    total = total + numbers[i];\n  }\n  return total;\n}"}},
        {"type": "predict", "lang": "js",
         "prompt": "What numbers are printed, in order? (separate with spaces)",
         "code": "for (let i = 0; i < 3; i++) {\n  console.log(i);\n}",
         "answer": ["0 1 2", "0,1,2", "0, 1, 2", "012"],
         "explain": "i starts at 0 and the loop stops before it reaches 3. Arrays also start counting at 0."},
    ],
}

MISSIONS[("javascript", 6)] = {
    "title": "Build the clicker game",
    "success_msg": "You built a real game with state, events, and win conditions!",
    "steps": [
        {"type": "code",
         "prompt": "Make the counter work: each click on the button adds 1 and shows the new number. We will click it three times to test.",
         "starter_html": "<h1 id=\"countDisplay\">0</h1>\n<button id=\"clickBtn\">Click me!</button>",
         "starter_js": "let count = 0;\nlet countDisplay = document.getElementById(\"countDisplay\");\nlet clickBtn = document.getElementById(\"clickBtn\");\n\n// when clickBtn is clicked: add 1 to count and show it\n",
         "tests": [T("s", "It starts at 0", "text", selector="#countDisplay", equals="0"),
                   T("c", "After 3 clicks it shows 3", "click", selector="#clickBtn", times=3, then=[T("x", "", "text", selector="#countDisplay", equals="3")]),
                   T("e", "No errors", "no_errors")],
         "hints": ["<code>clickBtn.addEventListener(\"click\", function () { ... });</code>", "Inside: <code>count = count + 1; countDisplay.textContent = count;</code>"],
         "solution": {"js": "let count = 0;\nlet countDisplay = document.getElementById(\"countDisplay\");\nlet clickBtn = document.getElementById(\"clickBtn\");\nclickBtn.addEventListener(\"click\", function () {\n  count = count + 1;\n  countDisplay.textContent = count;\n});"}},
        {"type": "code",
         "prompt": "Add a Reset button (<code>#reset</code>). After clicking the game button twice and then Reset, the counter must go back to 0.",
         "starter_html": "<h1 id=\"countDisplay\">0</h1>\n<button id=\"clickBtn\">Click me!</button>\n<button id=\"reset\">Reset</button>",
         "starter_js": "let count = 0;\nlet countDisplay = document.getElementById(\"countDisplay\");\nlet clickBtn = document.getElementById(\"clickBtn\");\nclickBtn.addEventListener(\"click\", function () {\n  count = count + 1;\n  countDisplay.textContent = count;\n});\n\n// make #reset put the count back to 0\n",
         "tests": [T("r", "Click twice then Reset gives 0", "click", selector="#clickBtn", times=2,
                     then=[T("m", "", "text", selector="#countDisplay", equals="2"),
                           T("z", "", "click", selector="#reset", then=[T("q", "", "text", selector="#countDisplay", equals="0")])]),
                   T("e", "No errors", "no_errors")],
         "hints": ["Reset needs its own listener.", "Set <code>count = 0</code> AND update the display."],
         "solution": {"js": "let count = 0;\nlet countDisplay = document.getElementById(\"countDisplay\");\nlet clickBtn = document.getElementById(\"clickBtn\");\nclickBtn.addEventListener(\"click\", function () {\n  count = count + 1;\n  countDisplay.textContent = count;\n});\ndocument.getElementById(\"reset\").addEventListener(\"click\", function () {\n  count = 0;\n  countDisplay.textContent = count;\n});"}},
        {"type": "code",
         "prompt": "Add a win condition! Once the count reaches 10 or more, the message <code>#msg</code> must say <strong>You win!</strong>. Before that it must not.",
         "starter_html": "<h1 id=\"countDisplay\">0</h1>\n<p id=\"msg\"></p>\n<button id=\"clickBtn\">Click me!</button>",
         "starter_js": "let count = 0;\nlet countDisplay = document.getElementById(\"countDisplay\");\nlet msg = document.getElementById(\"msg\");\nlet clickBtn = document.getElementById(\"clickBtn\");\nclickBtn.addEventListener(\"click\", function () {\n  count = count + 1;\n  countDisplay.textContent = count;\n  // check for the win here\n});",
         "tests": [T("n", "No win message at the start", "text", selector="#msg", not_contains="win"),
                   T("w", "After 10 clicks it says You win!", "click", selector="#clickBtn", times=10, then=[T("y", "", "text", selector="#msg", contains="you win")]),
                   T("e", "No errors", "no_errors")],
         "hints": ["Use an if inside the click handler: <code>if (count >= 10) { ... }</code>", "<code>msg.textContent = \"You win!\";</code>"],
         "solution": {"js": "let count = 0;\nlet countDisplay = document.getElementById(\"countDisplay\");\nlet msg = document.getElementById(\"msg\");\nlet clickBtn = document.getElementById(\"clickBtn\");\nclickBtn.addEventListener(\"click\", function () {\n  count = count + 1;\n  countDisplay.textContent = count;\n  if (count >= 10) {\n    msg.textContent = \"You win!\";\n  }\n});"}},
    ],
}


# ───────────────────────── skills, worked examples ─────────────────────────
SKILL_BY_LESSON = {
    ("html", 1): "html-structure", ("html", 2): "links-media", ("html", 3): "lists-tables", ("html", 4): "forms",
    ("css", 1): "css-selectors", ("css", 2): "color", ("css", 3): "spacing-type", ("css", 4): "flexbox", ("css", 5): "animation",
    ("javascript", 1): "variables", ("javascript", 2): "conditionals", ("javascript", 3): "functions",
    ("javascript", 4): "dom-events", ("javascript", 5): "loops-arrays", ("javascript", 6): "state-game",
}
SKILL_LABELS = {
    "html-structure": "HTML structure", "links-media": "Links & images", "lists-tables": "Lists & tables", "forms": "Forms",
    "css-selectors": "CSS rules", "color": "Colour", "spacing-type": "Spacing & text", "flexbox": "Flexbox", "animation": "Animation",
    "variables": "Variables", "conditionals": "If / else", "functions": "Functions",
    "dom-events": "Clicks & the page", "loops-arrays": "Loops & arrays", "state-game": "Game logic",
}
LESSON_BY_SKILL = {v: k for k, v in SKILL_BY_LESSON.items()}

WORKED = {
    ("html", 1): {"title": "Watch one first", "explain": "Here is a finished page. The <code>h2</code> is the big title and <code>p</code> is a sentence. Your turn comes next.",
                  "html": "<h2>Hi, I'm Ayanda</h2>\n<p>I like football and drawing.</p>"},
    ("html", 2): {"explain": "A link needs <code>href</code> (where it goes). A picture needs <code>src</code> (the file) and <code>alt</code> (words for people who cannot see it). The picture file is missing here, so you see the alt words.",
                  "html": "<a href=\"https://wikipedia.org\">Read more</a>\n<br>\n<img src=\"missing.png\" alt=\"A red kite in the sky\">"},
    ("html", 3): {"explain": "<code>ul</code> makes bullets, each item is an <code>li</code>. A table is rows (<code>tr</code>) made of cells: <code>th</code> for headings, <code>td</code> for data.",
                  "html": "<ul><li>Pap</li><li>Mango</li></ul>\n<table border=\"1\"><tr><th>Name</th><th>Score</th></tr><tr><td>Sam</td><td>90</td></tr></table>"},
    ("html", 4): {"explain": "Click the word <strong>Name</strong> in the result. The cursor jumps into the box, because the label's <code>for</code> matches the input's <code>id</code>.",
                  "html": "<label for=\"nm\">Name</label>\n<input id=\"nm\" type=\"text\" placeholder=\"Type here\">"},
    ("css", 1): {"explain": "A CSS rule has a selector (<code>h1</code>), then properties inside braces. This one turns every h1 teal and centers it.",
                 "html": "<h1>Hello!</h1>", "css": "h1 {\n  color: teal;\n  text-align: center;\n}"},
    ("css", 2): {"explain": "<code>background-color</code> paints behind things and <code>color</code> paints the text. A gradient mixes two colours.",
                 "html": "<h2>Night mode</h2>", "css": "body {\n  background-color: #1e3a5f;\n  color: white;\n}\nh2 {\n  background: linear-gradient(90deg, #FFB347, #9B7EDE);\n}"},
    ("css", 3): {"explain": "<code>padding</code> is space inside the box, around the text. Compare the two paragraphs.",
                 "html": "<p class=\"a\">Squished</p>\n<p class=\"b\">Breathing room</p>", "css": "p { background: #eef3ff; }\n.b { padding: 20px; font-size: 20px; }"},
    ("css", 4): {"explain": "<code>display: flex</code> goes on the PARENT. Its children line up in a row, and <code>justify-content</code> spaces them.",
                 "html": "<div class=\"row\"><div>A</div><div>B</div><div>C</div></div>", "css": ".row { display: flex; justify-content: space-around; }\n.row div { background: #9B7EDE; color: white; padding: 12px 20px; border-radius: 12px; }"},
    ("css", 5): {"explain": "Hover over the ball. The <code>transition</code> makes it grow smoothly instead of snapping.",
                 "html": "<div class=\"ball\"></div>", "css": ".ball { width: 50px; height: 50px; border-radius: 50%; background: #FFB347; margin: 30px auto; transition: transform 0.4s; }\n.ball:hover { transform: scale(1.5); }"},
    ("javascript", 1): {"explain": "A variable is a labelled box. Change what is inside and the message changes too.",
                        "html": "<p id=\"o\"></p>", "js": "let name = \"Sam\";\nlet age = 12;\ndocument.getElementById(\"o\").textContent = name + \" is \" + age;"},
    ("javascript", 2): {"explain": "The computer checks the condition. If it is true it runs the first block, otherwise the <code>else</code> block.",
                        "html": "<p id=\"o\"></p>", "js": "let score = 72;\nif (score >= 50) {\n  document.getElementById(\"o\").textContent = \"Pass\";\n} else {\n  document.getElementById(\"o\").textContent = \"Try again\";\n}"},
    ("javascript", 3): {"explain": "A function packs steps under a name. <code>return</code> hands the answer back to whoever called it.",
                        "html": "<p id=\"o\"></p>", "js": "function greet(name) {\n  return \"Hello, \" + name;\n}\ndocument.getElementById(\"o\").textContent = greet(\"Lerato\");"},
    ("javascript", 4): {"explain": "Click the button in the result. The page listens for a click, then JavaScript changes the text.",
                        "html": "<p id=\"t\">Before</p>\n<button id=\"b\">Press</button>", "js": "document.getElementById(\"b\").addEventListener(\"click\", function () {\n  document.getElementById(\"t\").textContent = \"After!\";\n});"},
    ("javascript", 5): {"explain": "A loop repeats the same steps for every item in the array, so you write the steps once.",
                        "html": "<ul id=\"l\"></ul>", "js": "let pets = [\"cat\", \"dog\", \"fish\"];\nfor (let i = 0; i < pets.length; i++) {\n  let li = document.createElement(\"li\");\n  li.textContent = pets[i];\n  document.getElementById(\"l\").appendChild(li);\n}"},
    ("javascript", 6): {"explain": "A game remembers things in variables (<code>count</code>). Each click changes the variable, then the page is updated to match. Click it!",
                        "html": "<h2 id=\"c\">0</h2><button id=\"b\">+1</button>", "js": "let count = 0;\ndocument.getElementById(\"b\").addEventListener(\"click\", function () {\n  count = count + 1;\n  document.getElementById(\"c\").textContent = count;\n});"},
}


# Plain-language glossary shown in each mission ("Code words"). Definitions may use simple HTML.
WORDS = {
    ("html", 1): [["Tag", "A label in angle brackets, like &lt;h1&gt;, that tells the browser what something is."], ["Element", "A tag plus what is inside it: &lt;p&gt;Hello&lt;/p&gt;."], ["Comment", "A note for people. The browser ignores it. It looks like &lt;!-- note --&gt;."]],
    ("html", 2): [["href", "The address a link goes to."], ["src", "Where a picture file lives."], ["alt text", "Words that describe a picture for people who cannot see it."]],
    ("html", 3): [["List item (li)", "One bullet or number in a list."], ["Table row (tr)", "One horizontal line of a table."], ["th / td", "A heading cell / a data cell in a table."]],
    ("html", 4): [["Form", "A page area where people type or choose things."], ["Input", "A box, checkbox or button inside a form."], ["id", "A unique name for one element. A label uses it to find its input."]],
    ("css", 1): [["Selector", "Says WHICH things to style, like h1."], ["Property", "WHAT to change, like color."], ["Value", "The new setting, like purple."]],
    ("css", 2): [["Hex colour", "A colour written as # and six letters or numbers, like #1e3a5f."], ["Gradient", "A colour that smoothly blends into another."]],
    ("css", 3): [["Padding", "Space INSIDE a box, around the text."], ["Margin", "Space OUTSIDE a box, pushing other things away."], ["px", "Pixels: tiny dots on the screen."]],
    ("css", 4): [["Flexbox", "A way to line up items in a row or column."], ["Parent", "The element that holds other elements."], ["Child", "An element inside another one."]],
    ("css", 5): [["Transition", "Makes a change happen smoothly over time."], ["Keyframes", "The steps of an animation: where it starts, what it does, where it ends."]],
    ("javascript", 1): [["Variable", "A labelled box that stores a value, like a name or a number."], ["let", "The word that makes a new variable."], ["String", "Text in quotes, like \"Sam\"."]],
    ("javascript", 2): [["Condition", "A question the computer answers with true or false, like score &gt;= 50."], ["if / else", "If the condition is true do one thing, otherwise do another."]],
    ("javascript", 3): [["Function", "A named set of steps you can use again and again."], ["Argument", "Information you give a function, like the name in greet(\"Sam\")."], ["return", "Hands an answer back from a function."]],
    ("javascript", 4): [["DOM", "The page as JavaScript sees it, so JavaScript can change it."], ["Event", "Something that happens, like a click."], ["Listener", "Code that waits for an event, then runs."]],
    ("javascript", 5): [["Array", "A list of things in order, like [\"cat\", \"dog\"]."], ["Index", "An item's position. The first item is 0."], ["Loop", "Repeats steps for every item."]],
    ("javascript", 6): [["State", "What the program remembers right now, like the score."], ["Win condition", "The rule that decides when the player wins."]],
}


# ───────────────────────── "Learn it first" steps: explore, then fill gaps, then build ─────────────────────────
import re as _re
Y, B, P, G, R_ = "#FFB347", "#7fb4ff", "#c4adee", "#7fe0b0", "#ff9b9b"


def part(t, k=None, e="", c=None):
    return {"t": t, "k": k, "e": e, "c": c} if k else {"t": t}


def anatomy(prompt, parts, success="You know what every part does."):
    return {"type": "anatomy", "prompt": prompt, "parts": parts, "success_msg": success}


def blank(prompt, template, gaps, tests, hints, success=None):
    it = iter(gaps)
    sol = {f: _re.sub(r"___", lambda m: next(it), template[f]) for f in ("html", "css", "js") if f in template}
    return {"type": "blank", "prompt": prompt, "template": template, "gaps_solution": list(gaps), "solution": sol,
            "tests": tests, "hints": hints, "success_msg": success or "Those gaps were the missing piece. Nicely done."}


TAP = "Tap each coloured part to find out what it does."
LEARN = {
    ("html", 1): [
        anatomy("This is HTML, the code that builds web pages. " + TAP, [
            part("<h1>", "Opening tag", "Tags are labels inside angle brackets &lt; &gt;. This one tells the browser: <em>a big heading starts here</em>.", Y),
            part("Hello!", "Content", "The words people will actually see on the page.", G),
            part("</h1>", "Closing tag", "The <strong>slash</strong> means: the heading ends here. Most tags need a closing tag.", B),
            part("\n"),
            part("<p>", "Opening tag", "Starts a paragraph: a block of normal text.", Y),
            part("I like football.", "Content", "More words people will see.", G),
            part("</p>", "Closing tag", "Ends the paragraph.", B)]),
        blank("Type your name in the gap. Everything else is already written.", {"html": "<h1>My name is ___</h1>"}, ["Thandi"],
              [T("h", "The heading says My name is, then your name", "text", selector="h1", regex=r"my name is\s+\S{2,}")],
              ["Click the white box and type any name."]),
        blank("The tag for a paragraph is just the letter <code>p</code>. Fill in BOTH gaps with it.", {"html": "<___>I like football.</___>"}, ["p", "p"],
              [T("p", "A paragraph shows the words", "text", selector="p", contains="football"),
               T("c", "It is closed with </p>", "code_has", text="</p>", lang="html")],
              ["Both gaps need the same letter. The closing one has the slash already."]),
    ],
    ("html", 2): [
        anatomy("Links and pictures have extra information called <strong>attributes</strong> inside the tag. " + TAP, [
            part("<a ", "Link tag", "<code>a</code> is short for <em>anchor</em>. It makes the words inside clickable.", Y),
            part('href="https://wikipedia.org"', "Attribute: href", "An attribute gives extra information. <code>href</code> is <strong>where the link goes</strong>.", P),
            part(">"), part("Visit Wikipedia", "Content", "The clickable words.", G), part("</a>", "Closing tag", "Ends the link.", B),
            part("\n"),
            part("<img ", "Image tag", "Shows a picture. It has no closing tag.", Y),
            part('src="kite.png"', "Attribute: src", "<code>src</code> is <strong>which picture file</strong> to show.", P),
            part(" "), part('alt="A red kite"', "Attribute: alt", "<code>alt</code> describes the picture in words, for people who cannot see it.", R_), part(">")]),
        blank("The attribute that says where a link goes is <code>href</code>. Fill the gap.", {"html": '<a ___="https://wikipedia.org">Visit Wikipedia</a>'}, ["href"],
              [T("a", "The link has an href address", "attr", selector="a", attr="href", not_empty=True)], ["h r e f."]),
        blank("Now describe the picture with the <code>alt</code> attribute.", {"html": '<img src="kite.png" ___="A red kite">'}, ["alt"],
              [T("a", "The picture has alt text", "attr", selector="img", attr="alt", not_empty=True)], ["a l t, short for alternative text."]),
    ],
    ("html", 3): [
        anatomy("Lists group things. " + TAP, [
            part("<ul>", "List (ul)", "<code>ul</code> means <em>unordered list</em>: bullet points.", Y), part("\n  "),
            part("<li>Pap</li>", "List item (li)", "One bullet. Every item gets its own <code>li</code> tag.", G), part("\n  "),
            part("<li>Mango</li>", "Another item", "Add as many items as you like.", G), part("\n"),
            part("</ul>", "Closing tag", "Ends the whole list.", B)]),
        blank("Every bullet is an <code>li</code>. Fill both gaps to add Mango to the list.", {"html": "<ul>\n  <li>Pap</li>\n  <___>Mango</___>\n</ul>"}, ["li", "li"],
              [T("n", "The list shows 2 bullets", "count", selector="ul li", equals=2), T("c", "Both items are closed with </li>", "code_has", text="</li>", min=2, lang="html")],
              ["Both gaps are the same two letters."]),
    ],
    ("html", 4): [
        anatomy("A form lets people type things. " + TAP, [
            part('<label for="nm">', "Label", "The words next to a box. <code>for</code> must match the box's <code>id</code> so a click on the words jumps to the box.", Y),
            part("Name", "Content", "What people read.", G), part("</label>", "Closing tag", "Ends the label.", B), part("\n"),
            part("<input ", "Input tag", "A box people can use. No closing tag.", Y),
            part('id="nm"', "Attribute: id", "A unique name for this one box.", P), part(" "),
            part('type="text"', "Attribute: type", "What kind of input: a text box, a checkbox, a button, and more.", R_), part(">")]),
        blank("Make it a text box by filling in the <code>type</code>.", {"html": '<input type="___" placeholder="Your name">'}, ["text"],
              [T("i", "A text box appears", "exists", selector="input[type=text]")], ["The type for typing words is text."]),
    ],
    ("css", 1): [
        anatomy("CSS is the code that controls how things <em>look</em>. A CSS rule has three parts. " + TAP, [
            part("h1", "Selector", "Says <strong>which</strong> things to style. Here: every h1 heading.", Y), part(" "),
            part("{", "Curly braces", "Everything between the braces is the style for that selector.", B), part("\n  "),
            part("color", "Property", "<strong>What</strong> to change: here, the text colour.", P), part(": "),
            part("purple", "Value", "The new setting.", G), part(";", "Semicolon", "Ends this line of style.", R_), part("\n"),
            part("}", "Closing brace", "Ends the rule.", B)]),
        blank("The property that changes text colour is <code>color</code>. Fill the gap.", {"html": "<h1>Hello</h1>", "css": "h1 {\n  ___: purple;\n}"}, ["color"],
              [T("c", "The heading is purple", "style", selector="h1", prop="color", equals="rgb(128, 0, 128)")], ["c o l o r (American spelling)."]),
    ],
    ("css", 2): [
        blank("Paint the page. Fill in any colour name, like <code>lightblue</code> or <code>pink</code>.", {"html": "<h2>Hello</h2>", "css": "body {\n  background-color: ___;\n}"}, ["lightblue"],
              [T("b", "The page has a background colour", "style", selector="body", prop="background-color", not_equals="rgba(0, 0, 0, 0)")], ["Type one colour word."]),
    ],
    ("css", 3): [
        blank("<code>padding</code> adds space inside a box. Fill in the property name.", {"html": "<p>Some text</p>", "css": "p {\n  background: #eef3ff;\n  ___: 20px;\n}"}, ["padding"],
              [T("p", "The paragraph has 20px of padding", "style", selector="p", prop="padding-left", equals="20px")], ["It starts with p."]),
    ],
    ("css", 4): [
        blank("Flexbox lines items up in a row. Fill in the value that turns it on.", {"html": '<div class="row"><div>A</div><div>B</div><div>C</div></div>', "css": ".row {\n  display: ___;\n}"}, ["flex"],
              [T("f", "The row is a flex container", "style", selector=".row", prop="display", equals="flex")], ["f l e x."]),
    ],
    ("css", 5): [
        blank("A transition needs a time. Fill in <code>0.3s</code> (a third of a second).", {"html": '<div class="ball"></div>', "css": ".ball {\n  width: 50px;\n  height: 50px;\n  background: #9B7EDE;\n  border-radius: 50%;\n  transition: transform ___;\n}\n.ball:hover {\n  transform: scale(1.3);\n}"}, ["0.3s"],
              [T("t", "The transition lasts at least 0.2 seconds", "style", selector=".ball", prop="transition-duration", min_s=0.2)], ["Type 0.3s with the s."]),
    ],
    ("javascript", 1): [
        anatomy("JavaScript is code that makes pages DO things. A <strong>variable</strong> is a labelled box that stores something. " + TAP, [
            part("let", "let", "A command word that means: <em>make a new box</em>.", Y), part(" "),
            part("name", "Variable name", "The label on the box. You choose it.", P), part(" "),
            part("=", "Equals", "Puts the value into the box.", B), part(" "),
            part('"Sam"', "Value (a string)", "Words are called strings and always go inside quotes.", G),
            part(";", "Semicolon", "Ends the instruction, like a full stop.", R_)]),
        blank("Put your name in the gap, between the quote marks. The computer will use it.", {"js": 'let name = "___";\nalert("Hi " + name);'}, ["Thandi"],
              [T("a", "A message pops up", "alert", contains="hi"), T("n", "A name is stored in the box", "code_has", regex=r'let name = "\S+"', lang="js"), T("e", "No errors", "no_errors")],
              ["Click the box and type a name. Do not delete the quote marks."]),
    ],
    ("javascript", 2): [
        blank("Pass if the score is 50 <strong>or more</strong>. Which symbol means that? Fill the gap (two characters).", {"js": 'function grade(score) {\n  if (score ___ 50) {\n    return "Pass";\n  }\n  return "Try again";\n}'}, [">="],
              [T("a", "grade(80) is Pass", "call", fn="grade", args=[80], returns="Pass"), T("b", "grade(50) is Pass", "call", fn="grade", args=[50], returns="Pass"), T("c", "grade(20) is Try again", "call", fn="grade", args=[20], returns="Try again")],
              ["&gt; means more than. Adding = means: or equal to.", "&gt;="]),
    ],
    ("javascript", 3): [
        anatomy("A <strong>function</strong> is a named set of steps you can use again and again. " + TAP, [
            part("function", "function", "A command word: <em>start a new function</em>.", Y), part(" "),
            part("greet", "Function name", "What you call it later: greet(\"Sam\").", P),
            part("(name)", "Parameter", "Information the function receives when you use it.", B), part(" {\n  "),
            part("return", "return", "Hands the answer back to whoever used the function.", R_), part(" "),
            part('"Hello, " + name', "The answer", "Joins the words Hello and the name together.", G), part(";\n}")]),
        blank("<code>twice</code> should give back double the number. Fill in what to multiply by.", {"js": "function twice(n) {\n  return n * ___;\n}"}, ["2"],
              [T("a", "twice(4) is 8", "call", fn="twice", args=[4], returns="8"), T("b", "twice(10) is 20", "call", fn="twice", args=[10], returns="20")],
              ["Double means times 2."]),
    ],
    ("javascript", 4): [
        anatomy("Pages respond to <strong>events</strong>, like a click. " + TAP, [
            part("document.getElementById(\"btn\")", "Find the button", "<code>document</code> is the whole page. This finds the element whose id is btn.", Y),
            part(".addEventListener(", "Listen", "Tells the page: <em>wait for something to happen</em>.", P),
            part('"click"', "The event", "What to wait for. Here: someone clicks.", G),
            part(", function () {\n  "), part("title.textContent = \"Done!\";", "Change the page", "<code>textContent</code> is the words inside an element. This replaces them.", R_), part("\n});")]),
        blank("Fill in the name of the event that happens when someone presses the button.", {"html": '<h1 id="title">Press the button</h1>\n<button id="btn">Press</button>', "js": 'document.getElementById("btn").addEventListener("___", function () {\n  document.getElementById("title").textContent = "Done!";\n});'}, ["click"],
              [T("c", "Pressing the button changes the heading", "changes_on_click", click="#btn", watch="#title", what="text", times=1), T("e", "No errors", "no_errors")],
              ["The event is the word for pressing a mouse button or tapping."]),
    ],
    ("javascript", 5): [
        anatomy("A <strong>loop</strong> repeats steps. " + TAP, [
            part("for (", "for", "Starts a loop.", Y),
            part("let i = 0;", "Start", "A counter called i begins at 0. Computers usually start counting at 0.", P), part(" "),
            part("i < 3;", "Keep going while", "Run another round only while this is true.", B), part(" "),
            part("i++", "Step", "After each round, add 1 to i.", R_), part(") {\n  "),
            part("console.log(i);", "The repeated steps", "Everything in the braces runs once per round: here it shows 0, then 1, then 2.", G), part("\n}")]),
        blank("<code>fruits.length</code> is how many items are in the list. Fill in the missing word.", {"js": 'let fruits = ["apple", "banana", "cherry"];\nlet total = 0;\nfor (let i = 0; i < fruits.___; i++) {\n  total = total + 1;\n}\nconsole.log(total);'}, ["length"],
              [T("l", "The loop counted 3 fruits", "log", contains="3"), T("c", "It uses fruits.length", "code_has", text="fruits.length", lang="js"), T("e", "No errors", "no_errors")],
              ["It is a word for how long the list is."]),
    ],
    ("javascript", 6): [
        blank("Each click should add <strong>1</strong> to the score. Fill the gap.", {"html": '<h1 id="c">0</h1>\n<button id="b">+</button>', "js": 'let count = 0;\ndocument.getElementById("b").addEventListener("click", function () {\n  count = count + ___;\n  document.getElementById("c").textContent = count;\n});'}, ["1"],
              [T("s", "After 3 clicks it shows 3", "click", selector="#b", times=3, then=[T("x", "", "text", selector="#c", equals="3")]), T("e", "No errors", "no_errors")],
              ["One click, one point."]),
    ],
}



# ───────────────────────── second pass: introduce everything a mission uses ─────────────────────────
# (an audit found constructs used in build steps that no explore/fill step had introduced)
LEARN[("html", 1)][0]["parts"][0]["e"] = "Tags are labels inside angle brackets &lt; &gt;. This one tells the browser: <em>a big heading starts here</em>. <code>h1</code> is the biggest heading; <code>h2</code> is a little smaller, and so on down to h6."
MISSIONS[("html", 1)]["steps"].insert(1, anatomy("Every page has the same outline, and you can leave notes for people. " + TAP, [
    part("<!DOCTYPE html>", "Page type", "The very first line. It tells the browser: this is a modern web page.", Y), part("\n"),
    part("<html>", "html tag", "Everything on the page lives inside this tag.", B), part("\n  "),
    part("<body>", "body tag", "The part people can SEE goes in here.", P), part("\n    "),
    part("<!-- This is a note -->", "Comment", "A note for people. The browser ignores it completely, so nobody sees it on the page.", R_), part("\n    "),
    part("<h1>Hello!</h1>", "Your content", "Headings, paragraphs and pictures go here.", G), part("\n  "),
    part("</body>", "Closing body", "Ends the visible part.", P), part("\n"),
    part("</html>", "Closing html", "Ends the page. Notice the tags close in the REVERSE order they opened.", B)]))

LEARN[("html", 3)] += [
    blank("A numbered list uses <code>ol</code> (ordered list) instead of <code>ul</code>. Fill both gaps.", {"html": "<___>\n  <li>Boil water</li>\n  <li>Pour</li>\n</___>"}, ["ol", "ol"],
          [T("o", "A numbered list appears", "exists", selector="ol"), T("c", "It is closed with </ol>", "code_has", text="</ol>", lang="html")], ["Two letters: o and l."]),
    anatomy("Tables organise information into rows and columns. " + TAP, [
        part("<table>", "Table", "The whole table.", Y), part("\n  "),
        part("<tr>", "Table row", "One horizontal line. <code>tr</code> means <em>table row</em>.", B), part("\n    "),
        part("<th>Name</th>", "Header cell", "A heading cell, shown bold. <code>th</code> means <em>table header</em>.", P), part("\n    "),
        part("<th>Score</th>", "Another header", "One <code>th</code> per column.", P), part("\n  "),
        part("</tr>", "End of row", "Ends the row.", B), part("\n  "),
        part("<tr><td>Sam</td><td>90</td></tr>", "A data row", "<code>td</code> means <em>table data</em>: a normal cell. A row of data has one <code>td</code> per column.", G), part("\n"),
        part("</table>", "End of table", "Ends the table.", Y)]),
    blank("Sam's score goes in a normal data cell. The tag for that is <code>td</code>. Fill both gaps.", {"html": "<table>\n  <tr><th>Name</th><th>Score</th></tr>\n  <tr><td>Sam</td><___>90</___></tr>\n</table>"}, ["td", "td"],
          [T("t", "The score appears in a data cell", "text", selector="td", contains="90"), T("c", "It is closed with </td>", "code_has", text="</td>", min=2, lang="html")], ["Same two letters as the first cell."]),
]
# html 4: show the <form> wrapper and placeholder inside the existing anatomy
a4 = LEARN[("html", 4)][0]["parts"]
a4[:0] = [part("<form>", "Form", "A form holds all the boxes and buttons that belong together. It opens here and closes with &lt;/form&gt;.", B), part("\n  ")]
for p_ in a4:
    if p_.get("t") == "\n  " and p_ is not a4[1]:
        pass
a4[-1:-1] = [part(" "), part('placeholder="Your name"', "Attribute: placeholder", "A grey hint inside the box. It disappears when you start typing.", G)]
a4.append(part("\n")); a4.append(part("</form>", "Closing form", "Ends the form.", B))

LEARN[("css", 1)].append(blank("To centre text use <code>text-align</code>. Fill the gap with the property name.", {"html": "<h1>Hello</h1>", "css": "h1 {\n  ___: center;\n}"}, ["text-align"],
    [T("a", "The heading is centred", "style", selector="h1", prop="text-align", equals="center")], ["It has a dash in the middle: text-align."]))
LEARN[("css", 2)] += [
    anatomy("A <strong>class</strong> lets you style some things but not others. The HTML says <code>class=\"badge\"</code>; the CSS picks it with a dot. " + TAP, [
        part('<div class="badge">Level 1</div>', "The HTML", "This element has the class name <code>badge</code>.", G), part("\n\n"),
        part(".badge", "Class selector", "A dot then the class name picks every element with that class.", Y), part(" {\n  "),
        part("background: #1e3a5f;", "Hex colour", "A colour written as <code>#</code> plus six letters or numbers. Every colour has its own code.", P), part("\n  "),
        part("padding: 10px 20px;", "Padding", "Space inside the badge, around the text. 10px above and below, 20px left and right. <code>px</code> means pixels.", B), part("\n  "),
        part("border-radius: 20px;", "Rounded corners", "The bigger the number, the rounder the corners.", R_), part("\n}")]),
    blank("Round the corners of the badge. Fill in the property name.", {"html": '<div class="badge">Level 1</div>', "css": ".badge {\n  display: inline-block;\n  padding: 10px 20px;\n  background: #1e3a5f;\n  color: white;\n  ___: 20px;\n}"}, ["border-radius"],
          [T("r", "The badge has rounded corners", "style", selector=".badge", prop="border-top-left-radius", not_zero=True)], ["border dash radius."]),
    blank("A gradient blends two colours. Fill in the missing word that makes it.", {"html": '<div class="badge">Level 1</div>', "css": ".badge {\n  display: inline-block;\n  padding: 10px 20px;\n  color: white;\n  background: ___-gradient(135deg, #FFB347, #9B7EDE);\n}"}, ["linear"],
          [T("g", "The badge has a gradient", "style", selector=".badge", prop="background-image", contains="gradient")], ["The word is linear."]),
]
LEARN[("css", 3)] += [
    blank("<code>font-size</code> sets how big the letters are. Make the heading much bigger: fill in <code>48px</code>.", {"html": "<h1>Big heading</h1>", "css": "h1 {\n  font-size: ___;\n}"}, ["48px"],
          [T("s", "The heading text is 48px", "style", selector="h1", prop="font-size", equals="48px")], ["Type 48px with no space."]),
    blank("<code>margin</code> pushes a box away from other things. Fill in the property name.", {"html": '<div class="box">Hello</div>', "css": ".box {\n  background: #eef3ff;\n  ___-top: 20px;\n}"}, ["margin"],
          [T("m", "The box is pushed 20px from the top", "style", selector=".box", prop="margin-top", equals="20px")], ["It starts with m."]),
]
LEARN[("css", 4)].append(blank("Centre the star sideways. <code>justify-content</code> chooses where items sit along the row. Fill in <code>center</code>.", {"html": '<div class="stage"><div>&#9733;</div></div>', "css": ".stage {\n  display: flex;\n  justify-content: ___;\n  background: #eef3ff;\n  padding: 20px;\n}"}, ["center"],
    [T("j", "The star is centred along the row", "style", selector=".stage", prop="justify-content", equals="center")], ["American spelling: c e n t e r."]))
LEARN[("css", 5)].insert(0, anatomy("A rule can apply only while the mouse is on something. " + TAP, [
    part(".ball", "Class selector", "Picks every element with the class <code>ball</code>.", Y),
    part(":hover", "Hover", "The colon-word <code>:hover</code> means: <strong>only while the mouse is over it</strong>.", P), part(" {\n  "),
    part("transform: scale(1.3);", "Transform", "<code>transform</code> moves or resizes something. <code>scale(1.3)</code> makes it 30% bigger.", G), part("\n}")]))

LEARN[("javascript", 1)][0]["parts"]  # (unchanged)
WORDS[("javascript", 1)].append(["console.log", "Shows a message in the browser's Console, a hidden panel for coders. In the puzzles, the result is shown for you."])
LEARN[("javascript", 2)].insert(0, anatomy("A <strong>decision</strong>: the computer asks a question and takes one path. This one sits inside a function, a named machine called <code>grade</code> that you will meet properly in lesson 3. " + TAP, [
    part("function grade(score) {", "A function", "A machine named <code>grade</code>. You give it a score and it gives back an answer.", B), part("\n  "),
    part("if (score >= 50) {", "The question", "<code>if</code> asks: is the score 50 or more? <code>&gt;=</code> means <em>greater than or equal to</em>.", Y), part("\n    "),
    part('return "Pass";', "Answer back", "If yes, the machine hands back the word Pass. <code>return</code> means <em>hand this back</em>.", G), part("\n  }\n  "),
    part('return "Try again";', "Otherwise", "If the answer was no, it carries on here and hands back Try again.", R_), part("\n}")]))
LEARN[("javascript", 2)].append(blank("A third path: between the two, add a middle step. The words are <code>else if</code>. Fill the gap with the first word.", {"js": 'function grade(score) {\n  if (score >= 90) {\n    return "Great";\n  } ___ if (score >= 50) {\n    return "Good";\n  } else {\n    return "Try again";\n  }\n}'}, ["else"],
    [T("a", "grade(95) is Great", "call", fn="grade", args=[95], returns="Great"), T("b", "grade(70) is Good", "call", fn="grade", args=[70], returns="Good"), T("c", "grade(20) is Try again", "call", fn="grade", args=[20], returns="Try again"),
     T("e", "The middle step is written as else if", "code_has", regex=r"else\s+if", lang="js")], ["The word is else."]))
for p_ in LEARN[("javascript", 4)][0]["parts"]:
    if p_.get("t") == ", function () {\n  ":
        p_.update({"k": "The code to run", "e": "<code>function () { }</code> is a function with no name. The steps inside run every time the click happens.", "c": B})
LEARN[("javascript", 4)].append(blank("Toggle means: switch on, or off if it is already on. Fill in the word.", {"html": '<button id="t">Dark mode</button>\n<p>Hello there.</p>', "css": "body.dark { background: #1e3a5f; color: white; }", "js": 'document.getElementById("t").addEventListener("click", function () {\n  document.body.classList.___("dark");\n});'}, ["toggle"],
    [T("a", "A click turns dark mode on", "click", selector="#t", then=[T("x", "", "exists", selector="body.dark")]), T("b", "A second click turns it off", "click", selector="#t", then=[T("y", "", "count", selector="body.dark", equals=0)])], ["The word is toggle."]))
WORDS[("javascript", 4)].append(["classList", "The list of style names (classes) on an element. <code>toggle</code> adds a name or removes it."])
LEARN[("javascript", 5)] = [
    anatomy("An <strong>array</strong> is a list of things in order. " + TAP, [
        part("let fruits = ", "A variable", "A box named fruits.", P),
        part('["apple", "banana", "cherry"]', "Array", "A list in square brackets. Items are separated by commas.", Y), part(";\n"),
        part("fruits[1]", "Index", "Asks for the item at position 1. Computers start counting at <strong>0</strong>, so position 1 is the SECOND item: banana.", G)])
] + LEARN[("javascript", 5)] + [
    blank("To add a new list item to the page you create it first. Fill in the tag name <code>li</code>.", {"html": '<ul id="list"></ul>', "js": 'let li = document.createElement("___");\nli.textContent = "apple";\ndocument.getElementById("list").appendChild(li);'}, ["li"],
          [T("c", "One list item appears", "count", selector="#list li", equals=1), T("t", "It says apple", "text", selector="#list li", contains="apple"), T("e", "No errors", "no_errors")],
          ["createElement makes it. appendChild puts it on the page."]),
]
WORDS[("javascript", 5)].append(["createElement / appendChild", "createElement makes a new tag. appendChild puts it on the page, at the end of another element."])


# ───────────────────────── practice bank (one extra step per skill) ─────────────────────────
PRACTICE = {
    "html-structure": [{"type": "fix", "prompt": "One closing tag is wrong, so the paragraph ends up inside the heading. Fix it.",
        "starter_html": "<h1>Hello<h1>\n<p>World</p>",
        "tests": [T("h", "Exactly one heading", "count", selector="h1", equals=1), T("p", "The paragraph sits on its own, not inside the heading", "exists", selector="body > p")],
        "hints": ["A closing tag starts with a slash: <code>&lt;/h1&gt;</code>."], "solution": {"html": "<h1>Hello</h1>\n<p>World</p>"}}],
    "links-media": [{"type": "predict", "lang": "html", "prompt": "What can the visitor click?",
        "code": "<a href=\"https://a.example\"><img src=\"x.png\" alt=\"Logo\"></a>", "answer": ["the image", "image", "logo", "picture", "the picture", "the logo"],
        "explain": "Everything between the opening and closing a tags is clickable, including a picture."}],
    "lists-tables": [{"type": "code", "prompt": "Write the 3 steps of making tea as an ordered (numbered) list with <code>&lt;ol&gt;</code>.",
        "starter_html": "<h3>Making tea</h3>\n",
        "tests": [T("ol", "An <ol> exists", "exists", selector="ol"), T("li", "At least 3 steps inside it", "count", selector="ol li", min=3)],
        "hints": ["<code>&lt;ol&gt;&lt;li&gt;Boil water&lt;/li&gt;...&lt;/ol&gt;</code>"],
        "solution": {"html": "<h3>Making tea</h3>\n<ol><li>Boil water</li><li>Add tea bag</li><li>Pour and wait</li></ol>"}}],
    "forms": [{"type": "code", "prompt": "Add a checkbox with a label that says <em>I agree</em>.",
        "starter_html": "<form>\n  \n</form>",
        "tests": [T("c", "A checkbox exists", "exists", selector="input[type=checkbox]"), T("l", "A label says I agree", "text", selector="label", contains="I agree")],
        "hints": ["<code>&lt;input type=\"checkbox\" id=\"ok\"&gt;</code> and <code>&lt;label for=\"ok\"&gt;I agree&lt;/label&gt;</code>"],
        "solution": {"html": "<form>\n  <input type=\"checkbox\" id=\"ok\">\n  <label for=\"ok\">I agree</label>\n</form>"}}],
    "css-selectors": [{"type": "fix", "prompt": "The paragraph should be red but is not. The selector does not match. Fix the CSS.",
        "starter_html": "<p class=\"note\">Hi</p>", "starter_css": ".notes {\n  color: red;\n}",
        "tests": [T("r", "The paragraph is red", "style", selector="p", prop="color", equals="rgb(255, 0, 0)")],
        "hints": ["Compare the class name in the HTML with the one in the CSS, letter by letter."], "solution": {"css": ".note {\n  color: red;\n}"}}],
    "color": [{"type": "predict", "lang": "html", "prompt": "What colour is the text? (one word)",
        "code": "<div style=\"background:#000;color:#fff;padding:8px\">Hi</div>", "answer": ["white"],
        "explain": "#fff is white. #000 is black, which is the background here."}],
    "spacing-type": [{"type": "code", "prompt": "Push the box away from the top with a 20px <code>margin-top</code>, and right-align its text.",
        "starter_html": "<div class=\"box\">Hello</div>", "starter_css": ".box {\n  background: #eef3ff;\n}",
        "tests": [T("m", "margin-top is 20px", "style", selector=".box", prop="margin-top", equals="20px"), T("a", "Text is right-aligned", "style", selector=".box", prop="text-align", equals="right")],
        "hints": ["<code>margin-top: 20px;</code>", "<code>text-align: right;</code>"], "solution": {"css": ".box {\n  background: #eef3ff;\n  margin-top: 20px;\n  text-align: right;\n}"}}],
    "flexbox": [{"type": "fix", "prompt": "The cards should sit in a row but they are stacked. Flex is on the wrong element. Fix it.",
        "starter_html": "<div class=\"row\"><div class=\"c\">A</div><div class=\"c\">B</div></div>", "starter_css": ".c {\n  display: flex;\n}",
        "tests": [T("f", "The parent .row is a flex container", "style", selector=".row", prop="display", equals="flex")],
        "hints": ["Flex goes on the parent that holds the items."], "solution": {"css": ".row {\n  display: flex;\n}"}}],
    "animation": [{"type": "predict", "lang": "html", "prompt": "How many times will this spinner spin? (one word)",
        "code": "<div style=\"width:30px;height:30px;background:#9B7EDE;animation:spin 2s infinite\"></div><style>@keyframes spin{to{transform:rotate(360deg)}}</style>",
        "answer": ["forever", "infinite", "infinitely", "never stops", "always", "non stop", "nonstop"], "explain": "infinite means it repeats without ever stopping."}],
    "variables": [{"type": "predict", "lang": "js", "prompt": "What is printed?", "code": "let x = 2;\nlet y = x * 5;\nconsole.log(y);",
        "answer": ["10"], "explain": "y is x times 5, which is 2 times 5."}],
    "conditionals": [{"type": "code", "prompt": "Write <code>isAdult(age)</code> that returns <code>true</code> for 18 or older and <code>false</code> otherwise.",
        "starter_js": "function isAdult(age) {\n  \n}",
        "tests": [T("a", "isAdult(17) is false", "call", fn="isAdult", args=[17], returns="false"), T("b", "isAdult(18) is true", "call", fn="isAdult", args=[18], returns="true"), T("c", "isAdult(40) is true", "call", fn="isAdult", args=[40], returns="true")],
        "hints": ["<code>return age >= 18;</code> is the shortest way."], "solution": {"js": "function isAdult(age) {\n  return age >= 18;\n}"}}],
    "functions": [{"type": "predict", "lang": "js", "prompt": "What is printed?", "code": "function f(a, b) {\n  return a - b;\n}\nconsole.log(f(9, 4));",
        "answer": ["5"], "explain": "a is 9 and b is 4, so 9 minus 4 is 5."}],
    "dom-events": [{"type": "fix", "prompt": "The text changes straight away when the page loads, but it should change only when the button is clicked. Find the bug.",
        "starter_html": "<p id=\"t\">Hi</p>\n<button id=\"b\">Go</button>",
        "starter_js": "function changeIt() {\n  document.getElementById(\"t\").textContent = \"Changed\";\n}\ndocument.getElementById(\"b\").addEventListener(\"click\", changeIt());",
        "tests": [T("s", "The text still says Hi before any click", "text", selector="#t", equals="Hi"), T("c", "Clicking the button changes it", "changes_on_click", click="#b", watch="#t", what="text", times=1)],
        "hints": ["Writing <code>changeIt()</code> RUNS the function right now. Pass the name without brackets."],
        "solution": {"js": "function changeIt() {\n  document.getElementById(\"t\").textContent = \"Changed\";\n}\ndocument.getElementById(\"b\").addEventListener(\"click\", changeIt);"}}],
    "loops-arrays": [{"type": "predict", "lang": "js", "prompt": "What is printed?", "code": "let a = [\"x\", \"y\", \"z\"];\nconsole.log(a[1]);",
        "answer": ["y"], "explain": "Arrays start counting at 0, so index 1 is the second item."}],
    "state-game": [{"type": "code", "prompt": "Build a score keeper. <code>#plus</code> adds 1 to <code>#score</code>. <code>#minus</code> takes 1 away but the score can never go below 0.",
        "starter_html": "<h2 id=\"score\">0</h2>\n<button id=\"plus\">+</button>\n<button id=\"minus\">-</button>",
        "starter_js": "let score = 0;\n",
        "tests": [T("z", "Minus at 0 stays at 0", "click", selector="#minus", then=[T("a", "", "text", selector="#score", equals="0")]),
                  T("p", "Three pluses then one minus gives 2", "click", selector="#plus", times=3, then=[T("b", "", "click", selector="#minus", then=[T("c", "", "text", selector="#score", equals="2")])]),
                  T("e", "No errors", "no_errors")],
        "hints": ["Two listeners, one per button.", "In minus: <code>if (score > 0) { score = score - 1; }</code>"],
        "solution": {"js": "let score = 0;\nlet out = document.getElementById(\"score\");\ndocument.getElementById(\"plus\").addEventListener(\"click\", function () {\n  score = score + 1;\n  out.textContent = score;\n});\ndocument.getElementById(\"minus\").addEventListener(\"click\", function () {\n  if (score > 0) {\n    score = score - 1;\n  }\n  out.textContent = score;\n});"}}],
}

# ───────────────────────── capstones (free build, rubric = the tests) ─────────────────────────
CAPSTONES = {
    "html": {"title": "Capstone: All About Me page", "success_msg": "You built a complete page from a blank editor. That is a real skill.",
        "steps": [{"type": "code", "skill": "capstone-html",
            "prompt": "Build an <strong>All About Me</strong> page from scratch. The checklist below is your rubric: tick every line.",
            "starter_html": "<!-- Build your page here -->\n",
            "tests": [T("h", "A main heading with your name", "text", selector="h1", regex=r"\S{2,}"),
                      T("p", "At least 2 paragraphs about you", "count", selector="p", min=2),
                      T("i", "A picture with alt text", "attr", selector="img", attr="alt", not_empty=True),
                      T("l", "A list of at least 3 things you like", "count", selector="ul li", min=3),
                      T("a", "A link to a website you like", "attr", selector="a", attr="href", not_empty=True)],
            "hints": ["Plan first: heading, two paragraphs, a picture, a list, a link."],
            "solution": {"html": "<h1>Thandi Mokoena</h1>\n<p>I am 12 and I love code.</p>\n<p>I live in Qwaqwa.</p>\n<img src=\"me.jpg\" alt=\"Me smiling\">\n<ul><li>Games</li><li>Music</li><li>Football</li></ul>\n<a href=\"https://wikipedia.org\">My favourite site</a>"}}]},
    "css": {"title": "Capstone: Style the team cards", "success_msg": "You styled a whole layout yourself. Designers do exactly this.",
        "steps": [{"type": "code", "skill": "capstone-css",
            "prompt": "Make these team cards look professional. The checklist is your rubric.",
            "starter_html": "<div class=\"row\">\n  <div class=\"card\">Ada</div>\n  <div class=\"card\">Linus</div>\n  <div class=\"card\">Grace</div>\n</div>",
            "starter_css": "/* style .row and .card */\n",
            "tests": [T("f", "The cards are in a row (flex)", "style", selector=".row", prop="display", equals="flex"),
                      T("g", "There is space between them (gap or justify-content)", "code_has", regex=r"\bgap\s*:|justify-content\s*:\s*space", lang="css"),
                      T("p", "Cards have at least 12px padding", "style", selector=".card", prop="padding-left", min_px=12),
                      T("r", "Cards have rounded corners", "style", selector=".card", prop="border-top-left-radius", not_zero=True),
                      T("b", "Cards have a background colour", "style", selector=".card", prop="background-color", not_equals="rgba(0, 0, 0, 0)"),
                      T("t", "Cards animate smoothly when changed (transition)", "style", selector=".card", prop="transition-duration", min_s=0.2)],
            "hints": ["Start with the parent: <code>.row { display: flex; gap: 16px; }</code>", "Then style one card and the rest follow."],
            "solution": {"css": ".row { display: flex; gap: 16px; }\n.card { padding: 16px; border-radius: 14px; background-color: #9B7EDE; color: white; transition: transform 0.3s; }"}}]},
    "javascript": {"title": "Capstone: Build a to-do list", "success_msg": "A working app with input, state and events. You are a developer.",
        "steps": [{"type": "code", "skill": "capstone-javascript",
            "prompt": "Make the to-do app work. <code>#add</code> puts the text from <code>#item</code> into the list <code>#list</code> as a new <code>li</code> (and ignores empty text). <code>#clear</code> empties the list.",
            "starter_html": "<input id=\"item\" placeholder=\"New task\">\n<button id=\"add\">Add</button>\n<button id=\"clear\">Clear all</button>\n<ul id=\"list\"></ul>",
            "starter_js": "// your code here\n",
            "tests": [T("e0", "Adding empty text does nothing", "click", selector="#add", then=[T("z", "", "count", selector="#list li", equals=0)]),
                      T("e1", "Typing Milk and pressing Add shows a Milk item", "click", selector="#add", fill={"selector": "#item", "value": "Milk"},
                        then=[T("m", "", "text", selector="#list li", contains="milk"),
                              T("e2", "", "click", selector="#add", fill={"selector": "#item", "value": "Eggs"},
                                then=[T("c2", "", "count", selector="#list li", equals=2),
                                      T("e3", "", "click", selector="#clear", then=[T("c0", "", "count", selector="#list li", equals=0)])])]),
                      T("n", "No errors", "no_errors")],
            "hints": ["Read the box: <code>document.getElementById(\"item\").value</code>", "Add: createElement(\"li\"), set textContent, appendChild.", "Clear with <code>list.innerHTML = \"\"</code>"],
            "solution": {"js": "let item = document.getElementById(\"item\");\nlet list = document.getElementById(\"list\");\ndocument.getElementById(\"add\").addEventListener(\"click\", function () {\n  if (item.value.trim() === \"\") { return; }\n  let li = document.createElement(\"li\");\n  li.textContent = item.value;\n  list.appendChild(li);\n  item.value = \"\";\n});\ndocument.getElementById(\"clear\").addEventListener(\"click\", function () {\n  list.innerHTML = \"\";\n});"}}]},
}

# ───────────────────────── "Before you code": zero typing, zero jargon ─────────────────────────
PRECODE = {
    "title": "Program a robot",
    "success_msg": "You just wrote a program! You gave a robot exact instructions and it followed them.",
    "skill": "intro",
    "words": [
        ["Instruction", "One small thing you tell the computer to do, like \"move right\"."],
        ["Program", "A list of instructions, in order. Computers follow them exactly."],
        ["Bug", "A mistake in a program. Finding and fixing bugs is a normal part of coding."],
        ["Repeat (a loop)", "A way to say \"do this many times\" without writing it over and over."],
    ],
    "worked": {
        "title": "Computers only do what they are told",
        "explain": "A computer cannot guess. It follows your instructions one at a time, exactly, and it never skips a step. In the next few levels you will tell a little robot how to walk to the star. You do not need to type anything: just tap the blocks.",
        "html": "<div style=\"font-size:1.6rem;font-weight:800;letter-spacing:.3rem\" id=\"o\">Press the button</div><button id=\"b\">Walk</button>",
        "js": "var steps = [\"\u2192\", \"\u2192\", \"\u2193\"];\nvar n = 0;\ndocument.getElementById(\"b\").addEventListener(\"click\", function () {\n  if (n < steps.length) {\n    document.getElementById(\"o\").textContent += steps[n] + \" \";\n    n = n + 1;\n  }\n});",
    },
    "steps": [
        {"type": "robot", "skill": "intro", "grid": ["R..G"],
         "prompt": "Get the robot to the star. Tap <strong>Right</strong> to add a move, then press <strong>Run program</strong>.",
         "solution": ["right", "right", "right"],
         "hints": ["The star is 3 squares to the right. Tap Right 3 times."],
         "success_msg": "That is a program: a list of instructions, in order."},
        {"type": "robot", "skill": "intro", "grid": ["R..", "...", "..G"],
         "prompt": "Now the star is down and to the right. Plan the path before you tap.",
         "solution": ["right", "right", "down", "down"],
         "hints": ["Count how many squares right, then how many down."],
         "success_msg": "Order matters. The same blocks in a different order take a different path."},
        {"type": "robot", "skill": "intro", "grid": ["R.#G", "..#.", "...."],
         "prompt": "Careful, there is a wall. A mistake in a program is called a <strong>bug</strong>. If the robot bumps, find the bug and fix it.",
         "solution": ["down", "down", "right", "right", "right", "up", "up"],
         "hints": ["The robot cannot go through the grey wall. Go around it.", "Down 2, right 3, then up 2."],
         "success_msg": "You found a way around the bug. Real coders do this all day."},
        {"type": "robot", "skill": "intro", "grid": ["R.....G"], "repeats": [2, 3, 6], "max_blocks": 2,
         "prompt": "The star is far away, and you may only use <strong>2 blocks</strong>. Use a <strong>Repeat</strong> block: it repeats the block right after it.",
         "solution": [{"r": 6}, "right"],
         "hints": ["Count the squares to the star.", "Repeat 6\u00d7 first, then Right."],
         "success_msg": "Repeating is called a loop. It saves you from writing the same thing again and again."},
        {"type": "predict", "lang": "js", "skill": "intro",
         "prompt": "<strong>Real code is the same idea, written as words.</strong> Each line is one instruction. Read the lines. How many steps to the RIGHT does the robot take? (type a number)",
         "setup": "function right() { console.log(\"\u2192\"); }\nfunction down() { console.log(\"\u2193\"); }\n",
         "code": "right();\nright();\ndown();",
         "answer": ["2", "two"],
         "hints": ["Count the lines that say right()."],
         "explain": "right() means move right once. You read it top to bottom, just like the blocks. Next you will write some real code."},
    ],
}

# ───────────────────────── "Meet code": the first 5 minutes ─────────────────────────
INTRO = {
    "title": "Your first real code",
    "success_msg": "You just gave a computer instructions and it obeyed. That is coding!",
    "skill": "intro",
    "words": [
        ["Code", "Instructions for a computer, written in words and symbols."],
        ["HTML", "The code that builds what is ON a web page: headings, text, pictures."],
        ["CSS", "The code that controls how a page LOOKS: colours, sizes, spacing."],
        ["Tag", "A label in angle brackets like &lt;h1&gt; that tells the browser what something is. Most tags have an opening &lt;h1&gt; and a closing &lt;/h1&gt;."],
        ["Heading / paragraph", "A heading is a big title (&lt;h1&gt;). A paragraph (&lt;p&gt;) is a block of normal text."],
        ["Browser", "The app you use to see web pages, like Chrome."],
    ],
    "worked": {
        "title": "First, what IS code?",
        "explain": "Code is a list of instructions a computer follows, one line at a time, exactly as written. Press the button below: your click runs two lines of code that change the page. In a few minutes you will write lines like these yourself.",
        "html": "<button id=\"b\">Press me</button>\n<p id=\"o\">Nothing has happened yet.</p>",
        "js": "document.getElementById(\"b\").addEventListener(\"click\", function () {\n  document.getElementById(\"o\").textContent = \"You just ran code!\";\n});",
    },
    "steps": [
        {"type": "order", "skill": "intro",
         "prompt": "<strong>You already give instructions.</strong> A computer needs them in the right order too. Put these steps for making toast in order.",
         "lines": ["Put bread in the toaster", "Push the lever down", "Wait for the toast to pop up", "Spread butter on it"],
         "hints": ["What must happen before the toaster can heat?"],
         "explain": "That list is called an algorithm: steps in the right order. Code is an algorithm written for a computer."},
        {"type": "predict", "lang": "js", "skill": "intro",
         "prompt": "<strong>Computers follow lines top to bottom.</strong> Here <code>console.log</code> just means \"show this word\". What appears, in order? (type both words)",
         "code": "console.log(\"Beep\");\nconsole.log(\"Boop\");",
         "answer": ["Beep Boop", "Beep, Boop", "beep boop", "beep and boop"],
         "hints": ["The first line runs first."],
         "explain": "One line at a time, top to bottom, exactly as written."},
        {"type": "code", "skill": "intro",
         "prompt": "<strong>Change a number, change the world.</strong> The box on the right comes from the code on the left. Make it <code>150px</code> wide and change its colour from <code>tomato</code> to any other colour.",
         "starter_html": "<div class=\"box\"></div>",
         "starter_css": ".box {\n  width: 50px;\n  height: 50px;\n  background: tomato;\n}",
         "tests": [T("w", "The box is 150px wide", "style", selector=".box", prop="width", equals="150px"),
                   T("c", "The box is a new colour (not tomato)", "style", selector=".box", prop="background-color", not_equals="rgb(255, 99, 71)")],
         "hints": ["Change the number after <code>width:</code>.", "Try <code>background: teal;</code> or <code>purple</code>."],
         "solution": {"css": ".box {\n  width: 150px;\n  height: 50px;\n  background: teal;\n}"},
         "success_msg": "You changed the code and the result changed. That is the whole loop of programming."},
        {"type": "fix", "skill": "intro",
         "prompt": "<strong>Computers are picky.</strong> One missing character breaks everything. The command <code>alert</code> pops up a message box. This one should say Hi, but it does not run. Find the missing piece (look at the quote marks).",
         "starter_js": "alert(\"Hi);",
         "tests": [T("a", "An alert says Hi", "alert", contains="Hi"), T("e", "No errors", "no_errors")],
         "hints": ["Every opening quote needs a closing quote.", "Put a <code>\"</code> just before the <code>)</code>."],
         "solution": {"js": "alert(\"Hi\");"},
         "success_msg": "Finding and fixing mistakes is a big part of a coder's day. You just did it."},
        {"type": "code", "skill": "intro",
         "prompt": "<strong>Your first real page.</strong> Replace the underscores with your name, then add a paragraph (<code>&lt;p&gt;</code>) saying what you want to build one day.",
         "starter_html": "<h1>Hello, ___</h1>\n",
         "tests": [T("h", "The heading shows your name (no underscores left)", "text", selector="h1", regex=r"^(?!.*_)\s*\S{2,}"),
                   T("p", "A paragraph says what you want to build (3+ words)", "text", selector="p", regex=r"\S+\s+\S+\s+\S+")],
         "hints": ["<code>&lt;p&gt;I want to build a game.&lt;/p&gt;</code>"],
         "solution": {"html": "<h1>Hello, Thandi</h1>\n<p>I want to build a game about robots.</p>"},
         "success_msg": "That is a real web page. You are a coder."},
    ],
}

# the to-do capstone needs three tools the lessons only touched: reading a box, trim(), emptying a list
CAPSTONES["javascript"]["steps"].insert(0, anatomy("Three new tools you will need for this project. " + TAP, [
    part("item.value", "Read a box", "<code>value</code> is whatever the person has typed into an input box.", Y), part("\n"),
    part("item.value.trim()", "Trim", "<code>trim()</code> removes spaces at the start and end, so a box with only spaces counts as empty.", P), part("\n"),
    part('item.value.trim() === ""', "Is it empty?", "<code>===</code> asks: is this EXACTLY equal? Two quote marks with nothing between them mean empty text.", G), part("\n"),
    part('list.innerHTML = "";', "Empty a list", "<code>innerHTML</code> is everything inside an element. Setting it to empty text clears it out.", R_)]))

# Skills that capstones belong to (shown on the skills page)
SKILL_LABELS.update({"intro": "Getting started", "capstone-html": "HTML capstone", "capstone-css": "CSS capstone", "capstone-javascript": "JavaScript capstone"})


def build_mission(key):
    """The full mission for a lesson: skill tags and a worked example added."""
    import copy
    m = copy.deepcopy(MISSIONS[key])
    skill = SKILL_BY_LESSON.get(key)
    m["skill"] = skill
    for st in m["steps"]:
        st.setdefault("skill", skill)
    # beginners first meet each idea by exploring and filling gaps, then build it
    m["steps"] = [dict(st, skill=skill) for st in LEARN.get(key, [])] + m["steps"]
    if key in WORKED:
        m["worked"] = WORKED[key]
    if key in WORDS:
        m["words"] = WORDS[key]
    return m


def practice_mission(skill):
    """Extra practice for one skill: its bank step(s) plus the steps from the lesson that teaches it."""
    import copy
    steps = copy.deepcopy(PRACTICE.get(skill, []))
    key = LESSON_BY_SKILL.get(skill)
    if key:
        steps += [dict(copy.deepcopy(st), skill=skill) for st in MISSIONS[key]["steps"] if st["type"] != "code" or st.get("solution")]
    for st in steps:
        st.setdefault("skill", skill)
    return {"title": "Practice: " + SKILL_LABELS.get(skill, skill), "success_msg": "Extra practice done. That skill just got stronger.", "skill": skill, "steps": steps}


def apply_missions(db, Lesson):
    """Write missions into Lesson.practice_json. Safe to run on every start."""
    changed = 0
    for key in MISSIONS:
        lesson = Lesson.query.filter_by(track=key[0], order=key[1]).first()
        if not lesson:
            logging.getLogger(__name__).warning('No %s lesson with order %s: its mission was not attached', key[0], key[1])
            continue
        payload = json.dumps(build_mission(key))
        if lesson.practice_json != payload:
            lesson.practice_json = payload
            changed += 1
    if changed:
        db.session.commit()
    return changed
