import os
import json
import smtplib
import requests as http_requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from collections import defaultdict
import time as _time

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-key-for-testing')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
csrf = CSRFProtect(app)

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)

# ==================== DATABASE MODELS ====================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='student')
    xp = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserProject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    html_code = db.Column(db.Text, default='')
    css_code = db.Column(db.Text, default='')
    js_code = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ProjectTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    difficulty = db.Column(db.String(20))
    icon = db.Column(db.String(50))
    color = db.Column(db.String(7))
    html_code = db.Column(db.Text, default='')
    css_code = db.Column(db.Text, default='')
    js_code = db.Column(db.Text, default='')
    order = db.Column(db.Integer, default=0)
    category = db.Column(db.String(50), default='general')  # 'game', 'art', 'general'

class Testimonial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(300), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    emoji = db.Column(db.String(10), default='⭐')
    is_approved = db.Column(db.Boolean, default=True)

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    track = db.Column(db.String(50), nullable=False)   # 'html', 'css', 'javascript'
    order = db.Column(db.Integer, default=0)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)       # HTML content rendered in page
    quiz_json = db.Column(db.Text, default='[]')       # JSON array of question dicts
    xp_reward = db.Column(db.Integer, default=10)

class LessonProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    quiz_passed = db.Column(db.Boolean, default=False)
    score = db.Column(db.Integer, default=0)           # quiz % score
    completed_at = db.Column(db.DateTime)
    __table_args__ = (db.UniqueConstraint('user_id', 'lesson_id'),)

# ==================== RATE LIMITING ====================
_failed_logins = defaultdict(list)
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300

def _is_rate_limited(ip):
    now = _time.time()
    _failed_logins[ip] = [t for t in _failed_logins[ip] if now - t < LOGIN_WINDOW_SECONDS]
    return len(_failed_logins[ip]) >= LOGIN_MAX_ATTEMPTS

def _record_failed_login(ip):
    _failed_logins[ip].append(_time.time())

