# Spec: Date Filter for Profile Page

## Overview
Step 6 adds a date-range filter to the profile page so users can narrow all
four data sections — summary stats, transaction list, and category breakdown —
to a specific period. The filter is submitted as a GET form, keeping all state
in the URL query string (`?from=YYYY-MM-DD&to=YYYY-MM-DD`). When no filter is
active, the page behaves exactly as it did after Step 5 (all-time data). The
profile route reads the two optional query params, passes them to every query
helper, and re-renders the template with a pre-filled form so the user can see
which range is active.

## Depends on
- Step 1: Database setup (`expenses` table with `date` column exists)
- Step 2: Registration (users stored in the database)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 4: Profile page static UI (template already renders all four sections)
- Step 5: Backend connection (live queries powering the profile page)

## Routes
No new routes. The existing `GET /profile` route is modified to read optional
`from` and `to` query parameters.

## Database changes
No database changes. The `expenses.date` column (TEXT, format `YYYY-MM-DD`)
already supports range comparisons with SQLite's `BETWEEN` or `>=`/`<=`
operators.

## Templates
- **Modify**: `templates/profile.html`
  - Add a date-filter form above the stats section with two `<input type="date">` fields (`from` and `to`) and a submit button.
  - Add a "Clear" link that navigates to `/profile` with no query params.
  - Pre-fill the form inputs with the current active filter values (passed from the route as `date_from` and `date_to`).
  - Show an "Filtered: DD Mon YYYY – DD Mon YYYY" label when a filter is active, hidden otherwise.
  - All existing sections (stats, transactions, category breakdown) continue to render using the same Jinja variables — no structural changes needed beyond the new form.

## Files to change
- `app.py` — update `profile()` to read `request.args.get("from")` and
  `request.args.get("to")`, validate them, and forward to every query helper.
- `database/queries.py` — add optional `date_from` / `date_to` keyword
  arguments to `get_summary_stats`, `get_recent_transactions`, and
  `get_category_breakdown`. When provided, add a `WHERE date BETWEEN ? AND ?`
  clause; when absent, queries behave exactly as before.
- `templates/profile.html` — add the filter form as described above.
- `static/css/style.css` — add styles for the filter form and active-filter label.

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline `<style>` tags
- Currency must always display as ₹ — never £ or $
- Date inputs must use `type="date"` (ISO format `YYYY-MM-DD`) — no custom pickers or JS date libraries
- Filter is GET-only — no POST, no session storage, no cookies
- If `from` is after `to`, treat it as no filter (return all-time data) and do not raise an exception
- If only one of the two params is provided, treat it as no filter
- `get_user_by_id` does **not** need a date filter — it fetches user metadata only
- The "Clear" link must use `url_for("profile")` — never a hardcoded path

## Definition of done
- [ ] Visiting `/profile` with no query params shows all-time data (same as Step 5)
- [ ] Submitting the date filter form with a valid range updates the URL to `/profile?from=YYYY-MM-DD&to=YYYY-MM-DD`
- [ ] After filtering, all three data sections (stats, transactions, category breakdown) reflect only expenses within the selected date range
- [ ] The form inputs are pre-filled with the active `from` and `to` dates after filtering
- [ ] The active-filter label is visible when a range is applied and hidden on the all-time view
- [ ] Clicking "Clear" returns to `/profile` with no query params and shows all-time data
- [ ] Filtering with `from` after `to` falls back to all-time data without an error
- [ ] Filtering to a range with no expenses shows ₹0.00 total, 0 transactions, "—" top category, empty transaction list, and empty category breakdown — no exceptions
