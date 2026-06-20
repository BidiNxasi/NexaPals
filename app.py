import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

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

class Testimonial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(300), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    emoji = db.Column(db.String(10), default='⭐')
    is_approved = db.Column(db.Boolean, default=True)

# ==================== SIMPLE LOGIN RATE LIMITING ====================
# In-memory tracker: {ip: [timestamps of failed attempts]}. Resets on restart;
# fine for a small app, not meant to replace a real rate-limit backend at scale.
from collections import defaultdict
import time as _time
_failed_logins = defaultdict(list)
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300  # 5 minutes

def _is_rate_limited(ip):
    now = _time.time()
    _failed_logins[ip] = [t for t in _failed_logins[ip] if now - t < LOGIN_WINDOW_SECONDS]
    return len(_failed_logins[ip]) >= LOGIN_MAX_ATTEMPTS

def _record_failed_login(ip):
    _failed_logins[ip].append(_time.time())

# Create tables
with app.app_context():
    db.create_all()
    if ProjectTemplate.query.count() == 0:
        samples = [
            ('Dino Run', 'Jump & run game', 'beginner', 'fa-dragon', '#FFB347',
             '<h1>Dino Run</h1><p>Click to jump!</p>',
             'body{font-family:Arial;text-align:center;margin-top:50px}',
             'document.addEventListener("click",()=>alert("Jump!"))'),
            ('Beat Box', 'Make music with keys', 'intermediate', 'fa-music', '#9B7EDE',
             '<div id="pad">Press A,S,D,F</div>',
             '#pad{width:200px;height:200px;background:#9B7EDE;margin:auto;line-height:200px}',
             'document.addEventListener("keydown",(e)=>alert(e.key+" sound!"))'),
            ('Colour Mixer', 'Blend colours with code', 'beginner', 'fa-palette', '#5D9BEC',
             '<div id="mixBox">Click to mix!</div>',
             '#mixBox{width:200px;height:200px;background:linear-gradient(135deg,#FFB347,#9B7EDE);margin:auto;text-align:center;line-height:200px;border-radius:20px;color:white;font-weight:bold;cursor:pointer}',
             'document.getElementById("mixBox").addEventListener("click",function(){this.style.background=`hsl(${Math.random()*360},70%,60%)`})'),
            ('Quiz Maker', 'Build your own quiz game', 'intermediate', 'fa-question-circle', '#1e5f4b',
             '<h2>Quick Quiz!</h2><p id="q">What is 2 + 2?</p><button onclick="check()">4</button><button onclick="check()">5</button><p id="result"></p>',
             'body{font-family:Arial;text-align:center;margin-top:30px} button{margin:5px;padding:10px 20px;border-radius:10px;border:none;background:#1e5f4b;color:white;cursor:pointer}',
             'function check(){document.getElementById("result").textContent=event.target.textContent==="4"?"Correct! 🎉":"Try again!"}'),
        ]
        for name, desc, diff, icon, color, html, css, js in samples:
            db.session.add(ProjectTemplate(name=name, description=desc, difficulty=diff,
                          icon=icon, color=color, html_code=html, css_code=css, js_code=js))
        db.session.commit()

    if Testimonial.query.count() == 0:
        testimonial_samples = [
            ('I made my first game in 1 hour!', 'Karabo, 10', '🎮'),
            ('Nexa Pals is my favorite!', 'Relebohile, 11', '⭐'),
            ('I taught my little brother!', 'Lesedi, 12', '💪'),
        ]
        for text, author, emoji in testimonial_samples:
            db.session.add(Testimonial(text=text, author=author, emoji=emoji))
        db.session.commit()

    # Seed a demo account and an admin account if they don't exist yet
    if not User.query.filter_by(username='test').first():
        demo_user = User(
            username='test',
            email='demo@nexapals.local',
            password_hash=generate_password_hash('test123'),
            role='student'
        )
        db.session.add(demo_user)

    if not User.query.filter_by(username='admin').first():
        admin_password = os.getenv('ADMIN_PASSWORD', 'nexa-admin-2026')
        admin_user = User(
            username='admin',
            email='admin@nexapals.local',
            password_hash=generate_password_hash(admin_password),
            role='admin'
        )
        db.session.add(admin_user)

    db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== AUTH ROUTES ====================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if len(username) < 3:
            flash('Username must be at least 3 characters')
            return redirect(url_for('signup'))
        if '@' not in email or '.' not in email.split('@')[-1]:
            flash('Please enter a valid email address')
            return redirect(url_for('signup'))
        if len(password) < 4:
            flash('Password must be at least 4 characters')
            return redirect(url_for('signup'))
        if User.query.filter_by(username=username).first():
            flash('Username exists')
            return redirect(url_for('signup'))
        if User.query.filter_by(email=email).first():
            flash('Email registered')
            return redirect(url_for('signup'))
        hashed = generate_password_hash(password)
        user = User(username=username, email=email, password_hash=hashed)
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please log in.')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        ip = request.remote_addr or 'unknown'
        if _is_rate_limited(ip):
            flash('Too many failed login attempts. Please wait a few minutes and try again.')
            return render_template('login.html')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
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
    templates = ProjectTemplate.query.order_by(ProjectTemplate.order).limit(12).all()
    testimonials = Testimonial.query.filter_by(is_approved=True).all()
    return render_template('index.html', templates=templates, testimonials=testimonials)

@app.route('/learn')
def learn():
    return render_template('learn.html')

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
        flash('Admin access only')
        return redirect(url_for('index'))
    users = User.query.all()
    projects = UserProject.query.all()
    templates = ProjectTemplate.query.all()
    return render_template('admin.html', users=users, projects=projects, templates=templates)

# ==================== ERROR HANDLERS ====================
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    db.session.rollback()
    return render_template('500.html'), 500

# ==================== API ENDPOINTS ====================
@app.route('/api/save_project', methods=['POST'])
@login_required
def save_project():
    data = request.get_json(silent=True) or {}
    project_id = data.get('project_id')
    title = (data.get('title') or 'My Project').strip()[:100] or 'My Project'
    html_code = data.get('html_code', '')
    css_code = data.get('css_code', '')
    js_code = data.get('js_code', '')

    if project_id:
        project = UserProject.query.get(project_id)
        if not project or project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Project not found'}), 404
        project.title = title
        project.html_code = html_code
        project.css_code = css_code
        project.js_code = js_code
        project.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Updated', 'project_id': project.id})

    new = UserProject(user_id=current_user.id, title=title, html_code=html_code, css_code=css_code, js_code=js_code)
    db.session.add(new)
    db.session.commit()
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
    db.session.delete(project)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Project deleted'})

@app.route('/api/load_template/<int:template_id>')
def load_template(template_id):
    template = ProjectTemplate.query.get(template_id)
    if template:
        return jsonify({'success': True, 'name': template.name, 'html_code': template.html_code, 'css_code': template.css_code, 'js_code': template.js_code})
    return jsonify({'success': False, 'message': 'Template not found'}), 404

@app.route('/api/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Admin access only'}), 403
    if user_id == current_user.id:
        return jsonify({'success': False, 'message': "You can't delete your own account from here"}), 400
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    UserProject.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True, 'message': f'User {user.username} deleted'})

@app.route('/api/admin/delete_project/<int:project_id>', methods=['POST'])
@login_required
def admin_delete_project(project_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Admin access only'}), 403
    project = UserProject.query.get(project_id)
    if not project:
        return jsonify({'success': False, 'message': 'Project not found'}), 404
    db.session.delete(project)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Project deleted'})

@app.route('/healthz')
def health_check():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)