# ==================== SEED DATA ====================
LESSON_DATA = [
    # ── HTML TRACK ──────────────────────────────────────────────────────────────
    {
        'track': 'html', 'order': 1, 'title': 'What is HTML?', 'xp_reward': 10,
        'content': """
<p>HTML stands for <strong>HyperText Markup Language</strong>. It's the skeleton of every webpage — it tells the browser <em>what</em> to show.</p>
<p>HTML uses <strong>tags</strong> — little labels wrapped in angle brackets. Most tags come in pairs:</p>
<pre><code>&lt;h1&gt;Hello World&lt;/h1&gt;</code></pre>
<p>The first tag <code>&lt;h1&gt;</code> opens the element, and <code>&lt;/h1&gt;</code> (with the slash) closes it. Everything in between is the content!</p>
<p>Here are the most important tags:</p>
<ul>
  <li><code>&lt;h1&gt;</code> to <code>&lt;h6&gt;</code> — headings (h1 is biggest)</li>
  <li><code>&lt;p&gt;</code> — a paragraph</li>
  <li><code>&lt;strong&gt;</code> — <strong>bold</strong> text</li>
  <li><code>&lt;em&gt;</code> — <em>italic</em> text</li>
</ul>
<div class="lesson-try-it">
  <p>✏️ <strong>Try it!</strong> In the Playground, type:</p>
  <pre><code>&lt;h1&gt;My name is ...&lt;/h1&gt;\n&lt;p&gt;I love coding!&lt;/p&gt;</code></pre>
  <p>Then click ▶ Run and watch it appear!</p>
</div>
""",
        'quiz_json': json.dumps([
            {"q": "What does HTML stand for?",
             "options": ["HyperText Markup Language","High Tech Modern Language","HyperText Making Language","Home Tool Markup Language"],
             "answer": 0},
            {"q": "Which tag makes the BIGGEST heading?",
             "options": ["<h6>","<h1>","<big>","<heading>"],
             "answer": 1},
            {"q": "How do you close an HTML tag?",
             "options": ["With a * before the name","With a / before the name","With a ! before the name","You don't need to close them"],
             "answer": 1},
        ])
    },
    {
        'track': 'html', 'order': 2, 'title': 'Links & Images', 'xp_reward': 10,
        'content': """
<p>Two of the most powerful HTML tags let you <strong>link to other pages</strong> and <strong>display pictures</strong>.</p>
<h3>🔗 Links — <code>&lt;a&gt;</code></h3>
<pre><code>&lt;a href="https://google.com"&gt;Visit Google&lt;/a&gt;</code></pre>
<p>The <code>href</code> attribute tells the browser <em>where</em> to go. An <strong>attribute</strong> is extra info you put inside the opening tag.</p>
<h3>🖼️ Images — <code>&lt;img&gt;</code></h3>
<pre><code>&lt;img src="cat.jpg" alt="A fluffy cat"&gt;</code></pre>
<p><code>&lt;img&gt;</code> is a <strong>self-closing</strong> tag — it has no closing tag! The <code>src</code> attribute is the image address, and <code>alt</code> is a description for people who can't see it.</p>
<div class="lesson-try-it">
  <p>✏️ <strong>Try it!</strong></p>
  <pre><code>&lt;a href="https://wikipedia.org"&gt;Go to Wikipedia!&lt;/a&gt;\n&lt;br&gt;\n&lt;img src="https://placekitten.com/200/200" alt="cute kitten"&gt;</code></pre>
</div>
""",
        'quiz_json': json.dumps([
            {"q": "Which attribute tells a link WHERE to go?",
             "options": ["src","link","href","url"],
             "answer": 2},
            {"q": "The <img> tag needs a closing </img> tag.",
             "options": ["True","False"],
             "answer": 1},
            {"q": "What does the 'alt' attribute on an image do?",
             "options": ["Makes the image alternate colours","Describes the image in words","Changes image size","Adds a link to the image"],
             "answer": 1},
        ])
    },
    {
        'track': 'html', 'order': 3, 'title': 'Lists & Tables', 'xp_reward': 10,
        'content': """
<p>HTML has two types of lists and a powerful table structure.</p>
<h3>📋 Unordered List — bullets</h3>
<pre><code>&lt;ul&gt;\n  &lt;li&gt;Pizza&lt;/li&gt;\n  &lt;li&gt;Ice cream&lt;/li&gt;\n  &lt;li&gt;Robots&lt;/li&gt;\n&lt;/ul&gt;</code></pre>
<h3>🔢 Ordered List — numbers</h3>
<pre><code>&lt;ol&gt;\n  &lt;li&gt;Wake up&lt;/li&gt;\n  &lt;li&gt;Eat breakfast&lt;/li&gt;\n  &lt;li&gt;Code!&lt;/li&gt;\n&lt;/ol&gt;</code></pre>
<h3>📊 Tables</h3>
<pre><code>&lt;table&gt;\n  &lt;tr&gt;\n    &lt;th&gt;Name&lt;/th&gt;\n    &lt;th&gt;Score&lt;/th&gt;\n  &lt;/tr&gt;\n  &lt;tr&gt;\n    &lt;td&gt;Karabo&lt;/td&gt;\n    &lt;td&gt;100&lt;/td&gt;\n  &lt;/tr&gt;\n&lt;/table&gt;</code></pre>
<p><code>&lt;tr&gt;</code> = table row, <code>&lt;th&gt;</code> = header cell, <code>&lt;td&gt;</code> = data cell.</p>
<div class="lesson-try-it">
  <p>✏️ <strong>Try it!</strong> Build a list of your top 3 favourite games or foods.</p>
</div>
""",
        'quiz_json': json.dumps([
            {"q": "Which tag creates an UNORDERED (bulleted) list?",
             "options": ["<ol>","<list>","<ul>","<bl>"],
             "answer": 2},
            {"q": "What does <tr> stand for in a table?",
             "options": ["Table Row","Text Right","Table Result","Table Reference"],
             "answer": 0},
            {"q": "Which tag makes a table HEADER cell?",
             "options": ["<td>","<tc>","<th>","<thead>"],
             "answer": 2},
        ])
    },
    {
        'track': 'html', 'order': 4, 'title': 'Forms & Inputs', 'xp_reward': 15,
        'content': """
<p>Forms let users type information and send it — like login pages and search bars!</p>
<pre><code>&lt;form&gt;\n  &lt;label&gt;Your name:&lt;/label&gt;\n  &lt;input type="text" placeholder="Type here..."&gt;\n  &lt;br&gt;&lt;br&gt;\n  &lt;input type="submit" value="Send!"&gt;\n&lt;/form&gt;</code></pre>
<p>The <code>type</code> attribute changes what kind of input it is:</p>
<ul>
  <li><code>type="text"</code> — regular text box</li>
  <li><code>type="password"</code> — hides what you type</li>
  <li><code>type="email"</code> — checks for a valid email</li>
  <li><code>type="number"</code> — only allows numbers</li>
  <li><code>type="checkbox"</code> — a tick box</li>
  <li><code>type="submit"</code> — the Send button</li>
</ul>
<p>A <code>&lt;textarea&gt;</code> is for longer messages:</p>
<pre><code>&lt;textarea rows="4" placeholder="Write something..."&gt;&lt;/textarea&gt;</code></pre>
<div class="lesson-try-it">
  <p>✏️ <strong>Try it!</strong> Build a mini "about me" form with a name field, an email field, and a submit button.</p>
</div>
""",
        'quiz_json': json.dumps([
            {"q": "Which input type hides your text as you type?",
             "options": ["type=\"hidden\"","type=\"secret\"","type=\"password\"","type=\"blur\""],
             "answer": 2},
            {"q": "What tag wraps all the inputs in a form?",
             "options": ["<input>","<form>","<group>","<fields>"],
             "answer": 1},
            {"q": "Which tag is best for a long message box?",
             "options": ["<input type=\"text\">","<input type=\"long\">","<textbox>","<textarea>"],
             "answer": 3},
        ])
    },
    # ── CSS TRACK ───────────────────────────────────────────────────────────────
    {
        'track': 'css', 'order': 1, 'title': 'What is CSS?', 'xp_reward': 10,
        'content': """
<p>If HTML is the skeleton of a page, <strong>CSS</strong> is the clothes and makeup! CSS stands for <strong>Cascading Style Sheets</strong>.</p>
<p>CSS rules look like this:</p>
<pre><code>h1 {\n  color: red;\n  font-size: 50px;\n}</code></pre>
<p>Break it down:</p>
<ul>
  <li><strong>Selector</strong> (<code>h1</code>) — which element to style</li>
  <li><strong>Property</strong> (<code>color</code>) — what to change</li>
  <li><strong>Value</strong> (<code>red</code>) — what to set it to</li>
</ul>
<p>You can use colour names (<code>red</code>, <code>blue</code>) or hex codes (<code>#FF0000</code> for red).</p>
<div class="lesson-try-it">
  <p>✏️ <strong>Try it!</strong> In the CSS panel of the Playground:</p>
  <pre><code>h1 { color: #FFB347; font-size: 60px; }\nbody { background: #1e2a3e; }</code></pre>
</div>
""",
        'quiz_json': json.dumps([
            {"q": "CSS stands for…",
             "options": ["Creative Style Syntax","Cascading Style Sheets","Computer Screen Styling","Coloured Style System"],
             "answer": 1},
            {"q": "In a CSS rule, what is the SELECTOR?",
             "options": ["The value after the colon","The part inside the { }","The element you want to style","The property you want to change"],
             "answer": 2},
            {"q": "Which CSS property changes text colour?",
             "options": ["font-color","text-color","color","colour"],
             "answer": 2},
        ])
    },
    {
        'track': 'css', 'order': 2, 'title': 'Colours & Backgrounds', 'xp_reward': 10,
        'content': """
<p>CSS gives you lots of ways to set colours and backgrounds.</p>
<h3>🎨 Colour formats</h3>
<ul>
  <li><strong>Named</strong>: <code>color: tomato;</code></li>
  <li><strong>Hex</strong>: <code>color: #FF6347;</code></li>
  <li><strong>RGB</strong>: <code>color: rgb(255, 99, 71);</code></li>
</ul>
<h3>🖼️ Backgrounds</h3>
<pre><code>body {\n  background-color: #f0f5ff;\n  background-image: url("pattern.png");\n}</code></pre>
<p>The coolest trick: <strong>gradients</strong>!</p>
<pre><code>body {\n  background: linear-gradient(135deg, #FFB347, #9B7EDE);\n}</code></pre>
<div class="lesson-try-it">
  <p>✏️ <strong>Try it!</strong></p>
  <pre><code>body {\n  background: linear-gradient(135deg, #667eea, #764ba2);\n  color: white;\n  font-family: sans-serif;\n  text-align: center;\n  padding: 50px;\n}</code></pre>
</div>
""",
        'quiz_json': json.dumps([
            {"q": "Which is a valid CSS hex colour?",
             "options": ["color: red-255","color: #FF5733","color: rgb-orange","color: 255,0,0"],
             "answer": 1},
            {"q": "How do you make a gradient background in CSS?",
             "options": ["background: gradient(red, blue)","background: mix(red, blue)","background: linear-gradient(red, blue)","background-gradient: linear red blue"],
             "answer": 2},
            {"q": "Which property sets a plain background colour?",
             "options": ["background","background-color","bg-color","color-background"],
             "answer": 1},
        ])
    },
    {
        'track': 'css', 'order': 3, 'title': 'Fonts, Size & Spacing', 'xp_reward': 10,
        'content': """
<p>Typography — the art of setting text — is huge in web design.</p>
<h3>📝 Font properties</h3>
<pre><code>p {\n  font-family: 'Arial', sans-serif;\n  font-size: 18px;\n  font-weight: bold;\n  line-height: 1.6;\n}</code></pre>
<h3>📐 Spacing: margin & padding</h3>
<p><strong>Margin</strong> = space OUTSIDE the element. <strong>Padding</strong> = space INSIDE.</p>
<pre><code>div {\n  margin: 20px;\n  padding: 10px;\n  border: 3px solid #FFB347;\n}</code></pre>
<p>Think of it like a framed picture: padding is the gap inside the frame, margin is the wall space around the frame.</p>
<div class="lesson-try-it">
  <p>✏️ <strong>Try it!</strong></p>
  <pre><code>div {\n  background: white;\n  margin: 30px auto;\n  padding: 20px;\n  border-radius: 20px;\n  width: 300px;\n  box-shadow: 0 10px 30px rgba(0,0,0,0.1);\n}</code></pre>
</div>
""",
        'quiz_json': json.dumps([
            {"q": "What is the difference between margin and padding?",
             "options": ["They are the same thing","Margin is space inside, padding is space outside","Margin is space outside, padding is space inside","Margin is for text, padding is for images"],
             "answer": 2},
            {"q": "Which property rounds the corners of an element?",
             "options": ["corner-radius","border-round","border-radius","round-corners"],
             "answer": 2},
            {"q": "Which unit makes font size relative to the screen?",
             "options": ["px","vw","em","cm"],
             "answer": 1},
        ])
    },
    {
        'track': 'css', 'order': 4, 'title': 'Flexbox Layout', 'xp_reward': 15,
        'content': """
<p><strong>Flexbox</strong> is a CSS superpower for arranging elements in a row or column.</p>
<pre><code>.container {\n  display: flex;\n  gap: 20px;\n  justify-content: center;\n  align-items: center;\n  flex-wrap: wrap;\n}</code></pre>
<p>Key properties:</p>
<ul>
  <li><code>justify-content</code> — horizontal alignment (<code>center</code>, <code>space-between</code>, <code>flex-start</code>)</li>
  <li><code>align-items</code> — vertical alignment (<code>center</code>, <code>flex-start</code>, <code>stretch</code>)</li>
  <li><code>flex-wrap: wrap</code> — items wrap to next line if they don't fit</li>
  <li><code>gap</code> — space between items</li>
</ul>
<div class="lesson-try-it">
  <p>✏️ <strong>Try it!</strong></p>
  <pre><code>&lt;div class="row"&gt;\n  &lt;div class="card"&gt;🎮 Games&lt;/div&gt;\n  &lt;div class="card"&gt;🎨 Art&lt;/div&gt;\n  &lt;div class="card"&gt;🤖 Robots&lt;/div&gt;\n&lt;/div&gt;</code></pre>
  <pre><code>.row { display: flex; gap: 20px; justify-content: center; padding: 30px; }\n.card { background: #9B7EDE; color: white; padding: 20px 30px; border-radius: 20px; font-size: 1.3rem; font-weight: bold; }</code></pre>
</div>
""",
        'quiz_json': json.dumps([
            {"q": "Which CSS property enables flexbox on a container?",
             "options": ["layout: flex","flex: true","display: flex","flex-mode: on"],
             "answer": 2},
            {"q": "Which property controls HORIZONTAL alignment in a flex row?",
             "options": ["align-items","flex-align","justify-content","horizontal-align"],
             "answer": 2},
            {"q": "What does 'flex-wrap: wrap' do?",
             "options": ["Wraps text in italic","Makes items wrap to next line","Wraps the container in a border","Disables flexbox"],
             "answer": 1},
        ])
    },
    {
        'track': 'css', 'order': 5, 'title': 'Animations & Transitions', 'xp_reward': 15,
        'content': """
<p>CSS can animate elements — no JavaScript needed!</p>
<h3>🌀 Transitions — smooth changes on hover</h3>
<pre><code>button {\n  background: #FFB347;\n  transition: background 0.3s, transform 0.2s;\n}\nbutton:hover {\n  background: #9B7EDE;\n  transform: scale(1.1);\n}</code></pre>
<h3>🎬 Keyframe Animations — repeating motion</h3>
<pre><code>@keyframes bounce {\n  0%   { transform: translateY(0); }\n  50%  { transform: translateY(-30px); }\n  100% { transform: translateY(0); }\n}\n\n.ball {\n  animation: bounce 1s infinite;\n}</code></pre>
<p><code>@keyframes</code> defines the motion, then you assign it to an element with the <code>animation</code> property.</p>
<div class="lesson-try-it">
  <p>✏️ <strong>Try it!</strong> Make an emoji bounce:</p>
  <pre><code>&lt;div class="emoji"&gt;🚀&lt;/div&gt;</code></pre>
  <pre><code>@keyframes fly {\n  0%,100% { transform: translateY(0) rotate(0deg); }\n  50% { transform: translateY(-40px) rotate(10deg); }\n}\n.emoji { font-size: 5rem; text-align: center; margin-top: 50px; animation: fly 2s infinite; }</code></pre>
</div>
""",
        'quiz_json': json.dumps([
            {"q": "Which CSS property makes a smooth colour change on hover?",
             "options": ["animation","transform","transition","keyframes"],
             "answer": 2},
            {"q": "What does 'animation: bounce 1s infinite' mean?",
             "options": ["Play bounce once for 1 second","Play bounce for 1 second then stop","Play bounce animation every 1 second, forever","Bounce by 1 pixel infinitely"],
             "answer": 2},
            {"q": "Which keyword starts a CSS animation definition?",
             "options": ["@animation","@keyframes","@motion","@frames"],
             "answer": 1},
        ])
    },
    # ── JAVASCRIPT TRACK ─────────────────────────────────────────────────────────
    {
        'track': 'javascript', 'order': 1, 'title': 'Variables & Data Types', 'xp_reward': 10,
        'content': """
<p>JavaScript (JS) makes web pages <strong>interactive</strong> — clicks, games, forms that react!</p>
<h3>📦 Variables — storing information</h3>
<pre><code>let name = "Karabo";\nlet age = 12;\nlet isCool = true;\n\nconsole.log(name); // prints: Karabo</code></pre>
<ul>
  <li><code>let</code> — a variable you can change later</li>
  <li><code>const</code> — a value that never changes</li>
  <li><code>var</code> — the old way (avoid it)</li>
</ul>
<h3>🧱 Data types</h3>
<ul>
  <li><strong>String</strong>: text in quotes → <code>"hello"</code></li>
  <li><strong>Number</strong>: a number → <code>42</code></li>
  <li><strong>Boolean</strong>: true or false → <code>true</code></li>
</ul>
<div class="lesson-try-it">
  <p>✏️ <strong>Try it!</strong> In the JS panel:</p>
  <pre><code>let myName = "Your name here";\nlet myAge = 12;\nalert("Hi! I am " + myName + " and I am " + myAge + " years old!");</code></pre>
</div>
""",
        'quiz_json': json.dumps([
            {"q": "Which keyword creates a variable you can change later?",
             "options": ["const","fixed","let","var"],
             "answer": 2},
            {"q": "What data type is: \"Hello World\"?",
             "options": ["Number","Boolean","String","Variable"],
             "answer": 2},
            {"q": "What does console.log() do?",
             "options": ["Shows an alert popup","Logs text to the browser console","Creates a variable","Adds text to the page"],
             "answer": 1},
        ])
    },
    {
        'track': 'javascript', 'order': 2, 'title': 'If Statements & Logic', 'xp_reward': 10,
        'content': """
<p><strong>If statements</strong> let your code make decisions!</p>
<pre><code>let score = 85;\n\nif (score >= 90) {\n  alert("A - Amazing!");\n} else if (score >= 70) {\n  alert("B - Good job!");\n} else {\n  alert("Keep practising!");\n}</code></pre>
<h3>⚖️ Comparison operators</h3>
<ul>
  <li><code>===</code> — exactly equal</li>
  <li><code>!==</code> — not equal</li>
  <li><code>&gt;</code> — greater than</li>
  <li><code>&lt;</code> — less than</li>
  <li><code>&gt;=</code> — greater than or equal</li>
</ul>
<h3>🔗 Logical operators</h3>
<ul>
  <li><code>&&</code> — AND (both must be true)</li>
  <li><code>||</code> — OR (at least one must be true)</li>
  <li><code>!</code> — NOT (flip true to false)</li>
</ul>
<div class="lesson-try-it">
  <p>✏️ <strong>Try it!</strong></p>
  <pre><code>let password = prompt("Enter the secret password:");\nif (password === "nexa123") {\n  alert("✅ Access granted! Welcome, pal!");\n} else {\n  alert("❌ Wrong password. Try again!");\n}</code></pre>
</div>
""",
        'quiz_json': json.dumps([
            {"q": "Which operator checks if two values are EXACTLY equal?",
             "options": ["==","=","===","equals"],
             "answer": 2},
            {"q": "What does the && operator mean?",
             "options": ["OR","NOT","AND","EQUALS"],
             "answer": 2},
            {"q": "What runs when the if condition is FALSE?",
             "options": ["The if block again","The else block","Nothing happens","The whole page reloads"],
             "answer": 1},
        ])
    },
    {
        'track': 'javascript', 'order': 3, 'title': 'Functions', 'xp_reward': 10,
        'content': """
<p>A <strong>function</strong> is a named block of code you can use over and over.</p>
<pre><code>function greet(name) {\n  return "Hello, " + name + "! 👋";\n}\n\nlet message = greet("Thabiso");\nalert(message); // "Hello, Thabiso! 👋"</code></pre>
<p>Functions can take <strong>parameters</strong> (inputs) and <strong>return</strong> a value (output).</p>
<h3>➡️ Arrow functions (short version)</h3>
<pre><code>const double = (n) => n * 2;\nconsole.log(double(5)); // 10</code></pre>
<h3>🎯 Why use functions?</h3>
<ul>
  <li>Write code once, use it many times</li>
  <li>Keep your code tidy and readable</li>
  <li>Easy to fix — change the function, it changes everywhere</li>
</ul>
<div class="lesson-try-it">
  <p>✏️ <strong>Try it!</strong></p>
  <pre><code>function calculateScore(correct, total) {\n  let percent = Math.round((correct / total) * 100);\n  return "You got " + percent + "%!";\n}\nalert(calculateScore(8, 10)); // "You got 80%!"</code></pre>
</div>
""",
        'quiz_json': json.dumps([
            {"q": "What keyword defines a function?",
             "options": ["def","fn","function","make"],
             "answer": 2},
            {"q": "What does 'return' do in a function?",
             "options": ["Exits the whole program","Sends a value back to where the function was called","Repeats the function","Deletes the function"],
             "answer": 1},
            {"q": "What are the inputs to a function called?",
             "options": ["Returns","Arguments/Parameters","Inputs","Variables"],
             "answer": 1},
        ])
    },
    {
        'track': 'javascript', 'order': 4, 'title': 'DOM — Changing the Page', 'xp_reward': 15,
        'content': """
<p>The DOM (Document Object Model) lets JavaScript <strong>talk to your HTML</strong> and change it live!</p>
<h3>🔍 Finding elements</h3>
<pre><code>// Find by ID\nlet title = document.getElementById("myTitle");\n\n// Find by CSS class\nlet cards = document.querySelectorAll(".card");</code></pre>
<h3>✏️ Changing things</h3>
<pre><code>// Change text\ntitle.textContent = "New Title!";\n\n// Change style\ntitle.style.color = "red";\ntitle.style.fontSize = "3rem";\n\n// Add/remove CSS classes\ntitle.classList.add("highlight");\ntitle.classList.remove("hidden");</code></pre>
<h3>🖱️ Responding to clicks</h3>
<pre><code>let btn = document.getElementById("myBtn");\nbtn.addEventListener("click", function() {\n  alert("You clicked me!");\n});</code></pre>
<div class="lesson-try-it">
  <p>✏️ <strong>Try it!</strong></p>
  <pre><code>&lt;h1 id="title"&gt;Click the button!&lt;/h1&gt;\n&lt;button id="btn"&gt;Change Me&lt;/button&gt;</code></pre>
  <pre><code>let colours = ["#FFB347","#9B7EDE","#5D9BEC","#1e5f4b"];\nlet i = 0;\ndocument.getElementById("btn").addEventListener("click", () => {\n  document.getElementById("title").style.color = colours[i % colours.length];\n  document.getElementById("title").textContent = "Colour #" + (i+1);\n  i++;\n});</code></pre>
</div>
""",
        'quiz_json': json.dumps([
            {"q": "What does document.getElementById('x') do?",
             "options": ["Deletes the element with id x","Creates an element with id x","Finds and returns the element with id x","Changes the element's id to x"],
             "answer": 2},
            {"q": "How do you change an element's text with JavaScript?",
             "options": ["element.text = 'new'","element.html = 'new'","element.textContent = 'new'","element.write = 'new'"],
             "answer": 2},
            {"q": "Which method listens for a button click?",
             "options": ["element.onClick()","element.listenClick()","element.addEventListener('click', fn)","element.onPress(fn)"],
             "answer": 2},
        ])
    },
    {
        'track': 'javascript', 'order': 5, 'title': 'Loops & Arrays', 'xp_reward': 15,
        'content': """
<p><strong>Arrays</strong> store lists of things. <strong>Loops</strong> repeat code.</p>
<h3>📋 Arrays</h3>
<pre><code>let fruits = ["apple", "banana", "mango"];\nconsole.log(fruits[0]); // "apple"  (index starts at 0!)\nconsole.log(fruits.length); // 3\n\nfruits.push("pineapple"); // add to end\nfruits.pop();             // remove from end</code></pre>
<h3>🔁 For Loop</h3>
<pre><code>for (let i = 0; i &lt; 5; i++) {\n  console.log("Round " + i);\n}</code></pre>
<h3>🔁 For…of (easier for arrays)</h3>
<pre><code>for (let fruit of fruits) {\n  console.log("I love " + fruit);\n}</code></pre>
<div class="lesson-try-it">
  <p>✏️ <strong>Try it!</strong> Make a list appear on the page:</p>
  <pre><code>&lt;ul id="list"&gt;&lt;/ul&gt;</code></pre>
  <pre><code>let games = ["Snake", "Flappy Bird", "Pac-Man", "Tetris"];\nlet ul = document.getElementById("list");\nfor (let game of games) {\n  let li = document.createElement("li");\n  li.textContent = "🎮 " + game;\n  ul.appendChild(li);\n}</code></pre>
</div>
""",
        'quiz_json': json.dumps([
            {"q": "What index does the FIRST item in an array have?",
             "options": ["1","0","-1","First"],
             "answer": 1},
            {"q": "Which method adds an item to the END of an array?",
             "options": ["array.add()","array.append()","array.push()","array.insert()"],
             "answer": 2},
            {"q": "What does a for loop do?",
             "options": ["Runs code once","Runs code a set number of times","Checks a condition once","Creates an array"],
             "answer": 1},
        ])
    },
    {
        'track': 'javascript', 'order': 6, 'title': 'Build a Clicker Game', 'xp_reward': 25,
        'content': """
<p>Let's put everything together and build a real game! A <strong>clicker game</strong> tracks how many times you click and rewards you with levels.</p>
<p>Here's the full game — read through each part and understand it:</p>
<pre><code>&lt;!-- HTML --&gt;\n&lt;div style="text-align:center; font-family:sans-serif; padding:30px;"&gt;\n  &lt;h1 id="level"&gt;Level 1 🐣&lt;/h1&gt;\n  &lt;p id="score"&gt;Clicks: 0&lt;/p&gt;\n  &lt;button id="btn" style="font-size:4rem; border:none; background:none; cursor:pointer;"&gt;🥚&lt;/button&gt;\n  &lt;p id="msg"&gt;&lt;/p&gt;\n&lt;/div&gt;</code></pre>
<pre><code>// JavaScript\nlet clicks = 0;\nconst levels = [\n  { at: 0,   emoji: "🥚", name: "Level 1 🐣" },\n  { at: 10,  emoji: "🐣", name: "Level 2 🐥" },\n  { at: 30,  emoji: "🐥", name: "Level 3 🐔" },\n  { at: 60,  emoji: "🐔", name: "Level 4 🦅" },\n  { at: 100, emoji: "🦅", name: "Level 5 🚀" },\n];\n\ndocument.getElementById("btn").addEventListener("click", () => {\n  clicks++;\n  document.getElementById("score").textContent = "Clicks: " + clicks;\n\n  // Check for level up\n  for (let i = levels.length - 1; i &gt;= 0; i--) {\n    if (clicks &gt;= levels[i].at) {\n      document.getElementById("btn").textContent = levels[i].emoji;\n      document.getElementById("level").textContent = levels[i].name;\n      break;\n    }\n  }\n\n  if (clicks === 100) {\n    document.getElementById("msg").textContent = "🎉 YOU WIN! Ultimate Coder!";\n  }\n});</code></pre>
<div class="lesson-try-it">
  <p>✏️ <strong>Your challenge!</strong> Copy this into the Playground and then modify it: add a new level at 200 clicks, change the emojis, or add a Reset button!</p>
</div>
""",
        'quiz_json': json.dumps([
            {"q": "In the clicker game, what does the 'at' property in each level object mean?",
             "options": ["The emoji to show","The level name","The number of clicks needed to reach that level","The XP reward"],
             "answer": 2},
            {"q": "Why does the level-checking loop go backwards (from the end)?",
             "options": ["It's faster","To find the highest level the player has reached","Arrays must always be looped backwards","It doesn't matter"],
             "answer": 1},
            {"q": "What JavaScript method attaches the click handler to the button?",
             "options": ["btn.onClick()","btn.click()","btn.addEventListener('click', fn)","btn.on('click', fn)"],
             "answer": 2},
        ])
    },
]

