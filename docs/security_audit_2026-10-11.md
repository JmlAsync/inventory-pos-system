# Security audit and debugging review: v0.19.2

**Date:** 2026-10-11 (Philippine time) · **Version checked:** v0.19.2 (`5eca0f3`, GitHub `main`) · **Done by:** Claude, at Yesha's request
**Result in one line:** no SQL injection, no script injection, no way past the login or admin checks, and no crash in
6,417 hostile requests. The deeper checks found **1 crash, 1 duplicate-sale risk, 1 outdated package and 4 other
weaknesses** worth fixing, plus 11 risks for future goals (going online, offline, Software Engineering 2).

> **Words used here.** A **vulnerability** is a weakness someone could use to cause harm. **Severity** says how bad it
> would be: *High* (serious harm, easy to do), *Medium* (real harm, needs some effort), *Low* (small harm or unlikely),
> *Info* (a decision to make, not a flaw). **DoS** (denial of service) means making the system stop working for others.

---

## 1. How it was checked

| Method | What it means | Size |
|---|---|---|
| **Dependency check** (`pip-audit`) | Compares every package version in `requirements.txt` with the public list of known vulnerabilities (CVEs) | 13 packages |
| **Code scanner** (`bandit`) | A program that reads Python code looking for dangerous patterns | 5 files, 1,700 lines |
| **Manual code review** | Reading every route in `app.py`, every template script and every place user input is used | All 21 pages (routes) |
| **Fuzzing** | Sending hostile values to every form field: empty, huge numbers, `nan`, `inf`, 10,000 letters, emoji, `<script>`, SQL commands, `../../app.py`, null bytes, Arabic digits… as admin and as cashier | 39 forms, 6,417 requests |
| **Targeted attacks** | Specific attacks for each suspicion from the review: stolen cookies, timing, memory, double-clicks, price changes | 11 scenarios |
| **Live server probing** | Path tricks on the real development server (`/static/..%2fapp.py`, `/instance/secret_key.txt`), unusual HTTP methods, very long addresses | About a dozen probes |
| **Upgrade test** | All 17 automated test files run on the newest Werkzeug (3.1.9) and SQLAlchemy (2.1.4) | All pass |

Every finding below was **reproduced** (made to happen on purpose) unless it says otherwise.

## 2. What held up (strengths)

- **SQL injection:** impossible. Every database query goes through SQLAlchemy with parameters. The one place SQL is
  built from text (`upgrade_database()`) only uses fixed names from the code.
- **Script injection (XSS):** a product named `<img src=x onerror=alert(1)>` shows as plain text everywhere. Jinja
  escapes everything, no template uses `|safe`, and the page scripts write user data only with `textContent` / `.value`.
- **Access control:** a visitor, cashier and admin each get exactly their pages. A cashier gets 403 on every admin page,
  including when sending forms by hand (also checked automatically on every pull request).
- **CSRF:** every POST form carries the token; a form without it is refused (400).
- **Files:** path tricks return 404; `instance/` (database and secret key) cannot be downloaded; pictures are checked
  by their first bytes and saved under random names.
- **Money and stock:** price changes after an item is in the basket are caught (the cashier is asked for the new total);
  stock and ingredients can't go below zero even with 20 tills at once (earlier tests, still passing).
- **Secrets:** no password, key or database in the Git history. `bandit` found **no** medium or high issue (only
  "random numbers are not for security" in the demo-data script, which is fine there).

## 3. Findings: weaknesses to fix

| # | Severity | Finding | Evidence | Fix (effort) |
|---|---|---|---|---|
| **A1** | **Medium** | **Crash with a huge quantity of a drink made from a recipe.** Typing a 309-digit quantity in New Sale's "Add to basket" box (or the drink window; neither box has a maximum) gives *Internal Server Error* (500). The number is too big to turn into a decimal (`OverflowError` in `Recipes.usage`, `app.py:670`). Products without a recipe are fine (their stock check stops it). | Reproduced: 309 and 400 digits → 500; 300 digits → message | Refuse quantities above `MAX_QUANTITY` (1,000,000) in `new_sale()` before any calculation. **Small** |
| **A2** | **Medium** | **One basket can be sold twice.** Two *Complete Sale* requests sent at the same moment with the same basket both succeed: two receipts, stock taken twice. The basket lives in the browser's cookie, so both requests carry it. | Reproduced with two simultaneous requests: 2 sales, stock 12 → 8. A real double-click in Chromium made only 1 sale (the browser itself helped), but a slow network, a retry or a script can still cause it | Give each basket a one-time "sale ticket" checked by the server, and disable the button after the first click. **Medium** |
| **A3** | **Medium** (Windows) | **Outdated Werkzeug 3.1.8 (CVE-2026-102598).** On Windows, asking for a special device name such as `NUL:` among the static files makes the request hang forever. Enough of them can tie up the server. The demo laptop runs Windows. | `pip-audit`. Not reproduced here (the test machine is Linux) | Change `Werkzeug==3.1.8` to `3.1.9` in `requirements.txt`. All 17 test files pass with it. **Very small** |
| **A4** | **Medium** | **Memory can be filled through the login form.** The login limit remembers every wrong username, never forgets the ones not tried again, and stores them at full length (up to about 500 KB each). | 50 tries with 450 KB usernames kept **33 MB**; 3,000 random usernames kept 3,000 entries | Cut the username to 80 characters before counting, and drop old entries for everyone, not just the one being checked. **Small** |
| **A5** | **High** if put online | **Demo passwords are public.** `admin` / `admin123` and `cashier` / `cashier123` are written in the documentation on GitHub. | Test case TC-5.1 in the documentation; `add_users.py` | Change both before the demo (Profile → Change password). Later: force a new password on first log-in. **None / small** |
| **A6** | **Medium** | **Logins can't be cancelled.** A copied session cookie keeps working after the owner logs out, and even after the password is changed. Sessions also never time out while the browser stays open. On a shared counter computer, the next person stays logged in as the previous one. | Reproduced: copied cookie → 200 after log-out and after a password change; the cookie has no expiry | Store a "session version" with each user (changed on log-out and password change) and log sessions out after, for example, 8 idle hours. **Medium** |
| **A7** | Low | **Change password has no attempt limit.** Someone using a stolen session could guess the current password there without the 5-try limit. | Code review (`change_password()`) | Reuse the login limit for this form. **Small** |
| **A8** | Low | **Usernames can be discovered by timing.** A wrong password for a real user takes about 100 ms (the password hash is checked); for an unknown user about 1 ms. | Measured: 100 ms vs 1 ms | Check a dummy hash for unknown users. **Small** (only 2 accounts, both public anyway) |
| **A9** | Low | **Two products can have SKUs that differ only in capitals** (`HC-001` and `hc-001`). | Reproduced | Compare SKUs without regard to capitals. **Small** |
| **A10** | Low | **No Content-Security-Policy header**, and the development server announces `Werkzeug/3.1.8 Python/3.13`. A CSP is a second wall against script injection. | Live probe | Add a CSP when the CDN files are bundled (offline patch); use a production server when deploying. **Small** |
| **A11** | Low | A crash shows the plain default *Internal Server Error* page, not a friendly one. | Seen with A1 | Add a `500.html` like `403.html`. **Very small** |
| **A12** | Info | **Any logged-in user can open any receipt** by its number (`/sales/5`), including another cashier's GCash reference. | Reproduced | A decision: normal for a small café, or limit cashiers to their own receipts. |

