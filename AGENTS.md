# AGENTS.md: rules for anyone changing this repository

This file is for **AI coding assistants** (Claude, Copilot, Cursor, Codex and others) and for
**people**. It lists the rules this project follows. A rule here is a decision that has already
been made. Follow it; do not re-decide it. When a rule says MUST, there is no exception unless
the project owner changes this file.

Rules marked **[checked]** are verified by `tests/check_contract.py` on every pull request.
The others are checked by review.

Last reviewed for v0.19.1 (2026-10-09).

---

## 1. What this project is

An **Inventory & Point-of-Sale (POS) web app for a small café**, built as a university final
project (Software Engineering 1). Admins manage products, servings (Hot / Iced), add-ons,
ingredients and recipes. Cashiers sell at the counter (cash or GCash) and print receipts.

| Part | Technology |
|---|---|
| Language | Python 3.13 |
| Web framework | Flask 3.1, Flask-Login, Flask-SQLAlchemy |
| Database | SQLite, one file: `instance/inventory.db` |
| Pages | Jinja2 templates + Bootstrap 5.3.3 + Bootstrap Icons 1.11.3 + Inter font |
| Tests | Python standard library only (`tests/`) |

The project's audience is a **beginner**. Code comments and messages are written so a beginner
can follow them.

## 2. Where things are

| Path | What it holds | Notes |
|---|---|---|
| `app.py` | Every page (route), the checks on every form, start-up and database upgrade | One file on purpose (course scope) |
| `models.py` | The database tables (Product, User, Sale, SaleItem, MenuOption, Ingredient, RecipeItem, IngredientMovement) | |
| `templates/` | The HTML pages; `base.html` is the shared layout; files starting with `_` are pieces | |
| `static/css/theme.css` | All custom styling, light and dark theme | |
| `seed_demo_data.py` | Fills the database with demo data; `--fresh` backs up first | |
| `add_users.py`, `add_test_product.py` | Small helper scripts from the first versions | |
| `tests/` | Automated tests and the contract check | See section 9 |
| `project_documentation_draft.md` | The living project report (versions, tests, defects, UML) | MUST be updated with every change (W4) |
| `diagrams/` | UML diagrams: `.puml` source + `.png` | |
| `screenshots/` | Screenshots used in the report | |

## 3. Security boundaries

- **S1 [checked]** Every page (`@app.route`) MUST be listed in `tests/check_contract.py` as
  public, user (logged in) or admin. Adding a page means deciding which list it belongs to.
  Only `/` and `/login` are public.
- **S2 [checked]** A user page MUST have `@login_required` directly under `@app.route`.
  An admin page MUST have `@app.route`, then `@login_required`, then `@admin_required`, in that order.
  Hiding a button is never enough: the server MUST refuse (403) a cashier who types the address.
- **S3 [checked]** Every `<form method="POST">` MUST contain the CSRF token:
  `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` (or a macro that adds it).
  The check runs in `check_csrf_token()` before every request.
- **S4 [checked]** No `debug=True` and no secret key written in any `.py` file. The secret key
  comes from the `SECRET_KEY` environment variable or `instance/secret_key.txt`. Debug mode only
  with `FLASK_DEBUG=1`.
- **S5 [checked]** SQL MUST NOT be built by joining text with user input. Use SQLAlchemy queries, or
  `db.text()` with `:named` parameters. The only exception is `upgrade_database()`, whose table and
  column names come from the fixed `NEW_COLUMNS` list.
- **S6** Anything that changes data MUST be a POST (never a GET link): delete, log out, restock.
- **S7** Every value from a form MUST be checked on the server, even if the browser already checks
  it: empty, too long, not a number, `nan`, `inf`, negative, too big. Show a friendly message;
  never a 500 error.
- **S8** Uploaded pictures MUST be checked by their first bytes (PNG, JPG or WebP only), be at most
  2 MB, and be saved under a random name. Never use the uploaded file name on disk.
- **S9** Passwords MUST be stored only as hashes (`generate_password_hash`). Never log or show them.
- **S10** Do not turn off or weaken: the login limit (5 tries per username and computer, then
  5 minutes), the security headers in `add_security_headers()`, or `SameSite=Lax` cookies.
- **S11** Never use `|safe`, `Markup()` or `render_template_string()` on anything a user typed.

## 4. Data integrity

- **I1** Selling MUST subtract stock and ingredients with a conditional update
  (`... SET quantity = quantity - n WHERE quantity >= n`) inside one transaction. If any update
  changes 0 rows, roll back the whole sale. Never "read, check in Python, then write".
- **I2** A sale is all or nothing: the Sale, its SaleItems, the stock changes and the ingredient
  history are committed together or not at all.
- **I3** Receipts MUST NOT change after the sale: SaleItem keeps its own copy of the product name,
  unit price and options text.
- **I4** A product with sales history MUST NOT be deleted (its id could be reused).
- **I5** New database columns MUST be added to `NEW_COLUMNS` in `app.py`, so an existing database
  on the owner's computer is upgraded at start-up without losing data. Never ask the user to
  delete their database.