GAME_TEMPLATES = [
    {
        'name': 'Snake Game',
        'description': 'Classic snake — eat food, grow longer, don\'t hit the walls!',
        'difficulty': 'intermediate',
        'icon': 'fa-worm',
        'color': '#1e5f4b',
        'category': 'game',
        'order': 10,
        'html_code': '<canvas id="c" width="400" height="400"></canvas>',
        'css_code': 'body{background:#1e2a3e;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;flex-direction:column;font-family:sans-serif;color:white} #c{border:4px solid #FFB347;border-radius:8px} #info{margin-top:10px;font-size:1.2rem;}',
        'js_code': '''const c=document.getElementById('c'),ctx=c.getContext('2d');
const SZ=20,COLS=20,ROWS=20;
let snake=[{x:10,y:10}],dir={x:1,y:0},food={},score=0,running=true;
function rndFood(){food={x:Math.floor(Math.random()*COLS),y:Math.floor(Math.random()*ROWS)};}
rndFood();
document.addEventListener('keydown',e=>{
  if(e.key==='ArrowUp'&&dir.y===0)dir={x:0,y:-1};
  if(e.key==='ArrowDown'&&dir.y===0)dir={x:0,y:1};
  if(e.key==='ArrowLeft'&&dir.x===0)dir={x:-1,y:0};
  if(e.key==='ArrowRight'&&dir.x===0)dir={x:1,y:0};
});
function draw(){
  ctx.fillStyle='#1e2a3e';ctx.fillRect(0,0,400,400);
  // food
  ctx.fillStyle='#FFB347';ctx.fillRect(food.x*SZ+2,food.y*SZ+2,SZ-4,SZ-4);
  // snake
  snake.forEach((s,i)=>{ctx.fillStyle=i===0?'#9B7EDE':'#5D9BEC';ctx.fillRect(s.x*SZ+1,s.y*SZ+1,SZ-2,SZ-2);});
  // score
  ctx.fillStyle='white';ctx.font='16px sans-serif';ctx.fillText('Score: '+score,8,20);
  if(!running){ctx.fillStyle='rgba(0,0,0,0.6)';ctx.fillRect(0,0,400,400);ctx.fillStyle='#FFB347';ctx.font='bold 32px sans-serif';ctx.textAlign='center';ctx.fillText('Game Over!',200,180);ctx.font='20px sans-serif';ctx.fillText('Score: '+score,200,220);ctx.fillText('Refresh to play again',200,260);}
}
function update(){
  if(!running)return;
  const head={x:snake[0].x+dir.x,y:snake[0].y+dir.y};
  if(head.x<0||head.x>=COLS||head.y<0||head.y>=ROWS){running=false;return;}
  if(snake.some(s=>s.x===head.x&&s.y===head.y)){running=false;return;}
  snake.unshift(head);
  if(head.x===food.x&&head.y===food.y){score++;rndFood();}
  else snake.pop();
}
setInterval(()=>{update();draw();},120);
'''
    },
    {
        'name': 'Memory Match',
        'description': 'Flip cards and find matching pairs — train your memory!',
        'difficulty': 'beginner',
        'icon': 'fa-brain',
        'color': '#9B7EDE',
        'category': 'game',
        'order': 11,
        'html_code': '<div id="grid"></div><div id="info">Pairs found: <span id="pairs">0</span>/8 &nbsp; Moves: <span id="moves">0</span></div>',
        'css_code': 'body{font-family:sans-serif;text-align:center;background:#f0f5ff;padding:20px} #grid{display:grid;grid-template-columns:repeat(4,90px);gap:10px;justify-content:center;margin:20px auto} .card{width:90px;height:90px;font-size:2.5rem;display:flex;align-items:center;justify-content:center;background:#9B7EDE;border-radius:16px;cursor:pointer;border:4px solid #FFB347;box-shadow:0 6px 0 #6B4F9E;transition:.2s;user-select:none} .card.flipped{background:white;box-shadow:0 2px 0 #ccc} .card.matched{background:#1e5f4b;border-color:#1e5f4b;box-shadow:none;cursor:default} #info{font-size:1.2rem;font-weight:600;color:#1e3a5f;margin-top:10px}',
        'js_code': '''const emojis=['🎮','🌟','🎨','🚀','🦄','🎵','🌈','🔥'];
let cards=[...emojis,...emojis].sort(()=>Math.random()-.5);
let flipped=[],matched=0,moves=0,locked=false;
const grid=document.getElementById('grid');
cards.forEach((e,i)=>{
  const d=document.createElement('div');
  d.className='card';d.dataset.val=e;d.dataset.idx=i;
  d.addEventListener('click',()=>flip(d));
  grid.appendChild(d);
});
function flip(d){
  if(locked||d.classList.contains('flipped')||d.classList.contains('matched'))return;
  d.classList.add('flipped');d.textContent=d.dataset.val;
  flipped.push(d);
  if(flipped.length===2){
    moves++;document.getElementById('moves').textContent=moves;locked=true;
    if(flipped[0].dataset.val===flipped[1].dataset.val){
      flipped.forEach(c=>c.classList.add('matched'));
      matched++;document.getElementById('pairs').textContent=matched;
      flipped=[];locked=false;
      if(matched===8)setTimeout(()=>alert('🎉 You won in '+moves+' moves!'),200);
    } else {
      setTimeout(()=>{flipped.forEach(c=>{c.classList.remove('flipped');c.textContent='';});flipped=[];locked=false;},900);
    }
  }
}
'''
    },
    {
        'name': 'Catch the Stars',
        'description': 'Move your basket with arrow keys and catch falling stars!',
        'difficulty': 'beginner',
        'icon': 'fa-star',
        'color': '#FFB347',
        'category': 'game',
        'order': 12,
        'html_code': '<canvas id="c" width="400" height="500"></canvas>',
        'css_code': 'body{background:#1e2a3e;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;flex-direction:column;font-family:sans-serif;color:white}#c{border:4px solid #FFB347;border-radius:8px}',
        'js_code': '''const c=document.getElementById('c'),ctx=c.getContext('2d');
let basket={x:160,w:80,y:450,h:20},stars=[],score=0,lives=3,spd=2.5;
function addStar(){stars.push({x:Math.random()*360+20,y:-20,r:15,spd:spd+(Math.random()*2)});}
setInterval(addStar,1200);
document.addEventListener('keydown',e=>{if(e.key==='ArrowLeft')basket.x=Math.max(0,basket.x-30);if(e.key==='ArrowRight')basket.x=Math.min(320,basket.x+30);});
function loop(){
  ctx.clearRect(0,0,400,500);
  // basket
  ctx.fillStyle='#FFB347';ctx.beginPath();ctx.roundRect(basket.x,basket.y,basket.w,basket.h,8);ctx.fill();
  // stars
  stars=stars.filter(s=>{
    s.y+=s.spd;
    ctx.fillStyle='#FFE347';ctx.font='24px sans-serif';ctx.fillText('⭐',s.x-12,s.y+10);
    if(s.y>450&&s.x+15>basket.x&&s.x-15<basket.x+basket.w){score++;spd=2.5+score*0.05;return false;}
    if(s.y>510){lives--;return false;}
    return true;
  });
  ctx.fillStyle='white';ctx.font='18px sans-serif';ctx.fillText('⭐ '+score,10,28);ctx.fillText('❤️ '+lives,340,28);
  if(lives<=0){ctx.fillStyle='rgba(0,0,0,.6)';ctx.fillRect(0,0,400,500);ctx.fillStyle='#FFB347';ctx.font='bold 32px sans-serif';ctx.textAlign='center';ctx.fillText('Game Over!',200,220);ctx.fillText('Score: '+score,200,268);return;}
  requestAnimationFrame(loop);
}
loop();
'''
    },
    {
        'name': 'Typing Speed Test',
        'description': 'How fast can you type? Race the clock and beat your high score!',
        'difficulty': 'beginner',
        'icon': 'fa-keyboard',
        'color': '#5D9BEC',
        'category': 'game',
        'order': 13,
        'html_code': '''<div id="app">
  <h2>⌨️ Typing Speed Test</h2>
  <div id="wordDisplay"></div>
  <input id="typeInput" placeholder="Start typing to begin!" autocomplete="off">
  <div id="stats">Time: <span id="timer">30</span>s &nbsp; Score: <span id="score">0</span> &nbsp; WPM: <span id="wpm">0</span></div>
  <button id="restart">🔄 Restart</button>
</div>''',
        'css_code': '''body{font-family:sans-serif;background:#f0f5ff;display:flex;justify-content:center;padding:30px}
#app{text-align:center;max-width:500px;width:100%}
#wordDisplay{font-size:2rem;font-weight:700;margin:20px 0;padding:20px;background:white;border-radius:20px;border:4px solid #FFB347;min-height:80px;color:#1e3a5f}
#wordDisplay span.correct{color:#1e5f4b}#wordDisplay span.wrong{color:#e25c5c}
#typeInput{width:90%;padding:12px;font-size:1.2rem;border:4px solid #9B7EDE;border-radius:30px;text-align:center;outline:none;margin:10px}
#stats{font-size:1.1rem;font-weight:600;color:#3A6EA5;margin:15px}
#restart{background:#FFB347;border:none;border-bottom:5px solid #C17D2E;padding:10px 30px;font-size:1.1rem;font-weight:700;border-radius:30px;cursor:pointer}''',
        'js_code': '''const words="the quick brown fox jumps over the lazy dog code is fun stars shine bright make games learn python create art explore worlds".split(" ");
let timeLeft=30,score=0,timerRunning=false,timer,current="";
function getWord(){return words[Math.floor(Math.random()*words.length)];}
function newWord(){current=getWord();document.getElementById("wordDisplay").textContent=current;document.getElementById("typeInput").value="";}
newWord();
document.getElementById("typeInput").addEventListener("input",e=>{
  if(!timerRunning){timerRunning=true;timer=setInterval(tick,1000);}
  let val=e.target.value;
  let disp=current.split("").map((ch,i)=>{
    if(i>=val.length)return `<span>${ch}</span>`;
    return val[i]===ch?`<span class="correct">${ch}</span>`:`<span class="wrong">${ch}</span>`;
  }).join("");
  document.getElementById("wordDisplay").innerHTML=disp;
  if(val===current){score++;document.getElementById("score").textContent=score;let wpm=Math.round(score/(((30-timeLeft)||1)/60));document.getElementById("wpm").textContent=wpm;newWord();}
});
function tick(){
  timeLeft--;document.getElementById("timer").textContent=timeLeft;
  if(timeLeft<=0){clearInterval(timer);document.getElementById("typeInput").disabled=true;document.getElementById("wordDisplay").innerHTML=`<b>⏰ Time\'s up! Score: ${score} words</b>`;}
}
document.getElementById("restart").addEventListener("click",()=>{clearInterval(timer);timeLeft=30;score=0;timerRunning=false;document.getElementById("timer").textContent=30;document.getElementById("score").textContent=0;document.getElementById("wpm").textContent=0;document.getElementById("typeInput").disabled=false;document.getElementById("typeInput").value="";newWord();});
'''
    },
    {
        'name': 'Colour Mixer Lab',
        'description': 'Drag RGB sliders and mix your own colours — see the hex code live!',
        'difficulty': 'beginner',
        'icon': 'fa-palette',
        'color': '#FF8B94',
        'category': 'art',
        'order': 14,
        'html_code': '''<div id="app">
  <h2>🎨 Colour Mixer Lab</h2>
  <div id="preview"></div>
  <div id="hex">#000000</div>
  <div class="slider-row"><label>🔴 Red</label><input type="range" id="r" min="0" max="255" value="100"><span id="rv">100</span></div>
  <div class="slider-row"><label>🟢 Green</label><input type="range" id="g" min="0" max="255" value="150"><span id="gv">150</span></div>
  <div class="slider-row"><label>🔵 Blue</label><input type="range" id="b" min="0" max="255" value="200"><span id="bv">200</span></div>
  <button id="copy">📋 Copy Hex Code</button>
</div>''',
        'css_code': '''body{font-family:sans-serif;background:#f0f5ff;display:flex;justify-content:center;padding:20px}
#app{text-align:center;width:100%;max-width:400px}
#preview{width:200px;height:200px;border-radius:50%;border:8px solid white;box-shadow:0 10px 30px rgba(0,0,0,0.2);margin:20px auto;transition:background .1s}
#hex{font-size:2rem;font-weight:700;margin:10px;letter-spacing:3px}
.slider-row{display:flex;align-items:center;gap:10px;margin:10px 0;background:white;padding:10px 15px;border-radius:20px;border:3px solid #FFB347}
label{font-weight:700;min-width:80px;text-align:left}
input[type=range]{flex:1;accent-color:#9B7EDE}
span{min-width:35px;font-weight:700;color:#3A6EA5}
button{background:#FFB347;border:none;border-bottom:5px solid #C17D2E;padding:12px 30px;font-size:1rem;font-weight:700;border-radius:30px;cursor:pointer;margin-top:15px}''',
        'js_code': '''function toHex(n){return n.toString(16).padStart(2,'0');}
function update(){
  let r=document.getElementById('r').value,g=document.getElementById('g').value,b=document.getElementById('b').value;
  document.getElementById('rv').textContent=r;document.getElementById('gv').textContent=g;document.getElementById('bv').textContent=b;
  let hex='#'+toHex(+r)+toHex(+g)+toHex(+b);
  document.getElementById('preview').style.background=hex;
  document.getElementById('hex').textContent=hex;
  document.getElementById('hex').style.color=hex;
}
['r','g','b'].forEach(id=>document.getElementById(id).addEventListener('input',update));
document.getElementById('copy').addEventListener('click',()=>{navigator.clipboard.writeText(document.getElementById('hex').textContent).then(()=>alert('Copied! '+document.getElementById('hex').textContent));});
update();
'''
    },
    {
        'name': 'Beat Maker',
        'description': 'Tap a 4-track loop sequencer and drop beats with your keyboard!',
        'difficulty': 'intermediate',
        'icon': 'fa-music',
        'color': '#6c5ce7',
        'category': 'art',
        'order': 15,
        'html_code': '''<div id="app">
  <h2>🎵 Beat Maker</h2>
  <div id="grid"></div>
  <div id="controls">
    <button id="play">▶ Play</button>
    <button id="stop">⏹ Stop</button>
    <button id="clear">🗑 Clear</button>
    <label>BPM: <input type="range" id="bpm" min="60" max="200" value="120"><span id="bpmVal">120</span></label>
  </div>
  <p id="hint">Click cells to toggle beats, then hit Play!</p>
</div>''',
        'css_code': '''body{font-family:sans-serif;background:#1e2a3e;color:white;display:flex;justify-content:center;padding:20px}
#app{text-align:center;max-width:600px;width:100%}
#grid{display:grid;grid-template-columns:80px repeat(16,1fr);gap:4px;margin:20px 0}
.lbl{display:flex;align-items:center;justify-content:flex-end;padding-right:8px;font-weight:700;font-size:.85rem;color:#FFB347}
.cell{height:32px;border-radius:6px;background:#2d3f5a;cursor:pointer;transition:.1s;border:2px solid transparent}
.cell.on{background:#FFB347;border-color:#C17D2E}
.cell.active{border-color:#9B7EDE!important}
.cell:hover{opacity:.8}
#controls{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;align-items:center;margin:10px}
button{background:#9B7EDE;color:white;border:none;border-bottom:4px solid #6B4F9E;padding:10px 20px;font-size:1rem;font-weight:700;border-radius:20px;cursor:pointer}
label{color:#FFB347;font-weight:600}input[type=range]{accent-color:#FFB347;vertical-align:middle}
#hint{color:#5D9BEC;font-size:.9rem}''',
        'js_code': '''const tracks=[{name:'Kick 🥁',freq:60,type:'sine'},{name:'Snare 🪘',freq:200,type:'sawtooth'},{name:'Hi-Hat 🔔',freq:800,type:'square'},{name:'Bass 🎸',freq:100,type:'triangle'}];
const STEPS=16;
let grid=tracks.map(()=>Array(STEPS).fill(false));
let playing=false,step=0,intervalId=null;
const ctx2=new AudioContext();
function beep(freq,type,dur=0.1){
  let o=ctx2.createOscillator(),g=ctx2.createGain();
  o.connect(g);g.connect(ctx2.destination);
  o.type=type;o.frequency.value=freq;
  g.gain.setValueAtTime(.4,ctx2.currentTime);
  g.gain.exponentialRampToValueAtTime(.001,ctx2.currentTime+dur);
  o.start();o.stop(ctx2.currentTime+dur);
}
// build grid
const gridEl=document.getElementById('grid');
tracks.forEach((t,ti)=>{
  let lbl=document.createElement('div');lbl.className='lbl';lbl.textContent=t.name;gridEl.appendChild(lbl);
  for(let s=0;s<STEPS;s++){
    let cell=document.createElement('div');cell.className='cell';
    cell.id=`c${ti}_${s}`;
    cell.addEventListener('click',()=>{grid[ti][s]=!grid[ti][s];cell.classList.toggle('on',grid[ti][s]);});
    gridEl.appendChild(cell);
  }
});
function tick(){
  // clear last
  for(let ti=0;ti<tracks.length;ti++){let prev=(step-1+STEPS)%STEPS;document.getElementById(`c${ti}_${prev}`)?.classList.remove('active');}
  // play current
  tracks.forEach((t,ti)=>{
    document.getElementById(`c${ti}_${step}`)?.classList.add('active');
    if(grid[ti][step])beep(t.freq,t.type);
  });
  step=(step+1)%STEPS;
}
document.getElementById('play').addEventListener('click',()=>{if(playing)return;playing=true;ctx2.resume();let bpm=+document.getElementById('bpm').value;intervalId=setInterval(tick,60000/bpm/4);});
document.getElementById('stop').addEventListener('click',()=>{playing=false;clearInterval(intervalId);step=0;});
document.getElementById('clear').addEventListener('click',()=>{grid=tracks.map(()=>Array(STEPS).fill(false));document.querySelectorAll('.cell').forEach(c=>{c.classList.remove('on','active');});});
document.getElementById('bpm').addEventListener('input',e=>{document.getElementById('bpmVal').textContent=e.target.value;if(playing){clearInterval(intervalId);intervalId=setInterval(tick,60000/e.target.value/4);}});
'''
    },
]

