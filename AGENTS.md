# TOGETHR: guide for AI coding assistants

TOGETHR is a Django web app where friends plan activities and invite each other.
Team project: one teammate builds the backend logic, and PJ handles the visual design.
Keep code simple, readable, and commented.

## Layout
This folder (with manage.py) is the project root. Run all commands here.
- togethr\ : project settings and urls
- accounts\, activities\, adminpanel\, core\, members\ : Django apps (models, views, forms)
- templates\ : HTML templates (includes\ holds shared pieces)
- static\ : CSS, JavaScript, images
- venv\ : local virtual environment (not in Git), do not edit
- .env : private settings (not in Git). Never read, print, or commit it.
  .env.example is the safe template.

## Commands
    venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    python manage.py runserver
    python manage.py makemigrations
    python manage.py migrate

## Rules
1. Explain your plan before editing. Ask before migrations, deletions, or installs.
2. Work on a branch, never directly on main.
3. Design tasks: change only templates\ and static\. Do not edit any .py file, URLs,
   template logic ({% %} tags), form field names, or context variable names.
4. Backend tasks: change only the app folders the task names.
5. Never commit secrets, .env, db.sqlite3, or venv. Do not weaken existing login checks.
6. Plain Django only. No extra packages unless asked.
7. After model changes, tell me to run makemigrations and migrate.

## Brand colors (warm red-orange with pastels)
primary #FF5A43, primary-tint #FFF3F1, primary-soft #FFDAD4, danger #E53935,
danger-bg #FCE4E5, success #059669, success-bg #ECFDF5, pending #FF7A00,
info-bg #EBF0FF, text #0F172A, text-secondary #5B6071, text-muted #8C8B8F,
background #F6F7FA, card #FFFFFF, border #E9EEF5.

## Skills (in .agents/skills/)
event-invite-app, admin-panel, web-privacy-auth, web-ui-from-design