# Nexa Pals

A Flask web platform that teaches kids 10+ to code, with a live HTML/CSS/JS playground, starter project templates, saved projects, and an admin dashboard.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 app.py
```

The app runs at `http://localhost:5000`. A SQLite database is created automatically on first run at `instance/database.db`, seeded with:

- 4 starter project templates (Dino Run, Beat Box, Colour Mixer, Quiz Maker)
- 3 sample testimonials
- A demo account: **username `test`, password `test123`**
- An admin account: **username `admin`**, password from `ADMIN_PASSWORD` in `.env` (defaults to `nexa-admin-2026`)

## Environment variables (`.env`)

```
SECRET_KEY=change-me-in-production
ADMIN_PASSWORD=change-me-too
```

## Features

- **Auth** — signup/login/logout with hashed passwords, server-side validation, and basic login rate-limiting (5 failed attempts per IP locks out for 5 minutes).
- **Playground** (`/play`) — live HTML/CSS/JS editor with instant preview. Save, rename, start a new project, or delete the current one. Open any saved project directly at `/play/<id>`.
- **My Projects** (`/my-projects`) — gallery of everything a user has saved, with quick open/delete.
- **Starter templates** (`/create`) — click a template to load it straight into the playground.
- **Admin dashboard** (`/admin`, admin role only) — view all users/projects/templates, delete any user (and their projects) or any project directly from the table.
- **CSRF protection** on every form and API mutation via Flask-WTF.
- **Custom 404/500 pages** and a `/healthz` endpoint for uptime checks.

## Deployment

A `Procfile` is included for platforms like Heroku/Render:

```
web: gunicorn app:app
```

Set `SECRET_KEY` and `ADMIN_PASSWORD` as real environment variables in production rather than relying on `.env`.

## Project structure

```
app.py                  Flask app, models, routes, API
templates/               Jinja2 templates
static/css/style.css     Styles
static/js/script.js      Site interactivity + playground logic
static/images/           Logo and other static images
instance/database.db     SQLite DB (auto-created, gitignored)
```