def seed_database():
    # Project templates (basic ones + game templates)
    if ProjectTemplate.query.count() == 0:
        basics = [
            ('Starter Page', 'A blank page ready for your ideas', 'beginner', 'fa-file-code', '#5D9BEC', '<h1>My Webpage</h1>\n<p>Start editing here!</p>', 'body{font-family:sans-serif;padding:20px;background:#f0f5ff}h1{color:#FFB347}', '', 0, 'general'),
            ('Colour Mixer', 'Blend colours with code', 'beginner', 'fa-palette', '#5D9BEC', '<div id="mixBox">Click to mix!</div>', '#mixBox{width:200px;height:200px;background:linear-gradient(135deg,#FFB347,#9B7EDE);margin:auto;margin-top:50px;text-align:center;line-height:200px;border-radius:20px;color:white;font-weight:bold;cursor:pointer;font-family:sans-serif}', 'document.getElementById("mixBox").addEventListener("click",function(){this.style.background=`hsl(${Math.random()*360},70%,60%)`})', 1, 'general'),
            ('Quiz Maker', 'Build your own quiz game', 'intermediate', 'fa-question-circle', '#1e5f4b', '<h2 style="font-family:sans-serif;text-align:center">Quick Quiz!</h2><p id="q" style="text-align:center;font-family:sans-serif">What is 2 + 2?</p><div style="text-align:center"><button onclick="check(this)">4</button><button onclick="check(this)">5</button></div><p id="result" style="text-align:center;font-family:sans-serif;font-size:1.5rem"></p>', 'body{background:#f0f5ff}button{margin:5px;padding:10px 20px;border-radius:10px;border:none;background:#1e5f4b;color:white;cursor:pointer;font-size:1rem}', 'function check(btn){document.getElementById("result").textContent=btn.textContent==="4"?"Correct! 🎉":"Try again! ❌"}', 2, 'general'),
        ]
        for name, desc, diff, icon, color, html, css, js, order, cat in basics:
            db.session.add(ProjectTemplate(name=name, description=desc, difficulty=diff, icon=icon, color=color, html_code=html, css_code=css, js_code=js, order=order, category=cat))

        for g in GAME_TEMPLATES:
            db.session.add(ProjectTemplate(**g))
        db.session.commit()

    # Lessons
    if Lesson.query.count() == 0:
        for ld in LESSON_DATA:
            db.session.add(Lesson(**ld))
        db.session.commit()

    # Testimonials
    if Testimonial.query.count() == 0:
        for t, a, e in [('I made my first game in 1 hour!','Karabo, 10','🎮'),('Nexa Pals is my favourite!','Relebohile, 11','⭐'),('I taught my little brother!','Lesedi, 12','💪')]:
            db.session.add(Testimonial(text=t, author=a, emoji=e))
        db.session.commit()

    # Users
    if not User.query.filter_by(username='test').first():
        db.session.add(User(username='test', email='demo@nexapals.local', password_hash=generate_password_hash('test123'), role='student'))
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(username='admin', email='admin@nexapals.local', password_hash=generate_password_hash(os.getenv('ADMIN_PASSWORD','nexa-admin-2026')), role='admin'))
    db.session.commit()

