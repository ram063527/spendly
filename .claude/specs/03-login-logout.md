# Spec: Login and Logout

## Overview

Implement session-based authentication so registered users can sign in and out of Spendly. This step upgrades the existing `GET /login` stub to accept a `POST` that verifies credentials against the `users` table, and replaces the `GET /logout` placeholder with a route that clears the session. It also makes the navbar in `base.html` session-aware so signed-in users see "Profile" / "Logout" instead of "Sign in" / "Get started". This is the gate that all future logged-in-only features (profile, expenses) will depend on.

## Depends on

- Step 01 — Database setup (`users` table, `get_db()`)
- Step 02 — Registration (`create_user()`, existing accounts to sign in with)

## Routes

- `GET /login` — render login form; if already signed in, redirect to `/` — public
- `POST /login` — verify credentials, set session, redirect to `/` — public
- `GET /logout` — clear session, flash confirmation, redirect to `/` — logged-in
- `GET /register`, `POST /register` — if already signed in, redirect to `/` instead of rendering/processing the form — public (modifies existing Step 02 route to add this guard)

## Database changes

No new tables or columns. The existing `users` table (id, name, email, password_hash, created_at) covers all requirements.

A new DB helper must be added to `database/db.py`:

- `get_user_by_email(email)` — returns the matching row from `users` (including `password_hash`) or `None` if no match. Parameterised query only.

## Templates

- **Modify:** `templates/login.html`
  - Change the form `action` to `url_for('login')` with `method="post"`
  - Remove the local `{% if error %}` block — errors are already rendered globally by `base.html` via `get_flashed_messages`, and duplicating that mechanism is redundant
  - Keep all existing visual design
- **Modify:** `templates/base.html`
  - Wrap the two nav links in a check on `session`: when a `user_id` is present in `session`, show a circular avatar link to `{{ url_for('profile') }}` displaying `session['user_initials']` and a `{{ url_for('logout') }}` ("Logout") link, instead of "Sign in" / "Get started"

## Files to change

- `app.py` — upgrade `login()` to handle `GET` and `POST`; implement `logout()`
- `database/db.py` — add `get_user_by_email()` helper
- `templates/login.html` — wire up form action/method, drop the local error block
- `templates/base.html` — make the navbar session-aware

## Files to create

None.

## New dependencies

No new dependencies. Uses `werkzeug.security.check_password_hash` (already installed) and Flask's built-in `session` / `flash` / `redirect` / `url_for`.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only — never use f-strings in SQL
- Passwords hashed with `werkzeug` — verify with `check_password_hash`, never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Store only non-sensitive data in the session (`user_id`, `user_initials` for the navbar avatar) — never store the password or password_hash
- On invalid email or wrong password, flash one generic message ("Invalid email or password.") — do not reveal whether the email exists
- On any validation failure, re-render the login form — do not redirect
- On success, `flash` a welcome message and `redirect` to `url_for('landing')`
- `GET /login` must redirect already-authenticated users to `url_for('landing')` instead of re-rendering the form
- `GET /logout` must clear the entire session (`session.clear()`), flash a confirmation message, and `redirect` to `url_for('landing')`
- Use `abort(405)` if an unsupported HTTP method reaches `/login`
- Use `url_for()` for every internal link — never hardcode URLs
- Do not implement or modify the `/profile`, `/expenses/add`, `/expenses/<id>/edit`, or `/expenses/<id>/delete` stub routes beyond what is described above — they stay out of scope for this step

## Definition of done

- [ ] `GET /login` renders the login form without errors when signed out
- [ ] `GET /login` redirects to `/` when already signed in
- [ ] `POST /login` with the seeded demo account (`demo@spendly.com` / `demo123`) signs in and redirects to `/`
- [ ] `POST /login` with a wrong password re-renders the form with a generic "Invalid email or password." error, no session set
- [ ] `POST /login` with an unregistered email shows the same generic error, no session set
- [ ] `GET /logout` clears the session and redirects to `/` with a confirmation flash message
- [ ] Navbar shows "Sign in" / "Get started" when signed out, and "Profile" / "Logout" when signed in
- [ ] Visiting `/logout` while already signed out does not error
- [ ] No plaintext password or password hash is ever stored in the session cookie
