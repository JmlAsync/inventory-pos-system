# AGENTS.md: rules for anyone changing this repository

This file is for **AI coding assistants** (Claude, Copilot, Cursor, Codex and others) and for
**people**. It lists the rules this project follows. A rule here is a decision that has already
been made. Follow it; do not re-decide it. When a rule says MUST, there is no exception unless
the project owner changes this file.

Rules marked **[checked]** are verified by `tests/check_contract.py` on every pull request.
The others are checked by review.

**Overridden rules.** When the project owner replaces a rule, the new wording takes its place and the
old wording stays right below it in a note marked *Overridden*, with the date and the reason. Follow
the new wording; the note is there so nobody re-decides the old question. Where a new rule names a
version ("from v0.25.0"), the old rule still applies to the code until that version is merged.

Last reviewed for v0.21.2 (2026-10-24, rules for the client upgrade, see `docs/upgrade_plan.md`).

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
| Pages | Jinja2 templates + Bootstrap 5.3.3 + Bootstrap Icons 1.11.3 + Inter font, all stored in `static/vendor/` |
| Tests | Python standard library only (`tests/`) |

The project's audience is a **beginner**. Code comments and messages are written so a beginner
can follow them.

**Next stage (decided 2026-10-24):** after the course submission (v0.21.2), the system becomes a
product sold to café owners by **subscription**. The email used to buy the subscription becomes the
shop's **owner** account; everyone else joins by invitation. A client chooses a **local** package
(SQLite) or a **cloud** package (managed PostgreSQL); a **Firebase** package (Firestore) is built only
for clients who already use Firebase, never first (DEC-014). The full plan and its order of work are in
`docs/upgrade_plan.md`.

## 2. Where things are

| Path | What it holds | Notes |
|---|---|---|
| `app.py` | Every page (route), the checks on every form, start-up and database upgrade | One file until v0.25.0; then split into blueprints, with all database access in `store/` (see the note below this table) |
| `models.py` | The database tables (Product, User, LoginSession, Sale, SaleItem, MenuOption, Ingredient, RecipeItem, IngredientMovement) | |
| `templates/` | The HTML pages; `base.html` is the shared layout; files starting with `_` are pieces | |
| `static/css/theme.css` | All custom styling, light and dark theme | |
| `static/vendor/` | Bootstrap, Bootstrap Icons and the Inter font, stored locally | Rule D2: nothing loads from the internet |
| `seed_demo_data.py` | Fills the database with demo data; `--fresh` backs up first | |
| `add_users.py`, `add_test_product.py` | Small helper scripts from the first versions | |
| `tests/` | Automated tests and the contract check | See section 9 |
| `migrations/` | Numbered database changes (`versions/0001_…`), run by Alembic at start-up after a backup (v0.23.0) | Rule I5; how to add one: `migrations/README.md` |
| `project_documentation_draft.md` | The living project report (versions, tests, defects, UML) | MUST be updated with every change (W4) |
| `diagrams/` | UML diagrams: `.puml` source + `.png` | |
| `docs/` | Other reports and guides: security audit, running on another computer | |
| `docs/decisions.md` | Every decision with how it works, why it was chosen and the alternatives checked (`DEC-NNN`) | MUST get an entry for every decision (C9, C10) |
| `docs/upgrade_plan.md` | The plan for the client version (sign-in, two database packages, missing features) | |
| `screenshots/` | Screenshots used in the report | |