with app.app_context():
    db.create_all()
    seed_database()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== AUTH ROUTES ====================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','')
        if len(username) < 3: flash('Username must be at least 3 characters'); return redirect(url_for('signup'))
        if '@' not in email or '.' not in email.split('@')[-1]: flash('Please enter a valid email address'); return redirect(url_for('signup'))
        if len(password) < 4: flash('Password must be at least 4 characters'); return redirect(url_for('signup'))
        if User.query.filter_by(username=username).first(): flash('Username taken'); return redirect(url_for('signup'))
        if User.query.filter_by(email=email).first(): flash('Email already registered'); return redirect(url_for('signup'))
        db.session.add(User(username=username, email=email, password_hash=generate_password_hash(password)))
        db.session.commit()
        flash('Account created! Please log in.')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        ip = request.remote_addr or 'unknown'
        if _is_rate_limited(ip): flash('Too many failed attempts. Please wait 5 minutes.'); return render_template('login.html')
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash(f'Welcome back, {user.username}! 🎉')
            return redirect(url_for('index'))
        _record_failed_login(ip)
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ==================== PAGE ROUTES ====================
@app.route('/')
def index():
    templates = ProjectTemplate.query.filter_by(category='general').order_by(ProjectTemplate.order).limit(6).all()
    testimonials = Testimonial.query.filter_by(is_approved=True).all()
    return render_template('index.html', templates=templates, testimonials=testimonials)