- **I6** Money and amounts are shown with the template filters: `peso` (₱1,234.50), `amount`
  (1,234) and `plain_amount` (1234, for `<input type="number">` boxes, which cannot show commas).
- **I7** Every ingredient change (sale, restock, stock count) MUST write an IngredientMovement line.

## 5. Dependencies

- **D1 [checked]** `requirements.txt` may only contain these packages, each with an exact version
  (`name==1.2.3`): blinker, click, colorama, Flask, Flask-Login, Flask-SQLAlchemy, greenlet,
  itsdangerous, Jinja2, MarkupSafe, SQLAlchemy, typing_extensions, Werkzeug.
  Adding a package needs the project owner's approval and a change to this list (and to the
  allowlist in `tests/check_contract.py`).
- **D2 [checked]** Pages may only load these from outside: Bootstrap 5.3.3 and Bootstrap Icons
  1.11.3 from cdn.jsdelivr.net, and the Inter font from Google Fonts. No other CDN, script,
  tracker or analytics.
- **D3** Tests use only the Python standard library plus the packages above.

## 6. Private files

- **P1 [checked]** These MUST NEVER be committed: `instance/` (database and secret key), any `.db`
  file, `static/avatars/` and `static/products/` (uploaded pictures), `local_demo/` (a real shop's
  menu and photos), `.env`, `venv/`. They are in `.gitignore`; do not remove those lines.
- **P2** Do not put a real shop's name, prices, recipes or photos in the repository. Real data
  stays in `local_demo/` on the owner's computer. Tests and examples use generic names.
- **P3** Do not commit passwords other than the documented demo accounts (`admin` / `admin123`,
  `cashier` / `cashier123`), which exist for the demo only.

## 7. Contribution scope

- **C1** One change per branch and per pull request: one feature, or one fix, or one
  documentation update. Do not mix in unrelated refactoring, renaming or reformatting.
- **C2** Stabilization rule: when a version has a known defect, fix it as a patch (vX.Y.1, vX.Y.2…)
  **before** starting the next feature.
- **C3** Every fix MUST come with a test that **fails before the fix and passes after** it. Name the
  defect in the test (for example `(DEF-13)`).
- **C4** Every new feature MUST come with tests in `tests/` for its rules, its error messages and
  who may use it (cashier gets 403 on admin pages).
- **C5** Every block of code MUST have a short comment saying what it does and why, in plain
  English a beginner can follow, ending with the version that added it, for example `(v0.17.0)`.
- **C6** Messages shown to users say what went wrong and what to do, in plain words
  ("Cash received must be at least ₱226.50"), never a code or a stack trace.
- **C7** Keep the existing look: Bootstrap classes plus `static/css/theme.css`. Check new pages in
  the light and dark theme and on a phone-width screen.
- **C8** Do not change these rules to make a change pass. If a rule is wrong, say so and let the
  project owner decide.

## 8. Workflow

- **W1** Branch names: `feature/<short-name>`, `fix/<short-name>`, `docs/<short-name>`.
- **W2** Pull request title: `vX.Y.Z: <what changed>` for a version, `Docs: <what changed>` for
  documentation. The description has three headings: **Problem**, **Change**, **Testing**.
- **W3** After merging: `git pull` on `main`, check the last commit is the merge, then add an
  **annotated** tag on the merge commit: `git tag -a vX.Y.Z -m "<one-line summary>"` and push it.
- **W4** Every change updates `project_documentation_draft.md`: the version history (section 3),
  the feature's user story and test cases (sections 5 and 6), and any defect found (section 7).
- **W5** Version numbers: new feature = next minor (0.18.0 → 0.19.0); fix = next patch
  (0.18.1 → 0.18.2). Documentation-only changes get no tag.
- **W6** Before asking for a merge: `python tests/run_tests.py` MUST end with
  "All N test files passed.", and GitHub's "Checks" MUST be green.

## 9. Tests

```
python tests/run_tests.py            # the contract check, then every test file
python tests/run_tests.py sales      # only test files whose name contains "sales"
python tests/run_tests.py -v         # show every PASS line too
python tests/check_contract.py       # only the rules marked [checked]
```

- **T1** Tests run in a temporary copy of the project, so they never touch `instance/` or uploads.
  Never write a test that uses the real database.
- **T2** A test file is a plain script: `from helpers import check, finish`, then
  `check('what is tested', condition)` lines, then `finish('NAME')`.
- **T3** Tests MUST NOT depend on the internet, the clock (use dates relative to today) or a
  particular computer. Picture fixtures are in `tests/fixtures/`.
- **T4** Browser tests (clicking in a real browser) are run by hand or by an assistant before a
  release and recorded in section 6 of the documentation; they are not in `tests/` because they
  need extra software.

## 10. Keeping this file up to date

- This file changes **only when a rule changes**: a new rule, a removed rule or a different rule.
  Features and fixes that follow the existing rules do not edit it.
- At every release, read it once against the code and update the **"Last reviewed for"** line at
  the top, even if nothing else changed.
- Keep it under 500 lines [checked]. If a rule can be checked by a program, add the check to
  `tests/check_contract.py` and mark the rule **[checked]**.
- `CLAUDE.md` only points to this file. Do not copy rules into it.