> *Overridden 2026-10-24.* Old wording: "`app.py` … One file on purpose (course scope)."
> Why: one file was right for a beginner's course project, but the client upgrade needs two databases
> (SQLite and Firestore). The routes can only work with both if they stop calling the database
> directly, so the code is split into blueprints and a `store/` data layer (audit risk R7). Until
> v0.25.0 is merged, keep adding to `app.py` as before. Full reasoning: DEC-008.

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
  `db.text()` with `:named` parameters. Migrations in `migrations/versions/` use Alembic's operations
  (`op.create_table`, `op.add_column`) and fixed SQL only.

  > *Overridden 2026-10-24 (v0.23.0).* Old wording: "The only exception is `upgrade_database()`, whose
  > table and column names come from the fixed `NEW_COLUMNS` list." Why: the column list moved into
  > migration 0001, which adds columns with Alembic's operations instead of joined SQL text, so no
  > exception is needed any more (DEC-023).
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
- **S12** Nobody can give themselves an account or a role. There is no open sign-up page. The
  **owner** account is created only from the subscription purchase, with the email used to buy it,
  confirmed by an emailed code; it cannot be deleted or demoted, and its email changes only through
  the subscription. Every other account starts from an **invitation** sent by the owner (or an admin
  the owner allowed to invite) to that person's own email, with the role chosen by the inviter.
  Accepting an invitation never changes its role. *(From v0.27.0; until then accounts are made only
  by `seed_demo_data.py` and `add_users.py`.)* Why: DEC-002 (owner) and DEC-003 (invitations).
- **S13** Every login needs the password (or Google sign-in) **and** a 6-digit code, unless that browser is a **trusted device** for that user. Trust skips only the code,
  never the password. The code comes by email (the default) or, if the user chose it on their
  Profile, from an authenticator app; turning the app on or off needs the password and a current
  code, and emails the user. Trust ends on log-out-everywhere, a password change, deactivation, removal on
  the Profile page, or after 30 days (7 for admins and the owner). *(From v0.28.0.)* Why: DEC-004,
  DEC-005, DEC-017.
- **S14** Codes, invitation tokens, trusted-device tokens and backup codes MUST be stored only as
  hashes and compared with `hmac.compare_digest`. A code is valid for 10 minutes, one use and one
  purpose, with at most 5 wrong tries. An authenticator key can't be hashed (the server needs it to
  work out the code), so it MUST be stored encrypted, and a code's 30-second step MUST NOT be
  accepted twice. Why: DEC-006, DEC-017.
- **S15** Voids, refunds, role changes and deactivations need an admin; the cashier only requests a
  void. A cashier gets 403 on every approval page. Why: DEC-007.

## 4. Data integrity

- **I1** Every stock or ingredient change (sale, void, refund, restock, count) MUST check and
  change the amount in **one atomic step** inside one transaction, and roll back the whole
  operation if any step finds too little. Never "read, check in Python, then write" outside that
  transaction. On SQL this is a conditional update (`... SET quantity = quantity - n WHERE
  quantity >= n`; 0 rows changed = roll back); on Firestore it is a transaction that reads and writes
  the same documents. From v0.25.0, routes change stock only through a `store/` operation.

  > *Overridden 2026-10-24.* Old wording: "Selling MUST subtract stock and ingredients with a
  > conditional update (`... SET quantity = quantity - n WHERE quantity >= n`) inside one
  > transaction. If any update changes 0 rows, roll back the whole sale. Never 'read, check in
  > Python, then write'." Why: Firestore has no SQL, so the rule now states the goal (no
  > overselling, all or nothing) instead of the SQL that achieves it; it also now covers voids,
  > refunds and counts, which change stock too. Full reasoning: DEC-009.
- **I2** A sale is all or nothing: the Sale, its SaleItems, the stock changes and the ingredient
  history are committed together or not at all.
- **I3** Receipts MUST NOT change after the sale: SaleItem keeps its own copy of the product name,
  unit price and options text.
- **I4** A product with sales history MUST NOT be deleted (its id could be reused).
- **I5** Every database change MUST upgrade an existing database without losing data. Never ask
  the user to delete their database. Until v0.23.0, new columns go in `NEW_COLUMNS` in `app.py`.
  From v0.23.0, every change is an Alembic migration (Flask-Migrate) in `migrations/`, tested on a
  copy of an old database, and a backup is taken automatically before it runs.

  > *Overridden 2026-10-24.* Old wording: "New database columns MUST be added to `NEW_COLUMNS` in
  > `app.py`, so an existing database on the owner's computer is upgraded at start-up without losing
  > data. Never ask the user to delete their database." Why: `NEW_COLUMNS` can only add columns. The
  > upgrade must change column types (money to whole centavos, times to UTC) and add tables, which
  > needs real migrations (audit risk R6). The promise to the user is unchanged. Full reasoning: DEC-010.