# ── LEARN ────────────────────────────────────────────────────────────────────
@app.route('/learn')
def learn():
    tracks = {'html': [], 'css': [], 'javascript': []}
    progress_map = {}
    if current_user.is_authenticated:
        progs = LessonProgress.query.filter_by(user_id=current_user.id).all()
        progress_map = {p.lesson_id: p for p in progs}
    for track in tracks:
        lessons = Lesson.query.filter_by(track=track).order_by(Lesson.order).all()
        tracks[track] = [(l, progress_map.get(l.id)) for l in lessons]
    total_lessons = sum(len(v) for v in tracks.values())
    completed = sum(1 for p in progress_map.values() if p.completed)
    return render_template('learn.html', tracks=tracks, completed=completed, total_lessons=total_lessons)

@app.route('/learn/<track>/<int:lesson_id>')
@login_required
def lesson(track, lesson_id):
    lesson_obj = Lesson.query.filter_by(id=lesson_id, track=track).first_or_404()
    progress = LessonProgress.query.filter_by(user_id=current_user.id, lesson_id=lesson_id).first()
    all_track_lessons = Lesson.query.filter_by(track=track).order_by(Lesson.order).all()
    idx = next((i for i,l in enumerate(all_track_lessons) if l.id == lesson_id), 0)
    prev_lesson = all_track_lessons[idx-1] if idx > 0 else None
    next_lesson = all_track_lessons[idx+1] if idx < len(all_track_lessons)-1 else None
    quiz = json.loads(lesson_obj.quiz_json) if lesson_obj.quiz_json else []
    return render_template('lesson.html', lesson=lesson_obj, progress=progress,
                           prev_lesson=prev_lesson, next_lesson=next_lesson,
                           track=track, quiz=quiz)

@app.route('/api/lesson/complete', methods=['POST'])
@login_required
def complete_lesson():
    data = request.get_json(silent=True) or {}
    lesson_id = data.get('lesson_id')
    answers = data.get('answers', [])
    lesson_obj = Lesson.query.get(lesson_id)
    if not lesson_obj:
        return jsonify({'success': False, 'message': 'Lesson not found'}), 404
    quiz = json.loads(lesson_obj.quiz_json) if lesson_obj.quiz_json else []
    correct = sum(1 for i, q in enumerate(quiz) if i < len(answers) and answers[i] == q['answer'])
    score = round((correct / len(quiz)) * 100) if quiz else 100
    passed = score >= 70
    prog = LessonProgress.query.filter_by(user_id=current_user.id, lesson_id=lesson_id).first()
    xp_earned = 0
    if not prog:
        prog = LessonProgress(user_id=current_user.id, lesson_id=lesson_id)
        db.session.add(prog)
    if not prog.completed and passed:
        prog.completed = True
        prog.completed_at = datetime.utcnow()
        prog.quiz_passed = True
        prog.score = score
        current_user.xp += lesson_obj.xp_reward
        xp_earned = lesson_obj.xp_reward
    elif passed and score > (prog.score or 0):
        prog.score = score
    db.session.commit()
    return jsonify({'success': True, 'score': score, 'correct': correct, 'total': len(quiz), 'passed': passed, 'xp_earned': xp_earned})

# ── GAMES ────────────────────────────────────────────────────────────────────
@app.route('/games')
def games():
    arcade = ProjectTemplate.query.filter_by(category='game').order_by(ProjectTemplate.order).all()
    art    = ProjectTemplate.query.filter_by(category='art').order_by(ProjectTemplate.order).all()
    return render_template('games.html', arcade=arcade, art=art)

@app.route('/games/play/<int:template_id>')
def play_game(template_id):
    template = ProjectTemplate.query.get_or_404(template_id)
    return render_template('arcade.html', template=template)

