# Spec: Registration

## Overview
Implement user account creation for Spendly.  Flask session, and redirects them to the
landing page. Duplicate emails and weak passwords are rejected with inline error messages.
This step also introduces `app.secret_key` — the session foundation that Steps 3–4 (logout
and profile) depend on.

## Depends on
- Step 1 — Database setup (`get_db`, `init_db`, `users` table must exist)

## Routes
- `POST /register` — process registration form, create user, start session — public

The existing `GET /register` route is unchanged; it continues to render `register.html`.

## Database changes
No new tables or columns.

Add two helpers to `database/db.py`:
- `create_user(name, email, password_hash)` — inserts a row into `users`, returns the new `id`
- `get_user_by_email(email)` — returns the matching `users` row or `None`

## Templates
- **Modify:** `templates/register.html`
  - Fix hardcoded `action="/register"` → `action="{{ url_for('register') }}"`
  - Re-populate `value="{{ request.form.name }}"` and `value="{{ request.form.email }}"` so
    values survive a failed submission
  - The `{% if error %}` block is already present — no structural change needed

## Files to change
- `app.py` — add `secret_key`, import `session` + `redirect` + `url_for` + `request`,
  add `POST /register` route, add `create_user` / `get_user_by_email` imports
- `database/db.py` — add `create_user()` and `get_user_by_email()` helpers
- `templates/register.html` — fix hardcoded action URL, add value re-population

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security.generate_password_hash` is already imported in
`database/db.py`.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — never f-strings or `%` formatting in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash` — never stored in plain text
- Use CSS variables — never hardcode hex values in templates or stylesheets
- All templates extend `base.html`
- `app.secret_key` must be set before any session usage — use a hard-coded dev string
  (e.g. `"spendly-dev-secret"`) for now; flag it as a `# TODO: load from env in production`
- Catch `sqlite3.IntegrityError` for duplicate email — render the form again with
  `error="An account with that email already exists."`
- Validate server-side before inserting:
  - All three fields (name, email, password) must be non-empty after `.strip()`
  - Password must be at least 8 characters
- On success: set `session["user_id"] = new_id`, then `redirect(url_for("landing"))`
- Use `abort(405)` for unsupported methods if needed — never a bare string return

## Definition of done
- [ ] Submitting the form with valid data creates a new row in `users` with a hashed password
- [ ] After successful registration, `session["user_id"]` is set and the browser is redirected to `/`
- [ ] Submitting with an already-registered email re-renders the form with an inline error message
- [ ] Submitting with a password shorter than 8 characters re-renders the form with an inline error message
- [ ] Submitting with any field blank re-renders the form with an inline error message
- [ ] Name and email values are preserved in the form after a failed submission
- [ ] Registering the same email twice does not create a duplicate row in the database
- [ ] `GET /register` still renders the empty form with no regressions