- **I6** Money and amounts are shown with the template filters: `peso` (₱1,234.50), `amount`
  (1,234) and `plain_amount` (1234, for `<input type="number">` boxes, which cannot show commas).
- **I7** Every ingredient change (sale, restock, stock count) MUST write an IngredientMovement line.
- **I8** A receipt is never edited or deleted after the sale. A void or refund is a new record that
  points to the original sale, keeps who requested and who approved it, and writes its own stock
  and ingredient history lines (reason `void`, `refund` or `waste`). Why: DEC-007.

## 5. Dependencies

- **D1 [checked]** `requirements.txt` may only contain these packages, each with an exact version
  (`name==1.2.3`): blinker, click, colorama, Flask, Flask-Login, Flask-SQLAlchemy, greenlet,
  itsdangerous, Jinja2, MarkupSafe, SQLAlchemy, typing_extensions, Werkzeug.
  Adding a package needs the project owner's approval and a change to this list (and to the
  allowlist in `tests/check_contract.py`).
  **Approved on 2026-10-24 for the upgrade**, each added to this list, the allowlist and the
  requirements file only in the version that first uses it, pinned to an exact version, together
  with the packages it brings with it: `Flask-Migrate` and `alembic` (v0.23.0), `waitress` (v0.24.0),
  `cryptography` and `segno` (v0.28.0; segno draws the authenticator QR code), `Authlib` and
  `requests` (v0.29.0), `psycopg` (v0.37.0, cloud package), `google-cloud-firestore` (v0.39.0,
  Firebase package only, built only when a client already on Firebase asks).
  From v0.24.0 the packages are split into `requirements/local.txt`, `requirements/cloud.txt`,
  `requirements/firebase.txt` and `requirements/dev.txt` (test-only tools such as Playwright), and the allowlist is checked per file.
  Email is sent with Python's own `smtplib`; no mail package is needed.

  > *Overridden 2026-10-24* (extended, not replaced). Old wording: the list above, with no approved
  > additions. Why: Google sign-in, real migrations, a production web server and Firestore cannot be
  > built from the standard library. Approving them now, with the version each belongs to, stops
  > anyone adding other packages "while they are at it". Full reasoning: DEC-011.
- **D2 [checked]** Pages load **nothing from the internet** (changed in v0.19.4, so the system works
  offline). Bootstrap 5.3.3, Bootstrap Icons 1.11.3 and the Inter font (@fontsource/inter 5.2.8) are
  stored in `static/vendor/` with their licences; `static/vendor/README.md` lists the exact files.
  No CDN, outside script, tracker or analytics. Updating one of them means replacing its files and
  changing the versions here, in that README and in `tests/check_contract.py`.
  **Still true for every page.** What changed (2026-10-24) is the promise about the system as a
  whole: the **local package MUST keep selling with no internet** on trusted devices (password only,
  no code) and with printed backup codes. Features that need the internet (Google sign-in, emailed
  codes, the cloud package) MUST say so on screen when it is down instead of failing silently. The
  cloud package needs internet to sell, and the client is told so before choosing it.

  > *Overridden 2026-10-24* (narrowed). Old meaning: the whole system works offline (NFR-12).
  > Why: sign-in with Google, codes by email and Firestore cannot work offline. The page-files rule
  > stays exactly as it was; the offline promise now applies to the local package's selling, which
  > is what the café actually needs when the Wi-Fi drops. Full reasoning: DEC-012.
- **D3** Tests use only the Python standard library plus the packages above.

## 6. Private files

