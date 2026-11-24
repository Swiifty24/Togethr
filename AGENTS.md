# TOGETHR: guide for AI coding assistants

TOGETHR is a Django web app where friends plan activities and invite each other.
Student project: keep code simple, readable, and commented.

## Layout
This folder (with manage.py) is the project root. Run all commands here.
- `Javier_Flores_WebApp/Javier_Flores_WebApp/` : settings.py and urls.py (project package name is kept).
- `accounts/` : custom User, Profile, EmailVerification, ActivityLog, Notification;
  registration, email-code verification, login, password reset.
- `activities/` : Activity, Category, Participation, Home, My Activities, calendar, invitations.
- `members/` : profile, settings (change password), notifications.
- `adminpanel/` : Admin Home and user management (Super Administrator only).
- `core/` : landing page, error pages, shared context processor, `create_database` command.
- `templates/` and `static/` : shared templates/includes and CSS/JS/images;
  `static/js/location.js` is the opt-in nearby-city helper.
- `media/` : uploaded activity covers and profile pictures (not committed).
- `WebApp_Project/` and `demo/` : old exam apps, left on disk but unused.
- `_her_source/` : read-only reference copy of the original project. Never edit it.
- `.env.example` : safe template. `.env` is private: never read, print, or commit it.
- `db.sqlite3` : old exam database, unused (the app uses MySQL database `togethr`).

## Setup and commands
Create a local virtual environment first, then:
    pip install -r requirements.txt
    copy .env.example .env        # then fill in the values (see the file's comments)
    python manage.py create_database
    python manage.py migrate
    python manage.py createsuperuser
    python manage.py runserver
    python manage.py test accounts activities core

MySQL/MariaDB must be running (XAMPP control panel). Keep `DJANGO_DEBUG=True` for
local development; `DJANGO_SECRET_KEY` is required in `.env` and must never be
hard-coded in settings. Start MySQL before `create_database` and `migrate`.

## Rules
1. Explain your plan before editing. Ask before migrations, deletions, or installs.
2. Plain Django only, no extra packages unless asked.
3. Keep secrets, `.env`, `db.sqlite3`, `media/`, and virtual environments out of Git.
4. Do not weaken login checks: state changes use POST + CSRF, private views use
   `@login_required`, admin views use `superuser_required`, and object access is
   checked in the view.
5. Design work: change only `static/` and `templates/`; do not change behavior,
   URLs, template logic, form fields, or context variable names.
6. After model changes, tell the user to run `makemigrations` and `migrate`.
7. The old exam apps are unused: do not wire their routes back into `urls.py`.
8. City lookup is opt-in: keep the Django proxy, cache and 1-request/second limit,
   never send coordinates straight to a third party, and keep the visible
   "City data © OpenStreetMap contributors" attribution. Browser location only
   works on HTTPS/localhost and falls back to manual entry. Provider settings
   are `GEO_REVERSE_URL` and `GEO_USER_AGENT` in `.env.example`.

## Pages
- `/` public landing page; logged-in users land on Home (`/home/` style activities).
- `/accounts/` registration, email verification, login, password reset.
- `/account/` profile, settings, notifications (logged in).
- `/` (activities) Home discovery, My Activities, Create/Edit/Cancel, Details,
  Participants, Invitations, Calendar (logged in).
- `/geo/cities/` logged-in JSON endpoint for opt-in nearby-city suggestions.
- `/manage/` Super Administrator home and user management.
- `/django-admin/` built-in Django admin (URL from `DJANGO_ADMIN_URL` in `.env`).

## Brand colors (tokens live in static/css/base.css)
primary #FF5A43, primary-tint #FFF3F1, primary-soft #FFDAD4, danger #E53935,
danger-bg #FCE4E5, success #059669, success-bg #ECFDF5, pending #FF7A00,
info-bg #EBF0FF, text #0F172A, text-secondary #5B6071, text-muted #8C8B8F,
background #F6F7FA, card #FFFFFF, border #E9EEF5.
Use `var(--name)` in CSS; never hard-code colors there. Emails and SVGs use the
literal brand values because CSS variables do not apply in those contexts.

## Skills (in .agents/skills/)
event-invite-app, admin-panel, web-privacy-auth, web-ui-from-design
