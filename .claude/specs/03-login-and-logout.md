# Spec: Login and Logout

## Overview
Implement credential-based login and session-clearing logout for Spendly. The login route
accepts a POST form submission, looks up the user by email, verifies the password hash, and
starts a Flask session on success. The logout route clears that session and redirects to the
landing page. This step also updates the shared nav in `base.html` so logged-in users see a
"Sign out" link instead of "Sign in / Get started", laying the groundwork for the
authenticated dashboard in Step 4.

## Depends on
- Step 1 — Database setup (`get_db`, `init_db`, `users` table must exist)
- Step 2 — Registration (`create_user`, `get_user_by_email`, `app.secret_key`, session infrastructure)

## Routes
- `POST /login` — verify email + password, set `session["user_id"]`, redirect to landing — public
- `GET /logout` — clear session, redirect to landing — public (effective only when logged in)

The existing `GET /login` route is unchanged; it continues to render `login.html`.

## Database changes
No database changes. `get_user_by_email(email)` already exists in `database/db.py`.

## Templates
- **Modify:** `templates/login.html`
  - Fix hardcoded `action="/login"` → `action="{{ url_for('login') }}"`
  - Re-populate `value="{{ request.form.email }}"` on the email field so the value survives a
    failed submission
- **Modify:** `templates/base.html`
  - In the nav, conditionally render links based on `session.get("user_id")`:
    - Logged-out: show "Sign in" and "Get started" (current behaviour)
    - Logged-in: show only a "Sign out" link pointing to `url_for('logout')`

## Files to change
- `app.py` — add `check_password_hash` import, convert `GET /login` to `GET|POST`, implement
  `GET /logout` to clear session and redirect
- `templates/login.html` — fix hardcoded action URL, add email value re-population
- `templates/base.html` — conditional nav links based on session state

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security.check_password_hash` is part of Werkzeug, which is
already installed as a Flask dependency.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — never f-strings or `%` formatting in SQL
- Passwords verified with `werkzeug.security.check_password_hash` — never compare plain text
- Use CSS variables — never hardcode hex values in templates or stylesheets
- All templates extend `base.html`
- On successful login: set `session["user_id"] = user["id"]`, then `redirect(url_for("landing"))`
- On failed login (unknown email or wrong password): re-render `login.html` with a generic
  `error="Invalid email or password."` — never reveal which field was wrong
- `GET /logout` must call `session.clear()` before redirecting — not just `session.pop()`
- The nav conditional in `base.html` must use `session.get("user_id")` (not `session["user_id"]`)
  to avoid a `KeyError` for anonymous visitors

## Definition of done
- [ ] Submitting valid credentials sets `session["user_id"]` and redirects to `/`
- [ ] Submitting an unknown email re-renders the login form with an inline error, no session set
- [ ] Submitting a correct email but wrong password re-renders the login form with an inline error
- [ ] The email field is pre-populated after a failed login attempt
- [ ] `GET /logout` clears the session and redirects to `/`
- [ ] After logout, `session["user_id"]` is no longer set
- [ ] Logged-out users see "Sign in" and "Get started" in the nav
- [ ] Logged-in users see "Sign out" (linking to `/logout`) in the nav instead
- [ ] `GET /login` still renders the empty form with no regressions
