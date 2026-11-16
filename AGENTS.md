# TOGETHR: guide for AI coding assistants

TOGETHR is a Django web app where friends plan activities and invite each other.
Student project: keep code simple, readable, and commented.

## Layout
This folder (with manage.py) is the project root. Run all commands here.
- Javier_Flores_WebApp\Javier_Flores_WebApp\ : settings.py and urls.py
- WebApp_Project\ : the app (models, views, urls, forms, templates, static)
- demo\ : unrelated app, do not touch
- ..\venv : shared virtual environment, do not edit
- db.sqlite3 : do not edit directly

## Commands
    ..\venv\Scripts\activate
    python manage.py runserver
    python manage.py makemigrations
    python manage.py migrate

## Rules
1. Only change files in WebApp_Project\ and the settings and urls files.
2. Explain your plan before editing. Ask before migrations, deletions, or installs.
3. Plain Django only: function-based views, ModelForms, built-in auth.
4. After model changes, tell me to run makemigrations and migrate.

## Pages
- "/" public welcome page; logged-in users go to Home
- login and sign up are public; everything else requires login
- /admin/ for staff only
- Events are private to the creator and invited people.

## Brand colors (warm red-orange with pastels)
primary #FF5A43, primary-tint #FFF3F1, primary-soft #FFDAD4, danger #E53935,
danger-bg #FCE4E5, success #059669, success-bg #ECFDF5, pending #FF7A00,
info-bg #EBF0FF, text #0F172A, text-secondary #5B6071, text-muted #8C8B8F,
background #F6F7FA, card #FFFFFF, border #E9EEF5.

## Skills (in .agents/skills/)
event-invite-app, admin-panel, web-privacy-auth, web-ui-from-design