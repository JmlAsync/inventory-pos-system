# Upgrade plan: from course project to a client-ready system

*Written 2026-10-24, against v0.21.2. Plan only: nothing here is built yet.*

This plan covers three requests:

1. **New sign-in:** sign up and log in with Gmail (Google), plus a code sent by email to confirm every
   registration and login, unless the user has marked the device as trusted.
2. **Two ways to install:** a **local** package (SQLite on the shop's own computer, as today) and a **cloud**
   package (managed PostgreSQL), so a client can choose, or use a cloud database they already pay for. A
   **Firebase** package (Firestore) is offered only to clients who already use Firebase, never as the first choice.
3. **Every missing feature** listed in the final report (refunds and voids, undo, backups, discounts,
   end-of-day readings and the rest), each designed carefully before it is built.

It ends with the order to build things in (§6) and the decisions the owner and the client must make first (§1).

---

## 1. Decisions

Some of these requests clash with rules already in `AGENTS.md`. Rule C8 says a rule is not changed to make a
change pass; the owner decides. **On 2026-10-24 the owner decided D-1 to D-5 as recommended below, with D-4
replaced by the subscription model** (§2.2), and the rules were rewritten (§5). D-6 to D-8 are settled with
the client later. **D-9 and D-10 came from checking every decision against its alternatives
(`docs/decisions.md`, rule C10) and wait for the owner.** Each decision's full reasoning is in that file.

| # | Decision | Why it is needed | Recommendation |
|---|---|---|---|
| **D-1** | **Allow new packages** (rule D1) | Google sign-in needs an OpenID Connect library; Firestore needs Google's client library; real database migrations need Alembic | Approve, each pinned to an exact version: `Authlib` (Google sign-in), `requests` (Authlib uses it to talk to Google), `google-cloud-firestore` (cloud package only), `Flask-Migrate` + `alembic` (migrations), `waitress` (a real web server on Windows). Email codes need **no** new package: Python's own `smtplib` sends mail. Each of these brings packages of its own (Firestore alone brings `grpcio`, `protobuf`, `google-auth` and more), so the allowlist in `check_contract.py` grows per install profile (§3.1) |
| **D-2** | **What "works without internet" means now** (rule D2, NFR-12) | Google sign-in, email codes and Firestore all need the internet. A café whose Wi-Fi drops must still be able to sell | Keep D2 for page files (still nothing loaded from a CDN). Add: *the local package must keep selling with no internet on trusted devices*. See §2.6 for how |
| **D-3** | **One file `app.py`** (AGENTS.md §2: "one file on purpose") | Two databases need a separate data layer (audit risk R7), and `app.py` is already 1,586 lines | Split into Flask *blueprints* and a `store/` package after the course submission (§3.2) |
| **D-4** | **Who may sign up** | A POS where anyone can create an account would let a stranger make themselves a cashier | **Decided:** the shop's **owner** account comes from the subscription purchase and uses the email it was bought with; cashiers (and any extra admins) join **only by invitation** to their own email. No open sign-up page anywhere in the shop's system (§2.2, rule S12) |
| **D-5** | **Code after Google sign-in too?** | Google often asks for its own second step already | Ask for our code after Google too, as requested: one rule for every login is easier to explain and test. Trusted devices skip it in both cases |
| **D-6** | **How long a device stays trusted** | Longer is more convenient, shorter is safer | 30 days for cashiers, 7 days for admins; trust ends at once on log-out-everywhere, password change or removal from Profile |
| **D-7** | **Which database the client wants** | Each client chooses; §3.6 is the comparison to show them | Local (SQLite) by default; managed PostgreSQL when the client wants the cloud (several branches, data kept off the laptop) and has steady internet; Firestore only if they already use Firebase; PostgreSQL / MySQL when the client already pays for a cloud SQL server |
| **D-9** | **Second step: also allow an authenticator app?** | The check in DEC-004 found that an authenticator app works with no internet, which emailed codes can't | **Decided 2026-10-24:** emailed code by default; each user may choose an authenticator app instead (DEC-017, §2.4) |
| **D-10** | **Default cloud database** | The check in DEC-014 found that managed PostgreSQL fits this system's data with almost no new code, while Firestore needs a whole second store | **Decided 2026-10-24:** managed PostgreSQL is the cloud option; Firestore is optional, only for clients already using Firebase, never first (DEC-014) |
| **D-8** | **Timing** | The course report describes v0.21.2 | Start only after the submission is in. The report and the submission zip stay as they are |

---

## 2. Authentication upgrade

### 2.1 What the user will see

```
                    ┌───────────────────────┐
  Log in page ──►   │ Username + password   │──┐
                    │   or                  │  │  correct
                    │ "Sign in with Google" │──┤
                    └───────────────────────┘  │
                                               ▼
                               Is this device trusted for this user?
                                  │ yes                    │ no
                                  ▼                        ▼
                              Logged in        A 6-digit code is emailed
                                               "Enter the code we sent to m•••@gmail.com"
                                                           │ correct code
                                                           ▼
                                               [ ] Trust this device for 30 days
                                                           │
                                                           ▼
                                                       Logged in
```

- **Login and the code are mandatory** on every device that is not trusted.
- **Trusting a device skips only the code**, never the password or Google step.
- The code screen offers **Resend code** (after 60 seconds) and **Use a backup code** (§2.6).

### 2.2 Who gets an account (rule S12)

Nobody can create their own account in a shop's system. There are exactly two ways in:

**The owner, from the subscription.**

```
Subscription website                         The shop's system (local or cloud)
──────────────────────                       ───────────────────────────────────
Client buys a plan with                      setup_shop.py asks for the licence key
maria@gmail.com  ──► licence key emailed ──► checks it with the subscription website
                                             ──► owner account = maria@gmail.com
                                             ──► code emailed to maria@gmail.com, entered once
```

- The owner account's email is **fixed to the purchase email**. The owner can't be deleted, demoted or have the
  email changed inside the shop's system; changing it is done on the subscription website, which then tells the
  shop's system (§2.11).
- The owner signs in with a password or with Google, as long as the Google account is that same email.

**Everyone else, by invitation.**

1. The owner opens **Users → Invite**, types the person's **own** email address and picks the role: Cashier,
   or Admin if the owner wants a manager. The owner can allow admins to invite cashiers; only the owner can
   invite admins.
2. The system emails a sign-up link holding a random one-time token (valid 48 hours, stored only as a hash).
3. The person opens the link and either **chooses a username and password** or **taps "Sign in with Google"**.
   With Google, the Google account's email must be the invited address.
4. A 6-digit code is emailed to confirm the address; entering it activates the account with the role the
   inviter chose. Nothing the new user does can change that role.

The demo accounts `admin` / `cashier` stay for the demo install only, behind `DEMO_MODE` (§2.7).

### 2.3 Sign in with Google (Gmail)

- **How:** OpenID Connect "authorization code" flow through **Authlib**, with `state`, `nonce` and PKCE.
  Scopes: `openid email profile` only (no access to the user's Gmail inbox).
- **Checks on Google's answer:** issuer is Google, audience is our client ID, not expired, `email_verified`
  is true. Accounts are linked by Google's permanent user id (`sub`), not by the email, because an email
  address can change hands.
- **One account, two ways in:** a user can link Google to an existing password account from Profile, after
  entering their password and a code.
- **Setting it up (once, by whoever installs the system):** a Google Cloud project → OAuth consent screen
  (External; the "Testing" mode allows up to 100 named users, enough for a café) → OAuth client ID of type
  *Web application* → redirect address `http://localhost:5000/auth/google/callback` and, if the system is put
  online, `https://<the shop's domain>/auth/google/callback`. The client ID and secret go in
  `instance/config.toml` or environment variables, never in Git.
- **Limit to state honestly to the client:** Google only accepts `localhost` or an `https` address on a real
  domain as a redirect. A phone on the café's Wi-Fi opening `http://192.168.1.10:5000` **cannot** use Google
  sign-in. In the local package, Google sign-in therefore works on the main computer; other devices use the
  password + code. In the cloud package with a domain and HTTPS it works everywhere.

### 2.4 Email codes

| Rule | Value | Why |
|---|---|---|
| Length | 6 digits, from `secrets.randbelow` | Easy to type; 1 in a million to guess |
| Stored as | HMAC-SHA256 of the code with the secret key, never the code itself | A copy of the database does not reveal live codes |
| Valid for | 10 minutes, one use, one purpose (`signup`, `login`, `link-google`, `reset-password`) | A code for one thing can't be used for another |
| Wrong tries | 5 per code, then the code is cancelled and a new one must be sent | Stops guessing (same idea as the login limit, S10) |
| Resend | Once every 60 seconds, at most 5 an hour per account | Stops someone flooding a mailbox |
| Compared with | `hmac.compare_digest` | No timing leak |
| Email text | The code, what it is for, the time and the device; "If this wasn't you, change your password" | Users can spot a login that isn't theirs |

**Sending mail:** `smtplib` with settings in `config.toml` (host, port, user, password, from-address). Works with
a Gmail account through an *App Password* (needs 2-Step Verification on that account; personal Gmail allows
roughly 500 messages a day) or with any transactional mail service. A **test button** on the settings page sends
a test message so the owner knows it works before relying on it.

**Authenticator app instead of email (DEC-017).** From Profile → Sign-in method a user can switch to an
authenticator app (Google Authenticator, Microsoft Authenticator…): password again, scan a QR code, type the
current code to confirm, new backup codes, and an email saying the method changed. The app's codes need no
internet. The app's key is stored encrypted; a code's 30-second step is never accepted twice; the same 5-try limit
applies. A lost phone: a backup code, or the owner / an admin resets the user to email (logged and emailed); the
owner's own reset goes through the subscription seller.

### 2.5 Trusted devices

- After a correct code, the box **"Trust this device"** creates a `trusted_device` record and a second cookie
  (`HttpOnly`, `SameSite=Lax`, `Secure` when served over HTTPS) holding 32 random bytes. The database keeps
  only a hash of it, the user, a short device label ("Chrome on Windows"), the creation date, the last use and
  the expiry.
- A trust cookie only counts for the user it was made for. A shared counter computer can be trusted by each
  cashier separately.
- **Profile → Devices** lists the user's trusted devices with a **Remove** button. **Log out everywhere**,
  a password change, and an admin deactivating the user all remove every trusted device.

### 2.6 When there is no internet (local package)

Email can't be sent without internet, so an untrusted device would be locked out. Two safety nets:

1. **Trusted devices keep working offline:** password only, no code. The counter computer should be trusted.
2. **Backup codes:** each user can print 10 one-time backup codes (shown once, stored as hashes) and use one
   instead of an emailed code.

If both fail, the owner can still sign in on the main computer with a backup code and trust it again.

### 2.7 Demo and development mode

`DEMO_MODE=1` (off by default) writes codes to the console instead of emailing them, so the demo install and
the automated tests run with no mail server and no internet. The start-up refuses `DEMO_MODE` together with a
real mail configuration, so it can't be left on by mistake in a shop.

### 2.8 Database changes (added through migrations, §3.4)

| Table | New columns / table | Notes |
|---|---|---|
| `user` | `email` (unique, lower-case), `email_verified_at`, `google_sub` (unique, may be empty), `is_active`, `must_change_password`, `created_at`; `role` gains **`owner`** | `password_hash` may be empty for Google-only users. Exactly one owner per shop |
| `invitation` *(new)* | email, role, token hash, invited_by, expires_at, used_at | Only the owner may invite an admin (S12) |
| `licence` *(new)* | licence key, purchase email, plan, valid until, last successful check, signature | One row; checked daily (§2.11) |
| `email_code` *(new)* | user or invitation, purpose, code hash, attempts, expires_at, used_at | Old rows tidied up like `login_session` |
| `trusted_device` *(new)* | user, token hash, label, created_at, last_used_at, expires_at | |
| `backup_code` *(new)* | user, code hash, used_at | |
| `user` (more) | `second_step` (`email` or `app`), `totp_key_encrypted`, `totp_last_step` | DEC-017 |
| `login_attempt` *(new)* | key, time | Replaces the in-memory login limit (audit R2), so it survives a restart and works with several server processes |

### 2.9 Pages to add (each listed in `tests/check_contract.py`, rule S1)

| Page | Who | Purpose |
|---|---|---|
| `/login/google`, `/auth/google/callback` | public | Google sign-in start and return |
| `/verify`, `/verify/resend` | half-logged-in | Enter or resend the email code |
| `/signup/<token>` | public, valid invitation only | Finish an invitation |
| `/forgot-password` | public | Reset by emailed code (answers the same way whether or not the email exists) |
| `/profile/devices`, `/profile/backup-codes`, `/profile/link-google` | user | Manage own sign-in |
| `/admin/users` | admin (inviting admins: owner only) | Invite, change role, deactivate, resend invitation (audit R9). The owner's own row can't be changed here |

"Half-logged-in" is a new state: the password was right but the code is still missing. It gets its own short
session value (5 minutes) and opens nothing except `/verify`. The state diagram of a login (report §7.12 c) gains
one state, *Waiting for code*.

### 2.10 Tests (rules C4, T3)

- A fake Google: the tests replace the token check with one that returns prepared answers (right, wrong
  audience, expired, unverified email, a different `sub`). No internet.
- A fake mailbox that collects outgoing mail, so tests read the code from it.
- Cases: every row of §2.4; trusted device skips the code; expired, removed, other user's and copied-after-
  password-change trust cookies are refused; invitation used twice; Google email different from the invitation;
  cashier opening `/admin/users` gets 403; CSRF token on every new form; backup code used twice; offline
  login on a trusted device.

### 2.11 The subscription website and the licence (a separate project)

The website where clients buy the subscription is **its own system**, not part of this repository: it holds
payments and client details that must never sit on a café's laptop. It needs only a small connection to the
shop's system:

| Moment | What happens | If there is no internet |
|---|---|---|
| Setup | The licence key and purchase email are checked; the owner account is created with that email | Setup waits until there is internet (needed once) |
| Every day | The shop's system checks the licence once in the background | Nothing changes; the last good check is kept |
| Licence about to end | Warning on Home for the owner, 14 days before | — |
| Licence ended or not checked for 30 days | **Selling continues for the day**; then new sales stop, while reports, receipts and the data **export** stay open | Same 30-day grace |
| Owner email changed on the website | The next check updates the owner account and sends a code to the new email | Applied at the next successful check |

**Careful choices here:** a licence problem never stops a sale halfway or locks the owner out of their own
records (they must always be able to export their data, which also matters under the Data Privacy Act). The
licence key is checked with a signature from the subscription website, so editing the database can't fake it.
Building the website itself (plans, payment, the client's account page) is a separate plan once the client
agrees on prices.

---

## 3. Two installation packages: local or cloud

### 3.1 One codebase, two install profiles

Two separate copies of the code would drift apart and double every fix. Instead there is **one codebase** with a
setting that chooses the database, and **two install profiles**:

| Package | Database | Installs | Best for |
|---|---|---|---|
| **Local** | SQLite file on the shop's computer | `requirements/local.txt` | One shop, one counter computer, unreliable internet, no monthly bill |
| **Cloud** *(recommended cloud option)* | Managed PostgreSQL (Google Cloud SQL, Supabase, Neon, Amazon RDS…), or the client's own PostgreSQL / MySQL server; same code as Local, a different `DATABASE_URL` | `requirements/cloud.txt` (adds the `psycopg` driver) | Several branches or devices across the internet, data kept off the laptop, a client who already pays for a SQL server |
| **Firebase** *(optional, never first)* | Google Firestore | `requirements/firebase.txt` | Only a client who **already** runs Firebase and wants the shop's data there (DEC-014) |

```
Flask routes (blueprints) ──► store interface ──┬──► SqlStore ──► SQLite / PostgreSQL / MySQL
  (checks, pages, CSRF,         (complete_sale,   │
   roles: unchanged)             restock, ...)    └──► FirestoreStore ──► Firestore (optional, built on request)
```

### 3.2 The data layer (`store/`)

The routes stop calling `Product.query…` directly. They call a small set of named operations, each of which keeps
today's rules:

| Operation | Rule it must keep |
|---|---|
| `complete_sale(basket, payment, ticket, user)` | All or nothing (I1, I2); stock never below zero; one receipt per ticket; GCash reference used once |
| `restock(ingredient, amount, user)` / `count(…)` | History line for every change (I7); restock adds safely |
| `void_sale(…)`, `refund(…)` | §4.1 |
| `create_product`, `update_product`, `archive_product` | SKU unique ignoring capitals; sold products never deleted (I4) |
| `sales_between(start, end)`, `daily_summary(day)` | Report totals |
| users, logins, codes, devices | §2 |

Rule I1 is written today in SQL terms (`WHERE quantity >= n`). It would become: *every stock change goes through
a store operation that checks and subtracts in one atomic step*; `check_contract.py` then checks that no route
touches stock directly.

The same test suite runs against SQLite and, in GitHub Actions, a throw-away PostgreSQL server. If the Firebase
package is built, the suite also runs against Firestore, using the **Firestore emulator** (part of
`firebase-tools`, already installed on the development laptop), locally and in GitHub Actions, so tests never
touch a real cloud project.

### 3.3 How the hard parts work on Firestore (Firebase package only)

*Kept for the day a client on Firebase asks. The cloud package (PostgreSQL) needs none of this: it uses the SQL
store as it is.*

| Today (SQL) | On Firestore |
|---|---|
| Conditional update `quantity >= n` inside one transaction | A Firestore **transaction**: read every product and ingredient in the basket, check, then write all decreases and the sale. Firestore retries it if another till changed the same documents in between, so overselling stays impossible |
| Unique columns (SKU, GCash reference, sale ticket) | Firestore has no unique indexes. A "claim" document whose id is the value (`skus/hc-001`, `gcash_refs/1023456789012`) is created **in the same transaction**; a second claim fails. The sale ticket simply becomes the sale document's id |
| Receipt numbers 1, 2, 3… | A counter document increased inside the sale transaction (fine for a café's pace; one counter per branch) |
| `SaleItem` rows | Stored inside the sale document as a list: a receipt never changes (I3) and is always read whole |
| Reports with `SUM` | Each sale also adds to a **daily summary** document in its transaction, so a report reads one document per day instead of every receipt (fewer reads, lower bill) |
| Local time | Times stored in UTC (Firestore always does), shown in Asia/Manila (audit R1). Done for SQL too, in Phase 1 |
| Product pictures in `static/products/` | Kept as files on the server at first; Cloud Storage is a later option |

Firestore's security rules will **deny all direct access**. Only the Flask server, using a service-account key,
reads and writes. The roles, CSRF tokens and checks stay in one place (the server), exactly as now.

### 3.4 Migrations, money and moving between databases

- **Alembic** (through Flask-Migrate) replaces `upgrade_database()` for the SQL store (audit R6). The first
  migration describes today's tables, so existing shop databases upgrade without losing data (rule I5 is
  reworded to "every database change is a migration").
- **Money in whole centavos** (audit R5): `₱180.00` is stored as `18000`. Done once, in a migration, before the
  cloud store exists, so Firestore never sees floats.
- **Export / import:** `python manage.py export shop.json` and `import`, for any store. This moves a shop from
  local to cloud (or back) and doubles as a portable backup.

### 3.5 Setup for each package

`python setup_shop.py` asks the questions and writes `instance/config.toml` (read with Python's own `tomllib`):

1. The **licence key** from the subscription purchase; it is checked online and gives the owner's email (§2.11).
2. Shop name, address and TIN for receipts (§4.3).
3. Database: *Local* (default), *Cloud* (asks for the PostgreSQL connection address and tests it) or, only in
   the Firebase package, *Firebase* (asks for the project id and the service-account key file, copied into
   `instance/`).
4. Email sending (or "skip for now" → demo mode warning).
5. Google sign-in (optional; client id and secret).
6. The owner's password, then a code emailed to the purchase email to confirm it.

Then `start_shop.bat` runs the app with **waitress** (audit R3) instead of Flask's development server.
Guides: `docs/install_local.md`, `docs/install_cloud.md` and, when built, `docs/install_firebase.md`.

### 3.6 Comparison to show the client

| Question | Local (SQLite) | Cloud (managed PostgreSQL) | Firebase (Firestore), only if already on Firebase |
|---|---|---|---|
| Keeps selling when the internet is down? | **Yes** | **No**, unless the server is in the shop | **No**: the counter needs internet for every sale |
| Monthly cost | None | A fixed plan (several providers have a free starting tier), or the client's existing plan | Free tier usually enough for one café; billed per read and write above it (check Google's current pricing with the client) |
| Backups | Backup button + daily copy to a second drive (§4.4) | The provider's backups | Google keeps the data; scheduled exports for extra safety |
| Several branches or devices over the internet | No (one shop network) | Yes | Yes |
| Google sign-in on every device | Main computer only (§2.3) | Yes, with a domain and HTTPS | Yes, with a domain and HTTPS |
| Who looks after it | The owner (the laptop) | The provider | Google |
| Data stays in the Philippines | Yes | Depends on the provider | Choose the region (e.g. `asia-southeast1`); note it for the Data Privacy Act |

---

## 4. The missing features, one by one

Everything the final report lists as a known limitation (§10.4), the unmet safety and reliability requirements
(SR6, SR7, RR7), and the open audit items. Each has a design note, the rule it must respect, and how it is tested.

### 4.1 Voids and refunds (report §10.4, state diagram "Void requested")

The original receipt is **never edited or deleted** (rule I3). Every correction is a new record that points to it.

| | **Void** | **Refund** |
|---|---|---|
| When | Same business day, before the Z reading, whole receipt | Any later day, whole receipt or chosen lines and quantities |
| Typical case | Wrong item rung up, customer changed their mind at the counter | Customer brings back a drink or pastry |
| Who | Cashier **requests**; an admin **approves** with their password (or an emailed code if not at the till) | Admin only |
| Stock | All products and ingredients go back | Per line, the admin chooses **Return to stock** (an unopened pastry) or **Waste** (a made drink): waste is recorded but not returned |
| Money | Cash back from the drawer, or "GCash refund done in the GCash app" with that reference | Same |

- **New table `sale_adjustment`:** sale, kind (void / refund), status (requested / approved / rejected), lines
  (product, quantity, amount, restock yes/no), total, refund method and reference, reason (required), requested
  by, approved by, times.
- **States:** Completed → Void requested → Voided / Rejected; Completed → Refunded (partly or fully). A receipt
  can't be refunded for more than was paid; two admins approving at once can't double the refund (a
  conditional update on the sale's refunded amount, same idea as I1).
- **Stock returns** are new history lines with reason `void`, `refund` or `waste` (rule I7).
- **Receipt page** shows "VOIDED" or "Refunded ₱… on …" and links to a printable refund slip.
- **Reports** show gross sales, voids, refunds and **net** sales; cash expected in the drawer subtracts cash
  refunds.
- **Tests:** void approval and rejection; cashier can't approve; double approval; refund above the amount paid;
  partial refund then a second partial refund; stock and ingredient history after each; report totals.

### 4.2 Undo

"Undo" means different things in different places. Each gets the safe version:

| Where | What undo does | Limit |
|---|---|---|
| **Basket** (report §10.4, "no undo for a tap") | An **Undo** button after every basket change brings back the basket as it was | The last 5 changes; the basket only lives in the session, so nothing in the database changes |
| **Completed sale** | No undo: it is a **void** (§4.1), because money and stock have already moved | — |
| **Ingredient Count** | **Undo** for 5 minutes adds the opposite history line | Refused if sales happened since (the count would be wrong either way); then the admin counts again |
| **Product edits and deletes** | No undo, but every change is in the **audit log** (§4.5) with the old values, so it can be put back by hand | — |

### 4.3 Receipts

- **"This is not an official receipt"** printed on every receipt (SR6). Small, but it closes the one intolerable
  risk in the report (§9.5, hazard 10).
- **Shop name, address, TIN and footer** from the settings instead of the fixed "Inventory & POS".
- **Reprint** marked "REPRINT" with the time it was printed.
- **BIR registration stays out of scope:** an accredited POS needs a BIR-accredited supplier and a Permit to Use
  per machine. The client keeps their registered POS for official invoices; this system remains their order and
  inventory system unless they pursue accreditation themselves.

### 4.4 Backup and restore (SR7, RR7)

- **Backup now** (admin): a consistent copy of the database using SQLite's own backup feature (safe while the
  shop is selling) plus the picture folders, zipped and named with the date.
- **Daily automatic backup** to a second folder (a USB drive or a synced cloud folder), keeping the last 14.
- **Restore** from a backup file: checks it first, keeps the current database under a new name (as `--fresh`
  does), then restarts.
- On the cloud package: scheduled Firestore exports, plus the same `export` file.
- **Tests:** a backup taken during a sale opens and contains either the whole sale or none of it; restore keeps
  the old file.

### 4.5 User management and audit log (audit R9, A5)

- **Users page** (§2.9): invite, change role, deactivate (never delete: receipts name their cashier), resend
  invitation, require a new password.
- **First-login password change** for accounts made by setup or by reset (audit A5).
- **Forgotten password** by emailed code (report §10.4).
- **Audit log** table: who changed which price, stock number, option, recipe or user, with old and new values and
  the time. An admin page lists and filters it.

### 4.6 Senior citizen and PWD discounts (report §10.4)

- A **Discount** button on the basket: Senior citizen or PWD, with the ID number and name required (kept on the
  sale for the shop's records).
- **The exact computation is a decision for the client and their accountant** (which items qualify, whether the
  20% applies before or after removing VAT, one or several qualifying customers per receipt). The plan is to
  confirm the rules in writing with the client first, then write them as a computation table like §6.6 of the
  report, then code and test every row.
- The discount is a separate line on the receipt and a separate total in the reports.

### 4.7 Shift and end-of-day readings (X and Z)

- **Open shift:** the cashier enters the starting cash (float).
- **Cash in / cash out** during the shift with a reason (paying a supplier, adding change).
- **X reading** (any time, shift so far) and **close shift:** the cashier counts the drawer; the system shows
  expected cash = float + cash sales − cash refunds ± cash in/out, and records the difference.
- **Z reading** (end of day, admin): totals for the day, payment split, voids, refunds, discounts, first and last
  receipt number. After the Z reading, that day's sales can only be corrected by refund, not void.

### 4.8 Inventory improvements

| Item (report §10.4) | Change |
|---|---|
| Count overwrites a sale made at the same moment | Count saves the difference against the amount it read, with a conditional update; if a sale changed it in between, the admin is asked to count again |
| Product stock overwritten by the Edit form | Products without a recipe get **Restock** and **Count** like ingredients, with history |
| Sold products can't be deleted | **Archive**: hidden from the menu and lists, kept for receipts and reports, can be restored |
| One low-stock level (5) for every product | A **warn at** level per product |
| Ingredient groups are a fixed list | Groups managed on a settings page |
| Recipe amounts are estimates | A "confirmed by owner" tick per recipe, and a list of recipes not yet confirmed |

### 4.9 Security and quality fixes from the audit

| Audit item | Fix |
|---|---|
| A7 change password has no attempt limit | Use the database login limit (§2.8) on that form |
| A8 usernames found by timing | Check a dummy hash for unknown usernames |
| A10 no Content-Security-Policy | Move the inline scripts into files in `static/js/`, then send a strict CSP |
| A11 plain crash page | A friendly `500.html` |
| A12 any user can open any receipt | Client decision; default: cashiers see their own shift's receipts, admins see all |
| R1 time zone | UTC in the database, Asia/Manila on screen |
| R2 login limit in memory | `login_attempt` table (§2.8) |
| R3 development server | waitress |
| R8 deprecated `User.query.get` | `db.session.get` |
| R10 demo servings named 12oz / 16oz | Hot / Iced in the demo menu |
| R11 `requirements.txt` saved as UTF-16 | Save as UTF-8 |
| Report: light/dark per browser | Also saved on the user's account |
| Report: no favicon; dark-theme tile bars the same colour | Add the icon; give the Low bar its own colour |
| Report: browser tests by hand | Playwright tests in a separate `tests/browser/` folder with their own `requirements/dev.txt`, run in GitHub Actions |
| Report: GCash recorded, not verified | Only possible with a merchant account and a payment provider's API. Offered to the client as an option, not built by default |

---

## 5. Rules (AGENTS.md) changed on 2026-10-24

The owner accepted these. Each replaced rule keeps its old wording in an *Overridden* note below it, with the
reason, and a rule that only applies from a later version says so:

- **D1:** add the packages approved in D-1, D-10 and DEC-017, and split `requirements.txt` into
  `requirements/local.txt`, `requirements/cloud.txt`, `requirements/firebase.txt` and `requirements/dev.txt`.
- **D2:** the page-files rule is unchanged; the offline promise now covers selling in the local package.
- **§2 "Where things are":** blueprints, `store/`, `migrations/`, `static/js/`.
- **I1:** reworded for the store operations (§3.2). **I5:** "every database change is a migration".
- **P1:** add `instance/config.toml`, the service-account key and any `client_secret*.json` to the never-commit
  list and to `.gitignore`.
- **New S12:** no self sign-up; the owner comes from the subscription email, everyone else by invitation.
- **New S13:** password (or Google) plus an emailed code on every login, unless the device is trusted.
- **New S14:** codes, invitation tokens, trust tokens and backup codes are stored only as hashes and compared
  with `hmac.compare_digest`.
- **New S15:** a void, refund, role change or deactivation needs an admin; a cashier gets 403 on the approval pages.
- **New I8:** receipts are never edited; voids and refunds are new records.
- **T4:** browser tests automated from v1.0.0 with their own dev requirements.
- **T1–T3** unchanged: the Firestore tests use the emulator, never a real project.

---

## 6. Order of work

Each line is one branch and one pull request (rule C1), with tests that fail before and pass after (C3, C4), and
the stabilization rule (C2) between phases. Sizes: **S** = a day or less, **M** = a few days, **L** = a week or more.

| Phase | Version | Work | Size |
|---|---|---|---|
| **0. Before** | — | Submit the course project (v0.21.2) and defend it (Tue 2026-10-27). ✅ Owner decisions and rules (§1, §5, 2026-10-24). Client chooses a package (§3.6) and confirms discount rules (§4.6) | S |
| **1. Foundations** | v0.21.3 – v0.21.7 (patches) | One fix each: A8 (login timing), A11 (friendly 500 page), R8 (deprecated call), R10 (demo servings Hot / Iced), R11 (`requirements.txt` as UTF-8), favicon and dark-theme tile colour. **Built for Sunday's tests (DEC-018)** | S each |
| | v0.22.0 | "This is not an official receipt" (SR6) + shop name, address, TIN and footer set by the owner (§4.3) | S |
| | v0.23.0 | Alembic migrations, first migration = today's tables (§3.4) | M |
| | v0.23.x | UTC times; money in centavos (each a migration with a test on a copy of a real old database) | M |
| | v0.24.0 | waitress, `config.toml`, `setup_shop.py` (local only for now) | M |
| **2. Data layer** | v0.25.0 | Blueprints + `store/` with `SqlStore`; **no visible change**, every existing test still passes | L |
| **3. Sign-in** | v0.26.0 | Email sending, `login_attempt` table, A7 | M |
| | v0.27.0 | Owner role, users page, invitations, forgotten password, first-login password change, audit log | L |
| | v0.28.0 | Email codes on every login, authenticator-app option, trusted devices, backup codes, demo mode | L |
| | v0.29.0 | Sign in with Google, linking from Profile | M |
| **4. Counter and back office** | v0.30.0 | Basket undo; count undo; conditional count (§4.2, §4.8) | M |
| | v0.31.0 | Voids and refunds (§4.1) | L |
| | v0.32.0 | Help on every page: a ? button with the page's help and a picture, and a Help page (DEC-034; added 2026-10-25 for the defense, later versions moved down one number) | S |
| | v0.33.0 | Shifts, X and Z readings (§4.7) | L |
| | v0.34.0 | Senior / PWD discounts, from the client's written rules (§4.6) | M |
| | v0.35.0 | Product restock/count/archive, per-product warn level, editable groups (§4.8) | M |
| | v0.36.0 | Backup and restore (§4.4) | M |
| | v0.37.0 | Inline scripts to files + CSP (A10); theme per user | M |
| **5. Cloud package** | v0.38.0 | Managed PostgreSQL: `psycopg`, cloud setup and guide, the whole suite on PostgreSQL in GitHub Actions, `export` / `import` between local and cloud | M |
| | v0.39.0 | Licence check against the subscription website (§2.11); needs that website's first version | M |
| *(optional)* | v0.40.0 | Firebase package: `FirestoreStore`, emulator tests, guide. **Only when a client already on Firebase asks** | L |
| **6. Release** | v1.0.0 | Browser tests in CI, full regression on both packages, client trial at the café, both install guides, updated report | M |

**Why this order.** Migrations, UTC and centavos come first because every later table depends on them. The
data layer comes before the new features, so sign-in, voids and shifts are written once against the store and
work on every database. The cloud package is cheap once the store exists, because PostgreSQL uses the same SQL
store. Firestore stays last and optional: it is built only for a client who already uses Firebase, when the store's
operations have stopped changing.

**Until the final defense (Tuesday 2026-10-27), DEC-018:** `main` keeps the defended version (v0.21.2) plus
documentation only. Phase 1 work is built on its own branches and pull requests, tested on Sunday evening
(2026-10-25), and merged only after the defense, so nothing new can break the system the day before it is shown.

---

## 7. Risks of the upgrade itself

| Risk | Mitigation |
|---|---|
| The data-layer split (v0.25.0) breaks something unnoticed | It ships with **no** behaviour change, the whole current suite must pass unchanged, and browser tests run before merging |
| Locked out when the internet is down | Trusted devices work offline; printed backup codes (§2.6) |
| Mail provider limits or blocks the sender | Test button; any SMTP provider can be used; codes are short and rate-limited |
| Firestore bill surprises | Daily summary documents keep report reads low; budget alert set up with the client |
| Old databases on the owner's computer | Every migration tested on a copy of a real old database first (rule I5), with a backup taken automatically before it runs |
| Scope creep | One feature per version, client sign-off on §1 and §4.6 before those phases start |