- **P1 [checked]** These MUST NEVER be committed: `instance/` (database and secret key), any `.db`
  file, `static/avatars/` and `static/products/` (uploaded pictures), `local_demo/` (a real shop's
  menu and photos), `.env`, `venv/`, and (added 2026-10-24) Google sign-in secrets
  (`client_secret*.json`) and cloud keys (`*service-account*.json`, `*serviceAccount*.json`). The
  shop's settings, mail password and keys live in `instance/` (`instance/config.toml`). They are in
  `.gitignore`; do not remove those lines. (Key files: DEC-016.)
- **P2** Do not put a real shop's name, prices, recipes or photos in the repository. Real data
  stays in `local_demo/` on the owner's computer. Tests and examples use generic names.
- **P3** Do not commit passwords other than the documented demo accounts (`admin` / `admin123`,
  `cashier` / `cashier123`), which exist for the demo only. From v0.28.0 the demo accounts work
  only with `DEMO_MODE=1`, which shows codes in the console instead of emailing them and is refused
  when a real mail server is configured. Never commit a client's email address, licence key,
  subscription details or customer data (senior / PWD ID numbers).

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
- **C9** Every change and every decision MUST come with a **Why** section that explains **how it
  works** and **why this method was chosen**, in plain words. Its length follows its weight: one or
  two sentences for a small fix, a full entry for anything that decides how the system behaves.
  - A change: the **Why** heading in its pull request (W2).
  - A decision (a new or changed rule; a design, data or security choice; a new package; anything a
    user or client will notice): an entry in `docs/decisions.md` (`DEC-NNN`), and the rule, plan or
    code comment it produced names that entry.
- **C10** Before a change or decision is applied, it MUST be **checked against the alternatives**:
  list the realistic other ways to do it, compare them on safety, reliability, cost, effort and what
  the user experiences, and record the verdict (*Best choice*, *Acceptable* or *Better option
  found*) in the same `DEC` entry or **Why** section. If the check finds a better option, say so
  plainly and let the project owner decide (C8); do not quietly build the weaker one.

## 8. Workflow

- **W1** Branch names: `feature/<short-name>`, `fix/<short-name>`, `docs/<short-name>`.
- **W2** Pull request title: `vX.Y.Z: <what changed>` for a version, `Docs: <what changed>` for
  documentation. The description has four headings: **Problem**, **Change**, **Why** (C9, C10:
  how it works, why this way, the alternatives checked), **Testing**.

  > *Overridden 2026-10-24.* Old wording: "The description has three headings: **Problem**,
  > **Change**, **Testing**." Why: see DEC-001. A reviewer could see *what* changed and *that* it
  > was tested, but not *why this way*, so weak choices could pass review unnoticed.
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
  particular computer. Picture fixtures are in `tests/fixtures/`. Google sign-in is tested with a
  fake token checker, email with a fake mailbox, and Firestore only with the local Firestore
  emulator, never a real Google, mail or cloud account. From v0.25.0 the same tests run against
  every database store.
- **T4** Browser tests (clicking in a real browser) are run by hand or by an assistant before a
  release and recorded in section 6 of the documentation. From v1.0.0 they are automated with
  Playwright in `tests/browser/`, installed from `requirements/dev.txt` (never from the shop's
  requirements), and run in GitHub Actions; `python tests/run_tests.py` keeps working without them.

  > *Overridden 2026-10-24.* Old wording: "…; they are not in `tests/` because they need extra
  > software." Why: a client release on two packages is too much to click through by hand every
  > time. Keeping the browser tools in a separate dev file keeps them off the shop's computer.
  > Full reasoning: DEC-013.

## 10. Keeping this file up to date

- This file changes **only when a rule changes**: a new rule, a removed rule or a different rule.
  Features and fixes that follow the existing rules do not edit it.
- At every release, read it once against the code and update the **"Last reviewed for"** line at
  the top, even if nothing else changed.
- Keep it under 500 lines [checked]. If a rule can be checked by a program, add the check to
  `tests/check_contract.py` and mark the rule **[checked]**.
- `CLAUDE.md` only points to this file. Do not copy rules into it.
