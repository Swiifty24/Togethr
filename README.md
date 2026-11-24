# Togethr

A responsive, role-based Django website: landing page, registration with **Gmail email-code verification**, login with rate limiting, password recovery, a social **Home** page for discovering and joining group activities, activity planning with invitations and responses, a calendar, notifications, profiles, and a Super Administrator **Admin Home** with full user management. Data lives in a **MySQL/MariaDB database named `togethr`**.

## Requirements
- Python 3.10+
- MySQL 8+ or **MariaDB 10.5+** (Django 5.2 rejects older MariaDB; if you see a version error, upgrade XAMPP's MariaDB)
- A Gmail account with 2-Step Verification (for an App Password)

## Setup (Windows/macOS/Linux)
```bash
# 1. Start MySQL (e.g. XAMPP control panel -> MySQL "Start")

# 2. Virtual environment + dependencies
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt

# 3. Configuration
copy .env.example .env           # macOS/Linux: cp .env.example .env
#    then edit .env (see "Environment" below)

# 4. Create the database, tables, and your Super Administrator
python manage.py create_database # creates `togethr` if missing (or create it in phpMyAdmin)
python manage.py migrate
python manage.py createsuperuser # asks for username, email, full name, password

# 5. Run
python manage.py runserver
```
Open http://127.0.0.1:8000/.

## Environment (`.env`)
| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Required. Generate: `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"` |
| `DJANGO_DEBUG` | `True` for local development, `False` in production |
| `DB_NAME/USER/PASSWORD/HOST/PORT` | MySQL connection (XAMPP default: user `root`, empty password) |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | Gmail address and a **16-character App Password** (https://myaccount.google.com/apppasswords) — never your normal password |
| `DEFAULT_FROM_EMAIL` | Sender shown on emails |
| `DJANGO_ADMIN_URL` | Path of the built-in Django admin (default `django-admin/`) |
| `VERIFICATION_*`, `LOGIN_*` | Code lifetime (10 min), max wrong codes (5), resend cooldown (60 s), login lockout (5 tries / 15 min) |

To try the site **without** Gmail, set `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`; emails are then printed in the terminal. This is for testing only.

## Where things are
| Path | Contents |
|---|---|
| `togethr/` | Settings, root URLs |
| `accounts/` | User model (unique email, roles), Profile, EmailVerification, ActivityLog, Notification; registration, verification, login, password reset; services & validators |
| `activities/` | Activities, categories, participation/invitations; Home discovery, My Activities, Create/Edit/Cancel, Details, Participants, Invited Activities, Calendar |
| `members/` | Profile (with picture), Settings (change password), Notifications |
| `adminpanel/` | Admin Home + user management (search, filter, create, edit, role, activate/deactivate, delete) |
| `core/` | Landing page, error-page previews (DEBUG), `create_database` command |
| `templates/`, `static/` | Template inheritance + reusable includes; CSS (`base`, `components`, `public`, `app`) and JS (`ui`, `password`, `verify`) |

## Activities: how it works
- **Create** an activity (title, description, cover image, category, date, start/end time, location, **minimum** and optional **maximum** participants, public or invite-only).
- **Join** from Home (public activities), or **reply to an invitation** with Join / Not Sure / Can't Join. Responses can be changed any time before the activity.
- **Status** is automatic: *Pending* until the number of people who joined reaches the minimum, then *Confirmed*; it drops back to *Pending* (and the organizer is notified) if people leave. Finished activities become *Completed*, or *Canceled* if the minimum was never reached. Organizers can also cancel.
- Everyone involved is notified of invitations, responses, confirmation, cancellation, and date/time/location changes (Notifications page).
- Invite people by searching registered, verified members (there is no separate friend list yet).
- Ten default categories are created by the migration; manage them in the Django admin.
- Uploaded images are stored in `media/` (served automatically while `DJANGO_DEBUG=True`; in production serve `/media/` from your web server).

## Roles & access
- **Super Administrator** = Django `is_superuser`. Sees `/manage/` and the Django admin (`/django-admin/` by default) for fine-grained permissions.
- **Regular user** = everyone else; gets 403 on administrator URLs. Every admin view is guarded server-side by `superuser_required`.
- Admins cannot delete/deactivate themselves or remove the last Super Administrator.
- Accounts created by an admin, `createsuperuser`, or the Django admin "Add user" form are treated as email-verified; self-registered accounts stay inactive until the email code is confirmed.

## Security notes
PBKDF2 password hashing, Django password validators + custom complexity rule (client checklist mirrors server), CSRF on every form, POST-only logout, hashed one-time codes (bound to the user, expiring, attempt-limited, resend cooldown + hourly cap), DB-backed login/reset throttling, generic messages that don't reveal which accounts exist, safe `next` redirects, `never_cache` on private pages, secure cookies/HSTS/SSL redirect when `DJANGO_DEBUG=False`.

Housekeeping: `python manage.py purge_unverified --days 7` deletes abandoned registrations (frees their username/email).

## Tests
```bash
python manage.py test accounts      # needs MySQL running; creates/destroys test_togethr
```

## Production
Set `DJANGO_DEBUG=False`, a real `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`; run `python manage.py collectstatic`; serve with gunicorn/uWSGI behind HTTPS and serve `/static/` from your web server (or add WhiteNoise). Set `TRUST_PROXY_HEADERS=True` only behind a trusted proxy.

## Troubleshooting
- *Access denied / can't connect*: MySQL not running, or `DB_USER`/`DB_PASSWORD` wrong.
- *MariaDB/MySQL version error*: need MariaDB 10.5+ / MySQL 8+.
- *Gmail "Username and Password not accepted"*: use an App Password; confirm 2-Step Verification is on.
- *Can't log in right after registering*: verify your email first (log in again to get a fresh code).