# ── EXISTING PAGES ───────────────────────────────────────────────────────────
@app.route('/play')
@login_required
def play():
    user_projects = UserProject.query.filter_by(user_id=current_user.id).order_by(UserProject.updated_at.desc()).all()
    return render_template('play.html', user_projects=user_projects, active_project=None)

@app.route('/play/<int:project_id>')
@login_required
def play_project(project_id):
    project = UserProject.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash("That project doesn't belong to you")
        return redirect(url_for('play'))
    user_projects = UserProject.query.filter_by(user_id=current_user.id).order_by(UserProject.updated_at.desc()).all()
    return render_template('play.html', user_projects=user_projects, active_project=project)

@app.route('/my-projects')
@login_required
def my_projects():
    user_projects = UserProject.query.filter_by(user_id=current_user.id).order_by(UserProject.updated_at.desc()).all()
    return render_template('my_projects.html', user_projects=user_projects)

@app.route('/create')
def create():
    templates = ProjectTemplate.query.order_by(ProjectTemplate.order).all()
    return render_template('create.html', templates=templates)

@app.route('/buddies')
def buddies():
    testimonials = Testimonial.query.filter_by(is_approved=True).all()
    return render_template('buddies.html', testimonials=testimonials)

@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        flash('Admin access only'); return redirect(url_for('index'))
    users = User.query.all()
    projects = UserProject.query.all()
    templates = ProjectTemplate.query.all()
    lessons = Lesson.query.order_by(Lesson.track, Lesson.order).all()
    return render_template('admin.html', users=users, projects=projects, templates=templates, lessons=lessons)

# ==================== ERROR HANDLERS ====================
@app.errorhandler(404)
def not_found(e): return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e): db.session.rollback(); return render_template('500.html'), 500

# ==================== API ENDPOINTS ====================
@app.route('/api/save_project', methods=['POST'])
@login_required
def save_project():
    data = request.get_json(silent=True) or {}
    project_id = data.get('project_id')
    title = (data.get('title') or 'My Project').strip()[:100] or 'My Project'
    html_code = data.get('html_code', '')
    css_code  = data.get('css_code', '')
    js_code   = data.get('js_code', '')
    if project_id:
        project = UserProject.query.get(project_id)
        if not project or project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Project not found'}), 404
        project.title = title; project.html_code = html_code; project.css_code = css_code
        project.js_code = js_code; project.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Updated', 'project_id': project.id})
    new = UserProject(user_id=current_user.id, title=title, html_code=html_code, css_code=css_code, js_code=js_code)
    db.session.add(new); db.session.commit()
    return jsonify({'success': True, 'message': 'Saved', 'project_id': new.id})

@app.route('/api/load_project/<int:project_id>')
@login_required
def load_project(project_id):
    project = UserProject.query.get(project_id)
    if project and project.user_id == current_user.id:
        return jsonify({'success': True, 'project_id': project.id, 'title': project.title, 'html_code': project.html_code, 'css_code': project.css_code, 'js_code': project.js_code})
    return jsonify({'success': False, 'message': 'Project not found'}), 404

@app.route('/api/delete_project/<int:project_id>', methods=['POST'])
@login_required
def delete_project(project_id):
    project = UserProject.query.get(project_id)
    if not project or project.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Project not found'}), 404
    db.session.delete(project); db.session.commit()
    return jsonify({'success': True, 'message': 'Project deleted'})

@app.route('/api/load_template/<int:template_id>')
def load_template(template_id):
    t = ProjectTemplate.query.get(template_id)
    if t: return jsonify({'success': True, 'name': t.name, 'html_code': t.html_code, 'css_code': t.css_code, 'js_code': t.js_code})
    return jsonify({'success': False, 'message': 'Template not found'}), 404

@app.route('/api/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if current_user.role != 'admin': return jsonify({'success': False, 'message': 'Admin access only'}), 403
    if user_id == current_user.id: return jsonify({'success': False, 'message': "Can't delete yourself here"}), 400
    user = User.query.get(user_id)
    if not user: return jsonify({'success': False, 'message': 'User not found'}), 404
    UserProject.query.filter_by(user_id=user.id).delete()
    db.session.delete(user); db.session.commit()
    return jsonify({'success': True, 'message': f'User {user.username} deleted'})

@app.route('/api/admin/delete_project/<int:project_id>', methods=['POST'])
@login_required
def admin_delete_project(project_id):
    if current_user.role != 'admin': return jsonify({'success': False, 'message': 'Admin access only'}), 403
    project = UserProject.query.get(project_id)
    if not project: return jsonify({'success': False, 'message': 'Project not found'}), 404
    db.session.delete(project); db.session.commit()
    return jsonify({'success': True, 'message': 'Project deleted'})

@app.route('/healthz')
def health_check(): return jsonify({'status': 'ok'})

# ==================== ABOUT & CONTACT ====================
CONTACT_EMAIL = os.getenv('CONTACT_EMAIL', 'info@nexapals.co.za')

def _send_contact_email(sender_name, sender_email, subject, message):
    """Send contact form submission to info@nexapals.co.za via Gmail SMTP."""
    smtp_user = os.getenv('SMTP_USER', '')
    smtp_pass = os.getenv('SMTP_PASS', '')
    if not smtp_user or not smtp_pass:
        return False, 'Email not configured'
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'[Nexa Pals Contact] {subject}'
        msg['From']    = smtp_user
        msg['To']      = CONTACT_EMAIL
        msg['Reply-To'] = f'{sender_name} <{sender_email}>'
        body = (
            f'Name: {sender_name}\n'
            f'Email: {sender_email}\n'
            f'Subject: {subject}\n\n'
            f'Message:\n{message}\n\n'
            f'---\nSent via nexapals.co.za contact form'
        )
        msg.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, CONTACT_EMAIL, msg.as_string())
        return True, 'Sent'
    except Exception as e:
        return False, str(e)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name    = request.form.get('name', '').strip()[:100]
        email   = request.form.get('email', '').strip()[:100]
        subject = request.form.get('subject', '').strip()[:200]
        message = request.form.get('message', '').strip()[:2000]
        if not all([name, email, message]):
            flash('Please fill in all required fields.')
            return redirect(url_for('contact'))
        ok, err = _send_contact_email(name, email, subject or 'General Enquiry', message)
        if ok:
            flash(f"Thanks {name}! We'll get back to you at {email} soon. 🎉")
        else:
            # Still show success to user — log the error server-side
            print(f'[CONTACT EMAIL ERROR] {err}')
            flash(f"Thanks {name}! We received your message and will get back to you soon. 🎉")
        return redirect(url_for('contact'))
    return render_template('contact.html')

# ==================== AI PROVIDERS ====================
# Architecture:
#   Fast Chat  → Groq  (llama-3.3-70b-versatile)  — low-latency, real-time tutoring
#   Structured → Gemini (gemini-2.5-flash)          — enforced JSON output for quizzes
#   Fallback   → if Groq hits 429 / outage, seamlessly retry via Gemini
#
# API keys never touch the browser — all calls are server-side proxies.

from groq import Groq as _GroqClient
from google import genai as _genai
from google.genai import types as _genai_types

GROQ_MODEL   = 'llama-3.3-70b-versatile'
GEMINI_MODEL = 'gemini-2.5-flash'

_KID_SAFE = (
    'You are a friendly, encouraging coding tutor for kids aged 10–14 on Nexa Pals. '
    'Never just give the answer — guide the student to understand the concept themselves. '
    'Use simple language, short sentences, and relatable analogies (sport, food, games). '
    'Celebrate effort: phrases like "Great question!", "You\'re so close!", "Nice thinking!". '
    'Keep responses concise (4–7 sentences) unless writing code. '
    'Never produce content that is violent, adult, political, or unrelated to coding. '
    'If asked anything off-topic, warmly redirect back to coding.'
)

# ── Core provider functions ───────────────────────────────────────────────────

def _chat_groq(system: str, messages: list, max_tokens: int = 700) -> str:
    """
    Fast chat via Groq (llama-3.3-70b-versatile).
    messages: list of {'role': 'user'|'assistant', 'content': str}
    Raises groq.RateLimitError on 429, groq.APIStatusError on other API errors.
    """
    api_key = os.getenv('GROQ_API_KEY', '')
    if not api_key:
        raise ValueError('GROQ_API_KEY not set')
    client = _GroqClient(api_key=api_key)
    full_messages = [{'role': 'system', 'content': system}] + messages
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=full_messages,
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return completion.choices[0].message.content

def _chat_gemini(system: str, messages: list, max_tokens: int = 700) -> str:
    """
    Fallback chat via Gemini (gemini-2.5-flash).
    Converts message history to Gemini's Content format.
    """
    api_key = os.getenv('GEMINI_API_KEY', '')
    if not api_key:
        raise ValueError('GEMINI_API_KEY not set')
    client = _genai.Client(api_key=api_key)
    # Gemini takes history as list of Content objects; last user turn is the prompt
    history = []
    for msg in messages[:-1]:
        role = 'user' if msg['role'] == 'user' else 'model'
        history.append(_genai_types.Content(role=role, parts=[_genai_types.Part(text=msg['content'])]))
    last_msg = messages[-1]['content'] if messages else ''
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=history + [_genai_types.Content(role='user', parts=[_genai_types.Part(text=last_msg)])],
        config=_genai_types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=0.7,
        ),
    )
    return response.text

