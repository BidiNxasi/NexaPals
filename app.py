import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
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
        ]
        for name, desc, diff, icon, color, html, css, js in samples:
            db.session.add(ProjectTemplate(name=name, description=desc, difficulty=diff,
                          icon=icon, color=color, html_code=html, css_code=css, js_code=js))
        db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== AUTH ROUTES ====================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
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
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
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
    return render_template('play.html', user_projects=user_projects)

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

# ==================== API ENDPOINTS ====================
@app.route('/api/save_project', methods=['POST'])
@login_required
def save_project():
    data = request.get_json()
    project_id = data.get('project_id')
    title = data.get('title', 'My Project')
    html_code = data.get('html_code', '')
    css_code = data.get('css_code', '')
    js_code = data.get('js_code', '')
    if project_id:
        project = UserProject.query.get(project_id)
        if project and project.user_id == current_user.id:
            project.title = title
            project.html_code = html_code
            project.css_code = css_code
            project.js_code = js_code
            project.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'success': True, 'message': 'Updated'})
    else:
        new = UserProject(user_id=current_user.id, title=title, html_code=html_code, css_code=css_code, js_code=js_code)
        db.session.add(new)
        db.session.commit()
        return jsonify({'success': True, 'project_id': new.id})
    return jsonify({'success': False})

@app.route('/api/load_project/<int:project_id>')
@login_required
def load_project(project_id):
    project = UserProject.query.get(project_id)
    if project and project.user_id == current_user.id:
        return jsonify({'success': True, 'title': project.title, 'html_code': project.html_code, 'css_code': project.css_code, 'js_code': project.js_code})
    return jsonify({'success': False})

@app.route('/api/load_template/<int:template_id>')
def load_template(template_id):
    template = ProjectTemplate.query.get(template_id)
    if template:
        return jsonify({'success': True, 'name': template.name, 'html_code': template.html_code, 'css_code': template.css_code, 'js_code': template.js_code})
    return jsonify({'success': False})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)