**Status:** A1 (DEF-47), A3 (DEF-49) and A4 (DEF-50) were fixed in **v0.19.3** on 2026-10-11 and the attacks re-run (test cases TC-20.1–20.5). A9 (DEF-52) in **v0.20.2** (2026-10-12). A5 needs the passwords changed on the demo laptop.

**Before Monday's demo:** A1, A3 and A5 are the quickest and matter most, because the professor will try to break
the system on a Windows laptop. A2 and A4 are the next patch. This follows the stabilization rule: fix as v0.19.x
patches before any new feature.

## 4. Risks for future goals (not attacks, but they would cause bugs later)

| # | Goal it affects | Risk | What to do |
|---|---|---|---|
| **R1** | Going online | **Time zone.** The app uses the computer's local time with no zone. A cloud server usually runs on UTC, so "today", the report's days and receipt times would be **8 hours off**. | Store times in UTC and show them in Asia/Manila (`zoneinfo`). |
| **R2** | Going online | **Login limit lives in memory.** It resets on restart and isn't shared when a host runs several copies of the app. Behind a host's proxy, every visitor may appear to have the same address, so 5 wrong tries could lock `admin` for everyone. | Check `request.remote_addr` on the host; store attempts in the database. |
| **R3** | Going online | `app.run()` is Flask's **development server**, not meant for the internet. | Use the host's WSGI server (e.g. PythonAnywhere) or `waitress` on Windows. |
| **R4** | Offline demo | Bootstrap, the icons and the Inter font loaded from the internet; without it the layout and icons broke (tested 2026-10-10). | ✅ Done in **v0.19.4**: stored in `static/vendor/`, AGENTS.md rule D2 changed (DEF-53, TC-21.1–21.5). |
| **R5** | Accounting | **Money is stored as decimal "floats".** Rounding to 2 places hides it today, but sums of many prices can drift by a centavo. | Store centavos as whole numbers, or use `Decimal`. |
| **R6** | New features | `upgrade_database()` can only **add** columns. Changing a type (e.g. decimal product quantities) or renaming needs a real migration tool. | Flask-Migrate (Alembic). |
| **R7** | Software Engineering 2 | `app.py` is one 1,285-line file, and the safe stock update (`… WHERE quantity >= n`) is SQL-specific. Moving to Firebase or several databases needs a separate "data layer". | Split into Flask *blueprints*; put database access behind functions. |
| **R8** | Library upgrades | `User.query.get()` (in `load_user`) is a deprecated SQLAlchemy call. It still works on 2.1.4 (tested). | Replace with `db.session.get(User, …)`. |
| **R9** | Real café use | No screen to add a cashier, reset a password or deactivate a user; no backup button; no record of who changed a price or deleted a product. | User management, backup/restore, audit log. |
| **R10** | Demo consistency | The built-in demo menu still names its servings **12oz / 16oz**, while the app and the café menu use **Hot / Iced**. | Rename in `seed_demo_data.py`. |
| **R11** | Tooling | `requirements.txt` is saved as UTF-16 (from PowerShell's `pip freeze >`). pip reads it, but some tools may not. | Save it as UTF-8. |

## 5. How this maps to the report (Lectures 11–12)

- **Vulnerability, attack, threat, control** (L11 p. 42): each row of §3 is a *vulnerability*; the evidence column is
  the *attack*; the fix column is the *control*.
- **Vulnerability avoidance** (L11 p. 45): §2 lists the controls already in place.
- **Threat and control analysis** (L12 p. 46): §3 and §4 together are a preliminary risk assessment, rated by severity.

*Scripts used: fuzzing (6,417 requests), targeted attacks and the double-submit test were run in a temporary copy of
the project, never on the real database. Defects A1–A4, A6 and A9 are recorded as DEF-47 to DEF-52 in the
documentation draft (§7).*