def _quiz_gemini(system: str, prompt: str, max_tokens: int = 1000) -> str:
    """
    Structured JSON quiz generation via Gemini with enforced JSON output.
    Uses responseMimeType='application/json' so the response is always
    valid JSON — no markdown fences to strip.
    """
    api_key = os.getenv('GEMINI_API_KEY', '')
    if not api_key:
        raise ValueError('GEMINI_API_KEY not set')
    client = _genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[_genai_types.Content(role='user', parts=[_genai_types.Part(text=prompt)])],
        config=_genai_types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=0.4,
            response_mime_type='application/json',
        ),
    )
    return response.text

# ── Fallback wrapper ──────────────────────────────────────────────────────────

import groq as _groq_module

def _chat_with_fallback(system: str, messages: list, max_tokens: int = 700) -> tuple[str, str]:
    """
    Try Groq first (fast). On rate-limit (429) or outage, fall back to Gemini.
    Returns (reply_text, provider_used) so callers can log which path was taken.
    """
    try:
        reply = _chat_groq(system, messages, max_tokens)
        return reply, 'groq'
    except ValueError:
        # Groq key missing — try Gemini directly
        pass
    except _groq_module.RateLimitError:
        # 429 — Groq quota hit, route to Gemini
        pass
    except _groq_module.APIStatusError as e:
        # 5xx outage or other server error — route to Gemini
        if e.status_code < 500 and e.status_code != 429:
            raise  # 4xx that isn't rate-limit: re-raise (bad request etc.)
    except Exception:
        pass  # Any unexpected Groq error → try Gemini

    # Gemini fallback
    reply = _chat_gemini(system, messages, max_tokens)
    return reply, 'gemini'

# ── Route helpers ─────────────────────────────────────────────────────────────

def _err(msg, code=503):
    return jsonify({'success': False, 'message': msg}), code

# ── 1. Code Explainer ─────────────────────────────────────────────────────────
@app.route('/api/ai/explain', methods=['POST'])
@login_required
def ai_explain():
    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip()[:2000]
    lang = data.get('lang', 'code')
    if not code:
        return _err('No code provided', 400)
    system = (
        _KID_SAFE +
        'You explain code in plain English for a 10-year-old. '
        'Start with "Here\'s what this code does:" then explain each important part. '
        'Use bullet points. Use simple analogies — compare code to things kids know. '
        'Highlight any cool or clever parts to build excitement about coding.'
    )
    try:
        reply, _ = _chat_with_fallback(
            system,
            [{'role': 'user', 'content': f'Please explain this {lang} code:\n\n```{lang}\n{code}\n```'}]
        )
        return jsonify({'success': True, 'reply': reply})
    except ValueError as e:
        return _err(str(e))
    except Exception:
        return _err('AI unavailable right now — please try again in a moment')

# ── 2. Code Helper (Playground) ───────────────────────────────────────────────
@app.route('/api/ai/help', methods=['POST'])
@login_required
def ai_help():
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()[:500]
    html = (data.get('html') or '')[:1500]
    css  = (data.get('css')  or '')[:1000]
    js   = (data.get('js')   or '')[:1000]
    if not question:
        return _err('Please type a question', 400)
    system = (
        _KID_SAFE +
        'You are helping a kid debug or improve their HTML/CSS/JavaScript project. '
        'Do NOT just give the fixed code — first ask "What do you think is happening?" '
        'or explain the concept behind the bug so they learn. '
        'Then show the corrected code wrapped in ```html, ```css, or ```js fences. '
        'Always explain WHY the fix works. End with an encouraging line.'
    )
    context = f'HTML:\n```html\n{html}\n```\nCSS:\n```css\n{css}\n```\nJS:\n```js\n{js}\n```'
    user_msg = f"Here's my current code:\n\n{context}\n\nMy question: {question}"
    try:
        reply, _ = _chat_with_fallback(system, [{'role': 'user', 'content': user_msg}], max_tokens=900)
        return jsonify({'success': True, 'reply': reply})
    except ValueError as e:
        return _err(str(e))
    except Exception:
        return _err('AI unavailable right now — please try again in a moment')

# ── 3. Lesson Tutor (multi-turn, with history) ────────────────────────────────
@app.route('/api/ai/tutor', methods=['POST'])
@login_required
def ai_tutor():
    data = request.get_json(silent=True) or {}
    question     = (data.get('question') or '').strip()[:500]
    lesson_title = (data.get('lesson_title') or 'this lesson')[:100]
    track        = (data.get('track') or 'web coding')[:20]
    history      = data.get('history', [])[:8]
    if not question:
        return _err('Please type a question', 400)
    system = (
        _KID_SAFE +
        f'You are tutoring a student on the lesson "{lesson_title}" in the {track} track. '
        'Stay focused on THIS lesson topic only — gently redirect if they go off-topic. '
        'Guide with questions: "What do you think would happen if…?", "Can you spot the pattern?". '
        'Give one clear example when helpful, using the lesson\'s own code snippets. '
        'NEVER directly give quiz answers — guide understanding instead. '
        'Remember what the student said earlier in this conversation.'
    )
    messages = []
    for turn in history:
        role    = turn.get('role')
        content = (turn.get('content') or '')[:400]
        if role in ('user', 'assistant') and content:
            messages.append({'role': role, 'content': content})
    messages.append({'role': 'user', 'content': question})
    try:
        reply, _ = _chat_with_fallback(system, messages, max_tokens=700)
        return jsonify({'success': True, 'reply': reply})
    except ValueError as e:
        return _err(str(e))
    except Exception:
        return _err('AI unavailable right now — please try again in a moment')

# ── 4. Project Idea → Code Generator ─────────────────────────────────────────
@app.route('/api/ai/generate', methods=['POST'])
@login_required
def ai_generate():
    data = request.get_json(silent=True) or {}
    idea = (data.get('idea') or '').strip()[:400]
    if not idea:
        return _err('Please describe your idea', 400)
    system = (
        _KID_SAFE +
        'You generate starter HTML/CSS/JS projects for kids based on their idea. '
        'Output ONLY valid JSON with exactly these keys: '
        '"title" (short project name, max 40 chars), '
        '"html" (complete HTML body content, no <html>/<head>/<body> tags), '
        '"css" (all CSS), '
        '"js" (all JavaScript). '
        'Code must be beginner-friendly, well-commented, and interactive. '
        'Keep total code under 80 lines. '
        'Output raw JSON only — no markdown fences, no explanation.'
    )
    try:
        # Use Gemini with enforced JSON for reliable parsing
        raw = _quiz_gemini(system, f'Create a fun web project for this idea: {idea}', max_tokens=1400)
        parsed = json.loads(raw)
        if not {'title', 'html', 'css', 'js'}.issubset(parsed.keys()):
            raise ValueError('Missing keys in AI response')
        return jsonify({'success': True, **{k: parsed[k] for k in ('title', 'html', 'css', 'js')}})
    except (json.JSONDecodeError, ValueError):
        # Gemini failed or key missing — try chat fallback
        try:
            raw2, _ = _chat_with_fallback(system, [{'role': 'user', 'content': f'Create a fun web project for this idea: {idea}'}], max_tokens=1400)
            clean = raw2.strip().strip('`').lstrip('json').strip('`').strip()
            parsed2 = json.loads(clean)
            if not {'title', 'html', 'css', 'js'}.issubset(parsed2.keys()):
                raise ValueError('Missing keys')
            return jsonify({'success': True, **{k: parsed2[k] for k in ('title', 'html', 'css', 'js')}})
        except Exception:
            return _err('AI returned unexpected format — try rephrasing your idea', 500)
    except ValueError as e:
        return _err(str(e))
    except Exception:
        return _err('AI unavailable right now — please try again in a moment')

# ── 5. Admin Quiz Generator (Gemini with enforced JSON) ───────────────────────
@app.route('/api/ai/quiz', methods=['POST'])
@login_required
def ai_quiz():
    if current_user.role != 'admin':
        return _err('Admin access only', 403)
    data  = request.get_json(silent=True) or {}
    topic = (data.get('topic') or '').strip()[:200]
    track = (data.get('track') or 'web coding')[:30]
    count = min(int(data.get('count', 3)), 6)
    if not topic:
        return _err('Please provide a topic', 400)
    system = (
        f'You generate multiple-choice quiz questions about web coding for kids aged 10–14. '
        f'Output ONLY a JSON array of exactly {count} question objects. '
        'Each object must have: '
        '"q" (question string), '
        '"options" (array of exactly 4 answer strings), '
        '"answer" (0-based integer index of the correct option). '
        'Questions must test understanding, not just memorisation. '
        'Language must be simple and age-appropriate. '
        'Output a raw JSON array only.'
    )
    prompt = f'Generate {count} quiz questions about: {topic} (track: {track})'
    try:
        # Gemini primary — enforced JSON means no fences to strip, reliable parse every time
        raw = _quiz_gemini(system, prompt, max_tokens=1000)
        questions = json.loads(raw)
        if not isinstance(questions, list):
            raise ValueError('Expected a JSON array')
        for q in questions:
            if not {'q', 'options', 'answer'}.issubset(q.keys()):
                raise ValueError('Missing question fields')
            if len(q['options']) != 4:
                raise ValueError('Each question must have exactly 4 options')
        return jsonify({'success': True, 'questions': questions})
    except (json.JSONDecodeError, ValueError) as e:
        # Gemini JSON failed — fallback to Groq chat with manual parse
        try:
            raw2, _ = _chat_with_fallback(system, [{'role': 'user', 'content': prompt}], max_tokens=1000)
            clean = raw2.strip().strip('`').lstrip('json').strip('`').strip()
            questions2 = json.loads(clean)
            if not isinstance(questions2, list):
                raise ValueError('Expected array')
            return jsonify({'success': True, 'questions': questions2})
        except Exception:
            return _err(f'AI returned unexpected format — try again: {e}', 500)
    except ValueError as e:
        return _err(str(e))
    except Exception:
        return _err('AI unavailable right now — please try again in a moment')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
