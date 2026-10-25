# Decisions: what was decided, how it works and why

Every decision about this system gets an entry here (rules C9 and C10 in `AGENTS.md`). Each entry says:

- **Decision:** what was decided, in one or two sentences.
- **How it works:** what actually happens, step by step if needed.
- **Why:** the reasoning. Long when the decision is important or easy to get wrong, short when it isn't.
- **Alternatives checked:** the other realistic ways to do it, compared honestly.
- **Verdict:** *Best choice*, *Acceptable* (good enough, a better option exists but costs more than it gives),
  or *Better option found* (the owner should decide again).
- **Status:** *Decided*, *Proposed* or *Open: owner to decide*, with the date.

Entries are never deleted. A decision that changes later gets a new entry, and the old one is marked
*Replaced by DEC-NNN*.

| # | Decision | Verdict | Status |
|---|---|---|---|
| [DEC-001](#dec-001) | Every change and decision explains itself and is checked against alternatives | Best choice | Decided |
| [DEC-002](#dec-002) | The owner account is the subscription purchase email | Best choice | Decided |
| [DEC-003](#dec-003) | Everyone else joins only by invitation | Best choice | Decided |
| [DEC-004](#dec-004) | An emailed code on every login, unless the device is trusted | **Better option found** (add one) | Decided: authenticator option added (DEC-017) |
| [DEC-005](#dec-005) | Trusted devices skip only the code, for 30 / 7 days | Best choice | Decided |
| [DEC-006](#dec-006) | Codes and tokens are stored only as keyed hashes | Best choice | Decided |
| [DEC-007](#dec-007) | Receipts are never edited; voids and refunds need an admin | Best choice | Decided |
| [DEC-008](#dec-008) | Split `app.py` into blueprints and a `store/` data layer | Best choice | Decided |
| [DEC-009](#dec-009) | Stock rule I1 states the goal, not the SQL | Best choice | Decided |
| [DEC-010](#dec-010) | Database changes become Alembic migrations | Best choice | Decided |
| [DEC-011](#dec-011) | The packages approved for the upgrade | Acceptable | Decided |
| [DEC-012](#dec-012) | The offline promise covers selling in the local package | Best choice | Decided |
| [DEC-013](#dec-013) | Browser tests automated with Playwright from v1.0.0 | Best choice | Decided |
| [DEC-014](#dec-014) | One codebase; cloud = managed PostgreSQL; Firestore optional, never first | Best choice (after the check) | Decided |
| [DEC-015](#dec-015) | Licence checked daily with a 30-day grace period | Best choice | Proposed |
| [DEC-016](#dec-016) | The contract check blocks Google and cloud key files | Best choice | Decided |
| [DEC-017](#dec-017) | Authenticator apps as a second step, and how they are kept safe | Best choice | Decided |
| [DEC-018](#dec-018) | Keep `main` at the defended version until after Tuesday's defense | Best choice | Decided |
| [DEC-019](#dec-019) | A crash shows a friendly page; details only in the log | Best choice | Decided |
| [DEC-020](#dec-020) | Unknown usernames check a dummy password hash | Best choice | Decided |
| [DEC-021](#dec-021) | Demo menu: one product per drink, sold Hot or Iced | Best choice | Decided |
| [DEC-022](#dec-022) | Shop details live in the database; the "not an official receipt" line is fixed | Best choice | Decided |
| [DEC-023](#dec-023) | Migrations: one catch-up first migration, a backup before every upgrade | Best choice | Decided |
| [DEC-024](#dec-024) | Times stored in UTC; shown in the shop's fixed UTC+8 | Best choice | Decided |
| [DEC-025](#dec-025) | Money: whole centavos in the database, exact Decimal pesos in Python | Best choice | Decided |
| [DEC-026](#dec-026) | A shop's copy: set up once, settings in `config.toml`, served by waitress | Best choice | Decided |
| [DEC-027](#dec-027) | Six blueprints, `common.py`, and `store/` for every database change | Best choice | Decided |
| [DEC-028](#dec-028) | Wrong passwords counted in the database; Change password limited too; email sent with `smtplib` | Best choice | Decided |
| [DEC-029](#dec-029) | The owner, the Users page, invitations, emailed codes, forgotten passwords and the audit log | Best choice | Decided (two points by the owner) |
| [DEC-030](#dec-030) | A code at every login, trusted devices, backup codes, the authenticator app and demo mode | Best choice | Decided (two points by the owner) |
| [DEC-031](#dec-031) | Sign in with Google, linking it from Profile, and joining with it | Best choice | Decided (two points by the owner) |
| [DEC-032](#dec-032) | Undo on the basket, a safe stock count, and undoing a count | Best choice | Decided |
| [DEC-033](#dec-033) | Voids and refunds: how they are asked for, approved, put back on the shelf and counted | Best choice | Decided |
| [DEC-034](#dec-034) | Help on every page: a ? button with this page's help, and a Help page | Best choice | Decided (three points by the owner) |

---

## DEC-001

**Every change and decision explains itself and is checked against alternatives** *(rules C9, C10, W2)*

**Decision.** Every change has a **Why** section in its pull request. Every decision also gets an entry in this
file, checked against the other ways it could have been done.

**How it works.** The pull request template gains a **Why** heading. For anything that decides how the system
behaves, the author writes a `DEC` entry here first, compares the alternatives, and links the entry from the rule,
plan or code comment it produces.

**Why.** Until now the project recorded *what* changed (version history), *that* it worked (tests) and *what went
wrong* (defects), but the reasons lived only in chat and in people's heads. That has three costs. A reviewer can't
tell a careful choice from a lucky one. The next person (or AI assistant) can't tell which rules are load-bearing
and may "simplify" one away. And in a viva or a client meeting, "why did you do it this way?" is the first
question, and the answer has to be ready. Writing the alternatives down also catches mistakes before they are built:
doing it for the first time on 2026-10-24 found two better options (DEC-004, DEC-014).

**Alternatives checked.**

| Option | Verdict |
|---|---|
| Keep reasons in commit messages only | Hard to find later; a commit can't hold a comparison table |
| One "Why" paragraph in the pull request only | Enough for small changes (kept for those), but decisions get lost among dozens of PRs |
| A decision log, separate file per decision (classic "ADR" folder) | Same idea, but many small files are harder for a beginner to browse than one file with a table at the top |
| **One `decisions.md` with a summary table + PR Why heading** | One place to read, short for small things, full for big ones |

**Verdict:** Best choice. **Status:** Decided, 2026-10-24.

---

## DEC-002

**The owner account is the subscription purchase email** *(rule S12, plan §2.2)*

**Decision.** The email used to buy the subscription becomes the shop's one **owner** account. It can't be deleted,
demoted, or have its email changed inside the shop's system.

**How it works.** `setup_shop.py` asks for the licence key, checks it with the subscription website, and receives the
purchase email. It creates the owner account with that email and sends a 6-digit code there; setup finishes only
when the code is entered. A change of owner email is made on the subscription website and reaches the shop at the
next daily licence check (DEC-015), again confirmed by a code.

**Why.** Someone has to be the first account, and whoever it is can invite everyone else and see every sale. The
purchase email is the one identity that has already been proven: the client paid with it and receives the licence
there. Tying the owner to it means a licence key that is forwarded, leaked or copied from a receipt can't be used to
set up someone else's shop as owner, because the confirmation code goes to the buyer. It also gives a recovery
path the client already understands: if they lose access, they prove who they are to the subscription seller (who
has the payment record), not to the café's laptop. Making the owner undeletable inside the shop stops a rogue
admin from removing the person paying for the system.

**Alternatives checked.**

| Option | Problem |
|---|---|
| Owner types any email during setup | Whoever holds the licence key becomes owner; no link to the paying client |
| Licence key alone, no email | A leaked key is a stolen shop; no recovery path |
| First person to open the app becomes owner (today's demo) | Fine for a demo, unsafe for a sold product |
| **Owner = purchase email, confirmed by code** | Needs internet once at setup, which setup needs anyway |

**Risk noted:** if the client loses access to that email, they also lose the owner account until the subscription
seller changes it. That is the right trade-off, but the seller's support process must exist before launch.

**Verdict:** Best choice. **Status:** Decided by the owner, 2026-10-24.

---

## DEC-003

**Everyone else joins only by invitation** *(rule S12, plan §2.2)*

**Decision.** There is no sign-up page. Cashiers (and any extra admins) get an invitation sent to their own email
by the owner, or by an admin the owner allowed to invite cashiers. Only the owner can invite an admin.

**How it works.**

1. The owner opens **Users → Invite**, enters the person's own email and chooses the role.
2. The system stores the invitation (email, role, inviter, expiry in 48 hours) and emails a link containing a
   random one-time token. The database keeps only a hash of the token (DEC-006).
3. The person opens the link and sets a username and password, or signs in with Google using **that same
   email**.
4. A 6-digit code is emailed to confirm the address. Only then does the account exist, with the role the inviter
   chose. The token can't be used again.

**Why.** A POS account is a key to the cash drawer: a cashier can ring up sales, see receipts and, with a void
request, start moving money. So the question "who decided this person may sell here?" must always have an answer,
and the answer must be the shop's owner, not the person themselves. An invitation answers it by design: the role
is fixed by the inviter before the person ever arrives, the email proves the invite reached the right person, and
nothing the newcomer types can raise their role. There is also nothing for a stranger to attack: with no sign-up
page, there are no fake "pending" accounts, no guessing which usernames exist, and no flood of junk registrations.
Each cashier having their **own** email (not a shared "cashier" account) means every sale, void request and stock
change names a real person, which is what the X/Z readings and the audit log rely on.

**Alternatives checked.**

| Option | Why it is weaker |
|---|---|
| Open sign-up, then the owner approves | Strangers can create accounts and wait in the queue; one careless "approve" tap and they're in. Creates spam and a social-engineering route ("I'm the new hire, approve me") |
| Owner creates the account and tells the cashier a temporary password | The password passes through the owner (by text or paper); the email is never proven, so codes and password resets may go to a typo |
| A shop "join code" anyone in the café can use | The code leaks (posted on a wall, sent in a group chat); anyone with it becomes a cashier |
| One shared cashier account (today's demo) | No way to know who made a sale or a void; one person leaving means changing everyone's password |
| **Invitation to the person's own email** | Needs email for every cashier, which the emailed codes (DEC-004) need anyway |

**Worth adding later (not instead):** real POS systems often let cashiers switch quickly on a shared till with a
short PIN. That is a convenience on top of invitations (the PIN would belong to an invited account on a trusted
device), not a replacement. Recorded as a possible later improvement.

**Verdict:** Best choice. **Status:** Decided by the owner, 2026-10-24.

---

## DEC-004

**An emailed code on every login, unless the device is trusted** *(rule S13, plan §2.4)*

**Decision.** After the password (or Google sign-in), a 6-digit code is sent to the user's email and must be
entered, except on a device the user has trusted (DEC-005).

**How it works.** See plan §2.4: 6 digits from `secrets`, valid 10 minutes, one use, one purpose, 5 wrong tries,
resend once a minute and at most 5 an hour, stored as a keyed hash, compared in constant time.

**Why.** A password alone fails the moment it is seen over a shoulder at the counter, reused from another site, or
guessed. A second step that needs something else, here access to the person's mailbox, means a stolen password is
not enough. Email was chosen because every cashier already has one (it is also how they were invited), there is
nothing to install, and it costs nothing to send.

**Alternatives checked.**

| Option | Strengths | Weaknesses |
|---|---|---|
| **Emailed code** (as requested) | Nothing to install; everyone has email; easy to explain | **Needs internet** to log in on an untrusted device; mail can arrive late or in spam; if the email account itself is hacked, both steps fall together |
| Authenticator-app code (TOTP, e.g. Google Authenticator) | **Works offline** (the code comes from the phone's clock); no mail server; stronger than email | Each user must install an app and scan a QR code once; a lost phone needs backup codes |
| Passkeys / security keys (WebAuthn) | Strongest, can't be phished | Browsers only allow them on `https` or `localhost`, so they **don't work on the café's other devices** over `http://192.168.x.x` in the local package |
| SMS code | Familiar | Costs money per message, needs an SMS provider, weaker (SIM swaps) |
| No second step, password only | Simplest | A seen or guessed password is the whole account |

**Finding: a better option exists for part of the problem.** The emailed code is the right *default*, but the
local package's biggest promise is selling when the internet is down (DEC-012), and email codes can't work then.
Trusted devices and printed backup codes cover it, but an **authenticator app as an optional second step** would
cover it better, because it works with no internet at all, and it's stronger.

**Recommendation for the owner:** keep the emailed code as the default for everyone, and **let each user choose an
authenticator app instead** from their Profile (same 6-digit entry box). The code calculation is about 20 lines of
standard-library Python; keeping the app's key safe needs encryption (DEC-017).

**Verdict:** Better option found (an addition, not a replacement). **Status:** emailed code decided by the owner
2026-10-24; the authenticator-app option **decided by the owner on 2026-10-24**, designed in DEC-017.

---

## DEC-005

**Trusted devices skip only the code, for 30 days (7 for admins and the owner)** *(rule S13, plan §2.5)*

**Decision.** After a correct code, a user may tick "Trust this device". On that browser they then log in with the
password (or Google) only.

**How it works.** A second, long-lived cookie holds 32 random bytes; the database keeps only its hash, the user, a
short device label, and the dates. It counts only for the user who created it. Removing it from Profile, logging out
everywhere, changing the password or being deactivated ends it at once.

**Why.** Asking for a code at every login on the counter laptop would make staff hate the system and look for ways
around it (a shared account, a code read aloud across the room). Trust puts the friction where the risk is: on a new
or unknown device. Skipping only the code, never the password, means a trusted laptop left open still needs the
password. Shorter trust for admins reflects that an admin login can change prices, see every sale and invite people.

**Alternatives checked.** *No trust at all* (secure, but staff work around it); *trust forever* (a lost or sold
laptop stays trusted); *trust by network address* (café Wi-Fi addresses change and anyone on the Wi-Fi would be
trusted); *trust skips the password too* (an unlocked laptop becomes an open account). The chosen middle is the
common practice of banks and email providers.

**Verdict:** Best choice. **Status:** Decided by the owner, 2026-10-24 (the exact days are confirmed with the client).

---

## DEC-006

**Codes and tokens are stored only as keyed hashes** *(rule S14)*

**Decision.** Login codes, invitation tokens, trusted-device tokens and backup codes are stored as HMAC-SHA256
hashes made with the shop's secret key, and checked with `hmac.compare_digest`.

**Why.** If the database file is copied, live codes and tokens in it must be useless. A keyed hash can't be reversed
and can't even be tested against guesses without the secret key, which lives in a separate file (`instance/`).
`compare_digest` takes the same time whether the first or last digit is wrong, so timing can't leak the answer.

**Alternatives checked.** *Plain text* (a database copy reveals working codes). *A slow password hash such as
scrypt* (used for passwords already, but no help for a 6-digit code, whose protection is the 5-try limit, and it
would slow every check). *Plain SHA-256 without a key* (a 6-digit code's million possibilities can be tried in under
a second). Keyed HMAC is the standard answer.

**Verdict:** Best choice. **Status:** Decided, 2026-10-24.

---

## DEC-007

**Receipts are never edited; voids and refunds need an admin** *(rules I8, S15, plan §4.1)*

**Decision.** A completed sale is never changed or deleted. A void or refund is a new record linked to it. A cashier
can only *request* a void; an admin approves it, and refunds are admin-only.

**How it works.** See plan §4.1: a `sale_adjustment` record with requested-by, approved-by, lines, amounts, refund
method and reason; stock and ingredient history lines with reason `void`, `refund` or `waste`; reports show gross,
voids, refunds and net.

**Why.** Editing a receipt would destroy the evidence of what happened: the report for yesterday would silently
change, and the cash count would no longer match anything. Keeping the original and adding a correction is how
accounting has always worked, and it lets the owner see *every* void, by whom and why. The approval step exists
because "ring it up, take the cash, void it" is the classic way money disappears from a till; a second person
signing off removes the opportunity, and the record names both people. Mistakes *before* payment don't need this:
the basket's Undo (plan §4.2) fixes them instantly.

**Alternatives checked.** *Cashier voids alone within a few minutes* (fast, and common in busy POS systems, but it is
exactly the theft pattern above; a remote approval by emailed code keeps it fast when the owner isn't in the shop).
*Delete and re-ring the sale* (no trail). *Edit the receipt with a change log* (the receipt shown to the customer no
longer matches their printout).

**Verdict:** Best choice. **Status:** Decided, 2026-10-24.

---

## DEC-008

**Split `app.py` into blueprints and a `store/` data layer** *(AGENTS.md §2, plan §3.2)*

**Decision.** From v0.25.0, routes are grouped into Flask blueprints (sales, products, ingredients, accounts,
reports) and every database read or write goes through named operations in `store/`.

**Why.** The routes can only work with two different databases if they stop talking to the database directly. With
a store layer, `complete_sale()` is written once per database and every route, test and rule uses it the same way.
`app.py` is also 1,586 lines; the upgrade would roughly double it, past what anyone can review.

**Alternatives checked.** *Keep one file with "if SQLite… else Firestore…" in each route* (every route doubles; one
forgotten branch oversells on one database only). *Only support SQL, so no layer is needed* (see DEC-014; the layer
is still worth it for testing and for the size of `app.py`). *Use an existing multi-database library* (none covers
both SQL and Firestore with transactions).

**Verdict:** Best choice. **Status:** Decided by the owner, 2026-10-24.

---

## DEC-009

**Stock rule I1 states the goal, not the SQL**

**Why.** The old rule named one SQL statement; Firestore has no SQL, so the rule would have been either broken or
ignored. Stating the goal (check and change in one atomic step, roll back all or nothing) keeps the protection that
fixed DEF-13 and DEF-48 on both databases, and extends it to voids, refunds and counts. *Alternative:* two separate
rules per database (harder to keep in step). **Verdict:** Best choice. **Status:** Decided, 2026-10-24.

---

## DEC-010

**Database changes become Alembic migrations** *(rule I5)*

**Why.** `NEW_COLUMNS` can only add columns. The upgrade changes types (money to centavos, times to UTC) and adds
tables; doing that by hand on clients' databases is how data gets lost. Alembic (through Flask-Migrate) is the
standard tool for SQLAlchemy: each change is a numbered, tested script that can also be undone. *Alternatives:*
hand-written SQL scripts (no ordering or record of what ran), or "export, recreate, import" on every upgrade (slow,
risky for a shop mid-week). Firestore has no fixed columns, so its data changes are small numbered scripts in the
same folder. **Verdict:** Best choice. **Status:** Decided, 2026-10-24.

---

## DEC-011

**The packages approved for the upgrade** *(rule D1)*

**Decision and why, per package.**

| Package | Needed for | Alternatives checked | Verdict |
|---|---|---|---|
| `Flask-Migrate` + `alembic` | Migrations (DEC-010) | Hand-written SQL | Best choice |
| `waitress` | A real web server on Windows | `gunicorn` (doesn't run on Windows); Flask's development server (not meant for real use) | Best choice |
| `Authlib` + `requests` | Google sign-in with state, nonce and PKCE handled correctly | `google-auth` plus a hand-written OAuth flow (more of our own security code to get wrong); `Flask-Dance` (simpler, but Authlib is the more general OpenID Connect library and also covers the subscription website later) | Best choice |
| `cryptography` | Encrypting authenticator keys (DEC-017) | Home-made encryption from `hashlib` (never: hand-rolled cryptography is where systems break); it comes with Authlib anyway | Best choice |
| `segno` | The authenticator QR code (DEC-017) | `qrcode` + Pillow; a JavaScript library; an online QR service | Best choice |
| `psycopg` | The cloud package's PostgreSQL connection (DEC-014) | `psycopg2` (older generation of the same driver); `pg8000` (pure Python, slower, less used with SQLAlchemy) | Best choice |
| `google-cloud-firestore` | The optional Firebase package | `firebase-admin` (wraps the same library and adds more than we need) | Acceptable, and only when a client on Firebase asks (DEC-014) |

**Cost noted:** these bring further packages with them (Firestore alone brings `grpcio`, `protobuf`, `google-auth`),
which is why each is added only in the version that first uses it, pinned, and only to the install profile that
needs it. **Verdict:** Acceptable overall. **Status:** Decided by the owner, 2026-10-24.

---

## DEC-012

**The offline promise covers selling in the local package** *(rule D2)*

**Why.** The original promise (the whole system works offline) can't survive Google sign-in, emailed codes or a
cloud database. Rather than drop it, it was narrowed to what the café actually needs when the Wi-Fi drops: keep
selling at the counter. Trusted devices log in with the password only, and printed backup codes stand in for email.
The page-files part of the rule (nothing loaded from a CDN) is unchanged. *Alternatives:* drop the promise (the café
loses sales every outage); refuse every online feature (the client asked for them). **Verdict:** Best choice (made
stronger still by the authenticator option in DEC-004). **Status:** Decided, 2026-10-24.

---

## DEC-013

**Browser tests automated with Playwright from v1.0.0** *(rule T4)*

**Why.** Two install packages times every page, theme and screen width is more clicking than anyone will do
reliably before each release. Playwright is what the earlier hand-run browser tests already used, runs headless in
GitHub Actions, and stays in `requirements/dev.txt` so it never reaches a shop's computer. *Alternatives:* Selenium
(slower, flakier, more setup); keep testing by hand (doesn't scale). **Verdict:** Best choice. **Status:** Decided,
2026-10-24.

---

## DEC-014

**One codebase with local and cloud packages; Firestore as the cloud database** *(plan §3)*

**Decision as requested.** One codebase, a setting that picks the database, and two install profiles: local
(SQLite) and cloud (Firestore). Clients with an existing SQL server can point the local package at it.

**How it works.** See plan §3: a `store/` layer (DEC-008) with `SqlStore` (SQLite, PostgreSQL, MySQL) and
`FirestoreStore`; Firestore transactions for stock, "claim" documents for unique values, a counter document for
receipt numbers, and daily summary documents for reports.

**Why one codebase.** Two copies of the program would drift apart; every fix would have to be made twice and would
sometimes be forgotten in one. One codebase with two profiles is clearly right (*Best choice* for that part).

**What PostgreSQL is, in plain words.** PostgreSQL ("Postgres") is a free, open-source database that has been
developed since the 1980s and is one of the most widely used databases in the world. It is the **same kind** of
database as the SQLite file the system uses today: data lives in tables with columns, and programs talk to it in SQL.
The difference is that SQLite is a single file read by one program on one computer, while PostgreSQL runs as a
**server** that many tills, branches and computers can use at the same time, with many people writing at once.
"Managed" PostgreSQL means a company runs that server for you (keeps it up, patched and backed up): Google Cloud SQL,
Supabase, Neon and Amazon RDS all offer it, several with a free starting tier. The system already reaches the
database through SQLAlchemy, which speaks PostgreSQL as well as SQLite, so switching is mainly a change of **one
setting** (the database address) plus PostgreSQL's driver package `psycopg`.

**Check of the cloud database choice.** This check found a **better option** for most clients:

| | Firestore | Managed PostgreSQL (e.g. Google Cloud SQL, Supabase, Neon) |
|---|---|---|
| Fits the data | The data is relational (sales → items → products → recipes → ingredients). Firestore is a document store, so joins, unique values and sums all need workarounds | Exactly the same tables as today |
| New code to write | A whole second store (`FirestoreStore`), claim documents, counters, daily summaries, emulator tests | **Almost none**: `SqlStore` already works; only a different connection address |
| Stock safety (I1) | Transactions with retries; correct but new code to test | The same conditional update already proven by 20-cashier tests |
| Reports | Must be pre-summed to keep the bill down | Plain `SUM`, as today |
| Cost | Pay per read and write; reports can get expensive without the summaries | Fixed monthly price or a free tier |
| Offline | Needs internet to sell | Needs internet to sell (same) |
| When it wins | The client **already** runs Firebase, or wants Firebase's other services (mobile app, push notifications) | Every other cloud case |

**Recommendation for the owner:** offer the cloud package with **managed PostgreSQL as the default**, delivered in
Phase 2 with almost no extra work, and build `FirestoreStore` (Phase 5) **only when a client who already uses
Firebase asks for it**. The client conversation and comparison table in plan §3.6 stay the same, with one more row.
Firestore remains fully planned; it just stops being built on speculation.

**Verdict:** One codebase: Best choice. Firestore as *the* cloud option: **Better option found**, now applied.

**Owner's decision (2026-10-24).** "Firestore (Firebase) should be optional for clients already using its services,
but never first." So the cloud package uses managed PostgreSQL (v0.37.0, driver `psycopg`), and the Firebase
package (v0.39.0) is built only when such a client asks. *Check of this decision:* it is the recommendation above,
and it also removes the riskiest work (a second store) from the critical path. **Best choice.**

**Status:** Decided by the owner, 2026-10-24.

---

## DEC-015

**Licence checked daily with a 30-day grace period** *(plan §2.11)*

**Why.** The subscription has to be enforced somehow, but a café must never lose a sale or its records because of a
billing hiccup or a week without internet. A daily background check notices a lapsed subscription soon; 30 days of
grace covers long outages and late payments; the day's selling always finishes; and reports and the data export stay
open even after expiry, because the shop's sales records belong to the shop (and the Data Privacy Act gives people
rights over their personal data in them). The licence answer is signed, so editing the database can't fake it.
*Alternatives:* check at every start-up (a restart during an outage would stop the shop); no check (the product
can't be sold as a subscription); hard lock-out on expiry (holds the client's data hostage, and would sour the
relationship). **Verdict:** Best choice. **Status:** Proposed, 2026-10-24 (the grace length is confirmed with the
client).

---

## DEC-016

**The contract check blocks Google and cloud key files** *(rule P1)*

**Why.** A Google sign-in secret or a cloud service-account key pushed to GitHub gives anyone full access, and
bots scan GitHub for them within minutes. Adding the file patterns to `.gitignore` *and* to
`tests/check_contract.py` means a key is refused even if someone forces it past `.gitignore`. *Alternative:* rely on
review alone (one tired reviewer is enough to leak a key). **Verdict:** Best choice. **Status:** Decided,
2026-10-24.

---

## DEC-017

**Authenticator apps as a second step, and how they are kept safe** *(rules S13, S14; plan §2.4)*

**Decision.** Besides the emailed code, each user may switch their second step to an **authenticator app** (Google
Authenticator, Microsoft Authenticator, or any app that follows the TOTP standard). The emailed code stays the default.

**How it works.**

1. *Turning it on (Profile → Sign-in method).* The user must already be fully logged in, types their password again,
   and is shown a QR code (and the same key as text, for typing in by hand). They scan it, then type the 6-digit code
   the app shows. Only if that code is right does the switch happen, so a mis-scanned key can't lock anyone out. New
   backup codes are shown at the same moment, and an email tells the user "Your sign-in method changed".
2. *Logging in.* Password (or Google), then the 6-digit code from the app instead of one from email. The code
   changes every 30 seconds and is worked out on the phone from the shared key and the clock, so **no internet is
   needed** on either side.
3. *Turning it off or changing phones.* Password plus a current app code (or a backup code). Again an email is sent.
4. *Lost phone.* A backup code, or the owner / an admin resets the user's second step back to email; the reset is
   written in the audit log and the user is emailed. The **owner's** own reset goes through the subscription
   seller (DEC-002), so no admin can take over the owner account this way.

**Security measures, and what each one stops.**

| Measure | Stops |
|---|---|
| The standard TOTP method (RFC 6238): 6 digits, 30 seconds, HMAC-SHA1, as every authenticator app expects | Home-made code schemes, which are where mistakes hide |
| A 160-bit random key per user from `secrets` | Guessing the key |
| The key stored **encrypted** (Fernet from the `cryptography` package), with its own key file in `instance/`, never in plain text | A copied database giving working codes (the same promise as DEC-006). The key can't be *hashed* like other codes, because the server must work out the current code from it |
| Codes accepted only for the current 30-second step and one step either side (for a phone clock a little off) | Old codes being reused later |
| The last accepted step is remembered and **the same or an earlier step is refused** | Someone watching the screen and replaying the code within the same 30 seconds |
| The same 5-wrong-tries limit and wait as the login (S10), stored in the database | Trying all million codes |
| `hmac.compare_digest` for the comparison | Timing leaks |
| Password **and** a current code to turn it off or change it; an email on every change | A thief at an unlocked till quietly moving the account to their own phone |
| The owner's second step is reset only through the subscription seller | An admin taking over the owner account |
| Trusted devices (DEC-005) still skip the code; nothing else changes | — |

**Alternatives checked.**

| Option | Verdict |
|---|---|
| **TOTP authenticator app** | Works offline, free, works on any phone, standard. Chosen |
| Passkeys / security keys (WebAuthn) | Strongest (can't be phished), but browsers allow them only on `https` or `localhost`, so the café's other devices on `http://192.168.x.x` can't use them in the local package. Worth adding **when the shop runs on HTTPS** (cloud package), as a third choice |
| Push approval apps ("Is this you? Yes / No") | Needs a paid service and internet; people tap "Yes" out of habit |
| SMS codes | Costs per message, needs internet and a provider, weaker (SIM swaps) |
| Store the key in plain text (many small apps do) | Simpler, but breaks the promise that a copied database gives no working codes. Rejected |

**Honest limits.** No second step makes a system unbreakable. One trick works against both emailed and app codes: a
fake login page that passes the password and code on to the real site within seconds. Inside a café's own network
this is unlikely, and only passkeys fully stop it (see above). The password, the code, the login limit, trusted
devices that expire and the change alerts together make an account very hard to take over, which is the realistic
goal.

**Packages.** The TOTP calculation itself needs only Python's own `hmac`, `struct`, `time` and `base64`.
Encrypting the key needs `cryptography`, which Authlib (DEC-011) brings with it anyway, so it is approved for
v0.28.0. Drawing the QR code needs `segno`; without it the user types a 32-character key into the app by hand,
which works but invites typing mistakes. **Approved by the owner on 2026-10-24** ("Include QR").

**How the QR code is kept safe.** It contains the secret key, so: it is drawn on the server as an SVG and placed in
the page as a `data:` image (no `|safe` and no file written to disk, rule S11); the page is sent with
`Cache-Control: no-store` so the browser doesn't keep a copy; and it is shown only during set-up, never again
(changing phones means setting up a new key). *Alternatives checked for drawing it:* `qrcode` (needs the Pillow
image package as well), a JavaScript QR library in `static/vendor/` (works, but puts the secret key into page
scripts), an online QR service (sends the secret to a stranger; never). `segno` is pure Python with no further
packages: **Best choice.**

**Verdict:** Best choice. **Status:** Decided by the owner, 2026-10-24 ("allow users to choose their own
authenticators"; QR code included, to be tested when v0.28.0 is built).

---

## DEC-018

**Keep `main` at the defended version until after Tuesday's defense** *(plan §6)*

**Decision.** Until the final defense on Tuesday 2026-10-27, only documentation is merged into `main`. The first
upgrade versions are built on their own branches with pull requests, tested on Sunday evening (2026-10-25), and
merged on Wednesday, after the defense.

**How it works.** The defended system is v0.21.2: its tag, the submission zip and the final report all describe it.
Each new version (starting with Phase 1 of the plan) gets its branch, its tests and its pull request as usual, and
GitHub's checks run on it, so Sunday's testing covers exactly what will be merged. Nothing on those branches can
change what is shown on Tuesday.

**Why.** A defense is judged on the system as submitted, with its report, test results and defect list. Merging new
code two days before would mean the demo laptop, the report and the tag no longer agree, and any new defect would
surface in front of the panel with no time to fix it under the stabilization rule (C2). Building on branches keeps
all the progress (nothing waits idle), gives Sunday's tests something real to check, and costs only one merge day.

**Alternatives checked.**

| Option | Verdict |
|---|---|
| Merge each version as soon as it passes | Fastest, but the report and demo drift from what is defended, and a late defect shows up on Tuesday |
| Stop all work until after the defense | Safest, but wastes the weekend and leaves nothing to test on Sunday |
| **Build on branches now, test Sunday, merge Wednesday** | Progress plus a stable defense. Chosen |

**Verdict:** Best choice. **Status:** Decided, 2026-10-24 (owner: "We will run tests by Sunday evening. Tuesday is
the final defense. Proceed with the plan.").

---

## DEC-019

**A crash shows a friendly page; details only in the log** *(v0.21.3, DEF-61, audit A11)*

**How it works.** Flask calls `server_error()` for any unexpected error. It first undoes the unfinished database work (`db.session.rollback()`), so the next request doesn't inherit a broken transaction; then it writes the error and its traceback to the server log; then it shows `500.html` inside the normal layout, with the advice "Nothing was saved. Please go back and try again." If drawing that page fails too (for example, the database itself is down), a plain two-line message is sent instead.

**Why.** The plain page tells a cashier nothing, and leaving the database session half-done can make the *next* page fail too. Showing details in the browser would help an attacker (file paths, library versions), so they go to the log, where the owner or developer can read them. The answer stays a real 500 so logs and monitoring still see the failure. Nothing can be "half saved" anyway, because every sale is one transaction (I2).

**Alternatives checked.** *Show the error details* (helps attackers, scares staff). *Redirect to Home with a flash message* (hides the failure from logs and loses the page the user was on). *Debug mode's error page* (can run code; forbidden by S4). **Verdict:** Best choice. **Status:** Decided, 2026-10-24.

---

## DEC-020

**Unknown usernames check a dummy password hash** *(v0.21.4, DEF-62, audit A8)*

**How it works.** At start-up the app hashes a random password nobody knows with the same slow method as real passwords (scrypt) and keeps the hash as `DUMMY_PASSWORD_HASH`. When someone logs in with a username that doesn't exist, the typed password is checked against that hash anyway, and the answer is always "no". Both cases now do one slow check and show the same message.

**Why.** The message already didn't reveal whether the username or the password was wrong, but the *time* did: about 100 ms for a real user (scrypt is slow on purpose) and about 1 ms for an unknown one. Measuring that lets someone list which usernames exist, which is the first half of guessing a login. Once the system has many invited cashiers (DEC-003), that list matters more than today with two accounts. One extra hash for wrong usernames costs nothing a real user notices.

**Alternatives checked.** *Add a fixed delay for unknown users* (a fixed number never matches the real hash time on every computer, so the difference still shows). *A random delay* (averages out over many tries). *Leave it* (the audit marked it Low, but it is a five-line fix and gets more important with invitations). Checking a real hash of the same kind is the standard fix. **Verdict:** Best choice. **Status:** Decided, 2026-10-24.

---

## DEC-021

**Demo menu: one product per drink, sold Hot or Iced** *(v0.21.5, DEF-63, audit R10)*

**How it works.** The built-in menu (`DEFAULT_MENU` in `seed_demo_data.py`) now has 8 drinks (Americano, Cafe Latte, Cappuccino, Spanish Latte, Caramel Macchiato, Mocha, Matcha Latte, Chocolate), each with **+ Hot** and **+ Iced** on its tile. The servings cost the same. What makes them different is their own recipe: Hot adds a hot cup; Iced adds an iced cup and 150 g of ice, so the stock bars and the "Uses N ingredients" panel show cups and ice running out. A shop's own `local_demo/menu.json` is unaffected.

**Why.** The demo is what a client, an examiner or a new cashier sees first. With 12oz / 16oz it showed the old design and hid the café's actual Hot / Iced flow (F15, F19): the serving buttons, the cup and ice stock and the colour-coded Hot / Iced buttons never appeared.

**Alternatives checked.** *Rename 12oz / 16oz to Hot / Iced and keep the "Iced ..." products* (gives nonsense such as "Iced Americano — Hot"). *Keep separate hot and iced products with no servings* (twice as many tiles; the serving feature never shows). *Leave it* (the demo contradicts the report and the café). **Verdict:** Best choice. **Status:** Decided, 2026-10-24. *Note:* the final report's tour screenshots show the old 12oz / 16oz menu; they describe v0.21.2 as defended and stay as they are.

---

## DEC-022

**Shop details live in the database; the "not an official receipt" line is fixed** *(v0.22.0, F21, SR6)*

**Decision.** The shop's name, address, TIN and receipt footer are kept in a one-row `shop_profile` table and edited by an
admin on **Shop details**. The words "This is not an official receipt." are written into the receipt template itself, not
stored as a setting.

**How it works.** The receipt page reads the row (or sensible defaults if it was never saved) and prints the name, the
address, "TIN: …" if set, and the footer. Below them it always prints the notice. The form checks every value on the server
(S7): name required and at most 60 characters, address and footer at most 120, TIN 9 to 14 digits with dashes or spaces
allowed (9 digits plus a 3- or 5-digit branch code). Typed text is shown as text (S11). An older database gets the table at
start-up from `db.create_all()` (I5).

**Why.** Receipts are what customers take home, so they should name the café, and the owner must be able to change that
without a programmer. The notice is the one thing the report rated *Intolerable* (hazard 10): a slip that looks like an
invoice could be mistaken for one, with tax consequences for the café. Making it part of the template, not an option, means no
setting, typo or later admin can remove it; changing it needs a code change, a pull request and a review.

**Alternatives checked.**

| Option | Verdict |
|---|---|
| **A one-row table with typed columns** | Simple, checked on save, backed up and exported with the shop's data, works on any database the store supports. Chosen |
| A general key-value settings table | More flexible, but every value is untyped text and harder to check; nothing else needs it yet |
| `instance/config.toml` (planned for v0.24.0) | Right for technical settings (database, mail), but the owner can't edit it in the app, and it wouldn't travel with an export to the cloud |
| Environment variables | Not something a café owner can change |
| The notice as a setting with "on" by default | One click turns it off; the hazard comes back silently |

**Verdict:** Best choice. **Status:** Decided, 2026-10-24.

---

## DEC-023

**Migrations: one catch-up first migration, a backup before every upgrade** *(v0.23.0, rules I5 and S5)*

**Decision.** Database changes are numbered Alembic scripts in `migrations/versions/` (`0001`, `0002`…), run through
Flask-Migrate. The first one, `0001`, describes the whole v0.22.0 database and *catches up* any older database. At
start-up the app backs the database up and then runs whatever migrations it hasn't had.

**How it works.**

1. `upgrade_database()` (called by `python app.py`, the demo-data script and the tests) looks at the database.
2. If it holds data and a migration is missing, it first copies the file with SQLite's own backup feature to
   `instance/inventory_backup_<date-time>_before_<number>.db`.
3. Alembic runs the missing migrations in order and writes the newest number in a small `alembic_version` table.
4. Migration `0001` only creates what is missing: every table in an empty database; in a database made before
   v0.23.0, the missing tables and the columns the old `NEW_COLUMNS` list used to add (with the same first-time
   fixes for ingredient groups and full levels). So a database from any earlier version keeps all its data.
5. The v0.17.1 clean-up of recipe lines from deleted products still runs at every start, as before.

**Why.** `NEW_COLUMNS` could only add columns. The next versions change types (money to whole centavos, times to
UTC) and add tables for sign-in, which needs real, ordered, testable scripts, the standard way a SQLAlchemy project
changes a live database. Starting with one catch-up migration (instead of pretending every past version had its own
script) is the usual way to adopt Alembic on a database that already exists. The automatic backup turns "the upgrade
went wrong" from lost data into restoring one file.

**Details decided along the way (each checked).**

| Detail | Choice | Why, and the alternative rejected |
|---|---|---|
| Numbering | Readable `0001`, `0002`… instead of Alembic's random ids | Easier to read in a report and to talk about; Alembic accepts any id (`--rev-id`) |
| First migration on old databases | Catch up (create what's missing) | "Stamp" the old database as up to date without checking: a database from v0.12 would be missing columns forever |
| Undoing `0001` | Refused with a message | Its automatic undo would drop every table, i.e. delete the shop's data; restoring a backup is the safe way back |
| Backups | Only when there is data *and* a migration to run | A backup on every start would fill the disk; an empty database has nothing to lose |
| Logging | `fileConfig(..., disable_existing_loggers=False)` in `env.py` | Alembic's default switches off loggers that already exist, which would hide crash details (DEF-61); found by TC-28.7 |
| Every-start clean-up of orphan recipe lines | Kept | A migration runs once; v0.17.1's guarantee ran at every start, so dropping it would have been a silent behaviour change (caught by `test_ingredients.py`) |
| Package versions | alembic 1.20.0, not the newest 1.20.1 | 1.20.1 was two days old; versions are only used once they have been out for about two weeks |
| Development environment | A separate venv outside the project and OneDrive (`C:\Users\axdr9\.venvs\inventory-pos-dev`) | Keeps the demo laptop's `venv` exactly as defended until the merge (DEC-018) |

**Alternatives checked for the whole approach.** *Keep `NEW_COLUMNS`* (can't change types or rename). *Plain Alembic
without Flask-Migrate* (works, but more set-up and no `flask db` commands). *Hand-written SQL scripts with our own
version table* (re-inventing Alembic, with fewer checks). *Recreate the database from an export on every upgrade*
(slow and risky in a busy week). **Verdict:** Best choice. **Status:** Decided, 2026-10-24.

---

## DEC-024

**Times stored in UTC; shown in the shop's fixed UTC+8** *(v0.23.1, DEF-67, audit R1)*

**How it works.** Every new time (sales, logins, ingredient changes, the login limit) is stamped with `utc_now()`.
Pages pass times through the `shop_time` filter, and the report and Home turn "a day" on the shop's clock into a UTC
range with `shop_day_start_utc()`. Migration `0002` converted the times already stored, from this computer's local
time to UTC; undoing it converts them back.

**Why.** Until now each time meant "whatever the computer's clock said". On the shop's laptop that happened to be
right, but a cloud server (DEC-014) runs on UTC, so the same code there would have put a 7 AM sale in the previous
day's report. Storing one unambiguous time and converting only for people is the standard practice, and it has to
happen before any cloud package exists.

**Details checked.**

| Detail | Choice | Alternative rejected |
|---|---|---|
| Shop time zone | A fixed UTC+8 (`timezone(timedelta(hours=8), 'PHT')`) | `zoneinfo("Asia/Manila")`: correct too, but Windows has no time-zone database, so it needs the `tzdata` package. The Philippines has had no daylight saving since 1978, so a fixed offset is exact. A shop in a country with daylight saving would need `tzdata` (noted for later) |
| Converting old times | This computer's own time zone | Always subtract 8 hours: wrong if the laptop was ever set to another zone. The old times were written by this computer's clock, so its own setting is the faithful inverse. The database is upgraded where it lives (at start-up on the shop's laptop); moving to the cloud happens after, through export/import |
| Stored form | UTC without a zone label | Zone-aware columns: SQLite has none, and labels would differ between databases |
| Backup file names | Still the computer's local time | They are read by a person in File Explorer on that computer |
| Tests | Fixed dates for the conversions; three older tests moved to the helpers | Relying on the test machine's zone: GitHub runs on UTC, where local and UTC are the same and a mistake would hide (one did: TC-27.8 only failed on the UTC+8 laptop) |

**Verdict:** Best choice. **Status:** Decided, 2026-10-24.

---

## DEC-025

**Money: whole centavos in the database, exact Decimal pesos in Python** *(v0.23.2, DEF-68, audit R5)*

**How it works.** A new column type, `Money` (in `models.py`), is used for every price and total: product and add-on
prices, sale totals, cash received, change and receipt-line prices. When a value is saved it is turned into an exact
`Decimal`, rounded once to the centavo (half up: 0.125 → 0.13) and stored as a whole number of centavos (₱75.50 →
7550). When it is read back, Python gets `Decimal('75.50')`. Forms still type pesos, pages still show pesos, and the
code still says `product.price`; only the storage and the arithmetic changed. Migration `0003` multiplied every stored
amount by 100 and rounded it *before* changing the column to INTEGER (changing the type alone would cut 75.50 to 75).

**Why.** A float can't hold most centavo amounts exactly (0.1 is really 0.1000000000000000055…). Rounding each result
hid that for single sums, but long sums drift, and one real case showed on a receipt: ₱0.125 was displayed as ₱0.12 per
item but ₱0.38 for three. Shops and accountants expect every receipt to add up to the centavo, and the cloud package
(DEC-014) will add up thousands of sales. Whole centavos are what payment systems use; doing it now, before the store
layer and the cloud package, means they are built on exact money from the start.

**Alternatives checked.**

| Option | Verdict |
|---|---|
| **`Money` type: INTEGER centavos stored, `Decimal` pesos in Python** | Exact storage *and* exact arithmetic, the same on SQLite and PostgreSQL, and almost no code had to change. Chosen |
| Integer centavos everywhere in the code too | Equally exact, but every calculation, form, template and about 15 test files would change in one version; much more risk for no extra exactness |
| SQLAlchemy `Numeric(10, 2)` | On SQLite it is still stored as a floating-point number (SQLite has no exact decimal type), so it doesn't fix the problem where the shop runs |
| Keep floats and round more carefully | Treats the symptom; the receipt case shows rounding in one place and not another still breaks |

**Details checked.** Rounding is *half up* (what a cashier expects: ₱0.125 → ₱0.13), not Python's default
"half to even". Amounts typed in forms are still checked as numbers first (limits, `nan`, `inf`), then converted
to `Decimal` at the boundary (`to_money()`), so a float never meets a `Decimal` in a sum. Tested on a copy of the
owner's database: all 58 receipts, 120 lines and 12 prices equal to the centavo before and after.

**Verdict:** Best choice. **Status:** Decided, 2026-10-24.

---

## DEC-026

**A shop's copy: set up once, settings in `config.toml`, served by waitress** *(v0.24.0, F22, audit R3 and A5)*

**How it works.**

1. `setup_shop.py` asks (or reads an answers file): may phones and other computers use the system; which port; the
   shop's details; the owner's admin username and password (typed twice, hidden). Every answer is checked *before*
   anything is written, so a wrong one changes nothing.
2. It writes `instance/config.toml` (server host and port, database address; never a password), keeping the old one as
   `config.toml.bak`, then brings the database up to date (with the v0.23.0 backup), saves the shop's details and
   creates the admin, unless that username already exists.
3. `start_shop.bat` runs `serve.py`, which checks the settings, upgrades the database and starts **waitress**, printing
   the address for this computer and, if allowed, for phones on the shop's network.

**Why.** Until now a shop's copy was the demo: Flask's development server (which says itself it isn't for real use),
the public demo passwords, and settings only in code. A café needs a real server that handles several devices, one
place for settings that a person can read, and an install that can't accidentally keep `admin123` as the owner's password.

**Details checked.**

| Detail | Choice | Alternatives rejected |
|---|---|---|
| Web server | waitress 3.0.2 (pure Python, no other packages, made for Windows) | gunicorn and uWSGI (don't run on Windows); Flask's development server (not for real use) |
| Listening | This computer only unless the owner says yes to other devices | Always open to the network (exposes the system on every Wi-Fi the laptop joins); always closed (phones and tablets couldn't be used) |
| Allowed hosts | Only `127.0.0.1` or `0.0.0.0` | Any address: typing mistakes could leave it unreachable, and there's no need for more on a shop's laptop |
| Settings file | `instance/config.toml`, read with Python's own `tomllib` | `.env` (needs `python-dotenv`), JSON (no comments for a person editing it), the database (it can't hold its own address) |
| Shop details | Still in the database (DEC-022), entered by the setup | Duplicating them in the config file (two places to keep in step) |
| First account | The owner's own admin, password at least 8 characters and not the username | The demo accounts (public passwords, audit A5) |
| Automated installs | An answers file (`--answers`), read with `utf-8-sig` | Command-line arguments (the password would stay in the shell's history); plain `utf-8` refused files saved by PowerShell 5 or older Notepad (found in the end-to-end trial, TC-31.10) |
| Requirements | `requirements/local.txt`, with `requirements.txt` pointing to it (`-r`) | Moving everyone to new commands; empty `cloud.txt` and `dev.txt` before anything goes in them |
| `.bat` line endings | Forced to CRLF with `.gitattributes` | Leaving it to Git's settings on each computer (a `.bat` with Unix line endings can misbehave) |

**Honest limits.** The interactive questions can't be automated (the password prompt reads the keyboard), so they
are a hand test for Sunday (TC-31.12). Windows Firewall may ask once whether Python may use the network; the README
says to allow it on private networks only. The owner role, the owner's email and the licence come later (v0.27.0,
v0.38.0); until then the setup creates an ordinary admin.

**Verdict:** Best choice. **Status:** Decided, 2026-10-24.

---

## DEC-027

**Six blueprints, `common.py`, and `store/` for every database change** *(v0.25.0, rules I1 and the AGENTS.md §2 note)*

**How it works.** The pages moved out of `app.py` into Flask *blueprints*, one per part of the system, named after the
subsystems in the report's high-level architecture: `accounts`, `catalog`, `ingredients`, `sales`, `reports`, `shop`.
Rules every part needs (limits, `find_by_id`, `admin_required`, money and the shop's clock, picture files) are in
`common.py`. Every change to the database is a function in `store/`: `record_sale()` (the all-or-nothing sale),
`restock()`, `count()`, products, options, recipes, logins, passwords, pictures and shop details; the stock
calculations (`Recipes`, `can_make`, `stock_levels`…) are in `store/stock.py`. `app.py` only starts the app and
re-exports the old names, so `seed_demo_data.py`, `setup_shop.py`, the migrations and the tests keep working.

**Why.** `app.py` was 1,722 lines and the upgrade would roughly double it (DEC-008). With every database change in one
place, the stock rule I1 can be *checked by a program* instead of by review: `check_contract.py` now fails if a page
writes to the database itself. The code was moved, not rewritten: the same steps, messages and checks, which is why
26 of the 27 test files pass without a single change.

**Details checked.**

| Detail | Choice | Alternative rejected |
|---|---|---|
| How to split | By part of the system (matches the report's architecture) | By kind of code (all forms in one file, all queries in another): a change to selling would touch many files |
| Moving code | Copied with only the necessary edits (page names, `store` calls, `current_app`) | Rewriting while moving: any behaviour change would be hidden inside a huge diff |
| Page names | `part.page` (Flask's blueprint naming), all templates updated | Keeping one flat list of names by registering routes on `app` from each file: not real blueprints, and the parts can't be tested or moved separately |
| Proof of "no visible change" | The unchanged suite + a page-by-page walk in Edge | Writing new tests for the move (they would test the new code against itself) |
| The one test edit | `test_hardening.py` now swaps `check_password_hash` in `blueprints/accounts.py`, where `login()` lives | Making `login()` look the function up through `app`: hiding the real location to keep a test line unchanged |

**Open: reads.** The AGENTS.md §2 note (2026-10-24) says "all database access in `store/`". v0.25.0 moves every
**write** and the shared stock reads; the pages still read with simple queries (lists, look-ups, the report). Moving
every read too would double the change for no benefit today: SQLite and PostgreSQL both use this same SQL code, and a
second kind of store (Firestore) is built only for a client already on Firebase (DEC-014). The reads would move then.
**The owner decides** (C8): either move the reads in a follow-up version, or reword the note to "every database change
in `store/`; reads move when a second store is built".

**Owner's decision (2026-10-24):** reword the note: "every database change goes through `store/`; reads move there
when a second kind of store is built." Applied in AGENTS.md §2, with the old wording kept in an *Overridden* note.
*Check of this decision:* it matches the recommendation above and keeps the rule true of the code today; the I1
contract check enforces the part that protects the data (writes). **Best choice.**

**Verdict:** Best choice. **Status:** Decided, 2026-10-24.

---

## DEC-028

**Wrong passwords counted in the database; Change password limited too; email sent with `smtplib`**
*(v0.26.0, F23; audit A7 and R2; rules S10, P1, D1, D2)*

**How it works.**

1. **The `login_attempt` table** (migration 0004) replaces the list of wrong passwords that lived in memory. Each
   row is one try: a *key* and a time. The key is a keyed hash (HMAC-SHA256 with the secret key) of what is being
   limited, for example `login|cashier|192.168.1.20`, so the table never holds anything a person typed.
2. **A try is recorded first, then counted.** Before a password is checked, a row is added and the rows for that key
   in the last 5 minutes are counted. If there are more than 5, the try is refused ("wait 5 minutes") and its row is
   removed again, so waiting really ends the lock. A correct password removes every row for that key (the count
   starts again, as before). Rows older than 5 minutes are deleted at every try.
3. **Change password (audit A7)** uses the same limit with the key `password|<user id>`: after 5 wrong *current*
   passwords, the form refuses for 5 minutes, whatever the password typed.
4. **Email** is sent by `mail.py` with Python's own `smtplib`. The settings are the `[mail]` part of
   `instance/config.toml` (server, port, `starttls` or `ssl`, username, password, sender address), written by
   `setup_shop.py`; the `MAIL_PASSWORD` environment variable wins over the file, as `DATABASE_URL` does.
   Every connection is encrypted and the server's certificate is checked. Messages are plain text, sent from the
   shop's name. Any failure becomes one plain sentence (C6) and the details go to the server log, never the password.
5. **Settings → Email** (admin) shows the settings (never the password) and sends a test message, so the owner
   knows mail works before v0.27.0 and v0.28.0 start relying on it for invitations and codes.

**Why.** The limit in memory was forgotten whenever the app restarted (a crash, or simply closing `start_shop.bat`),
and each server process kept its own list (audit R2). Codes, invitations and the cloud package all need limits that
hold however the app is run. Change password checked the current password with no limit at all, so a person with a
stolen login could guess it there as fast as they liked (A7); now that form is no weaker than the login page. Email
comes now, alone, because the next two versions depend on it and a mail problem is easier to find in a version
that does nothing else with it.

**Details checked.**

| Detail | Choice | Alternatives rejected |
|---|---|---|
| Where tries are kept | A database table | In memory (forgotten on restart, one list per process: R2); columns on `user` like `failed_count` (no row for unknown usernames, and a per-user lock lets a stranger lock the real user out) |
| What the key holds | A keyed hash of username + computer | The text typed: people sometimes type their **password** into the username box, and a database copy would show it (in memory it vanished; in a table it stays) |
| Counting | Record first, then count | Count, then record: two tries at the same moment both see "4" and both get checked, so the limit leaks under load; the I1 idea (check and change in one step) applied here |
| A refused try | Its row is removed | Kept: every refused try would extend the lock, and a script could keep the owner locked out forever |
| Change password key | Per user | Per user and computer like login: a thief only has to change Wi-Fi to get 5 more guesses; the only person who can trip it is someone already logged in as that user |
| Change password after the limit | Wait 5 minutes, like login | Logging the browser out: stronger against a thief, but logs out a cashier who mistypes; the S13 code (v0.28.0) is the real answer to stolen logins |
| Mail package | `smtplib` (standard library; DEC-011) | Flask-Mail (a package not approved); a mail service's web API (ties the shop to one provider and needs `requests`) |
| Encryption | `starttls` (port 587) or `ssl` (465) only, certificate checked | Plain SMTP: the mail password would cross the network readable |
| Where the mail password lives | `instance/config.toml` (rule P1 names it), or `MAIL_PASSWORD` | A file of its own (a second place to look after); a web settings form (the web server would rewrite its own settings file, and the password would travel through a page) |
| Test messages in tests | The tests replace `smtplib`'s two connection classes with a fake that records what was sent | A real mailbox (needs the internet, rule T3); a small fake SMTP server (can't test the encrypted connection without certificates) |

**Honest limits.** The test button has no limit of its own: only an admin can use it, the text is fixed, and the
mail provider's daily cap applies; invitation and code mail get their own limits in v0.27.0 and v0.28.0. Behind a
hosting proxy every visitor may share one address (the rest of R2); that is set up with the cloud package (v0.37.0).
The mail password is stored as typed, because the server must hand it to the mail provider; it sits next to the
secret key in `instance/`, which never leaves the computer.

**Verdict:** Best choice. **Status:** Decided, 2026-10-24.

---

## DEC-029

**The owner, the Users page, invitations, emailed codes, forgotten passwords and the audit log**
*(v0.27.0, F24; rules S1, S12, S14, S15; DEC-002, DEC-003, DEC-006; audit A5, R9)*

**Owner's decisions (2026-10-24), asked before building (C8):**

1. **The owner before the licence exists.** Rule S12 ties the owner to the subscription purchase email, but the
   licence check comes in v0.38.0. Until then `setup_shop.py` asks for the owner's username, **email** and password
   (on an older database it turns an existing admin into the owner), and the owner confirms that email with a code
   on Profile. v0.38.0 replaces the typed email with the purchase email. S12 carries a dated note saying so.
2. **Three new public pages** in rule S1: `/signup/<token>` (only with a valid invitation), `/forgot-password` and
   `/forgot-password/code`.

**How it works.**

1. **Roles.** `owner`, `admin`, `cashier`. The owner counts as an admin everywhere (`User.is_admin`). The database
   allows **one** owner (a unique index on `role` where it is `owner`). Nobody can change, switch off or demote the
   owner from the Users page, including the owner.
2. **Who may do what on Users** (`/admin/users`, every admin may open it):

   | Action | Owner | Admin |
   |---|---|---|
   | Invite a cashier | Yes | Only if the owner ticked "may invite" for them |
   | Invite an admin, change a role, give "may invite" | Yes | No (403) |
   | Switch an account off or on, require a new password | Anyone but the owner | Cashiers only |
   | Resend or cancel an invitation | Any | The ones they sent |

   Accounts are **switched off, never deleted**: receipts name their cashier. Switching off ends every login of
   that account at once.
3. **Invitations.** The inviter types the person's own email and the role. The invitation stores the email, role,
   inviter, a 48-hour expiry and a keyed hash of a random token (DEC-006); the email holds the link. Resend makes a
   new token (the old link stops working); cancel ends it. The link opens `/signup/<token>`: the person chooses a
   username and password, a 6-digit code goes to the invited address, and entering it creates the account with
   the inviter's role and logs them in. The invitation is marked used in one conditional step, so it can't make two
   accounts.
4. **Emailed codes** (table `email_code`), the rules of plan §2.4 and S14: 6 digits from `secrets`, stored as a keyed
   hash bound to its purpose and address, 10 minutes, one use, one purpose (`signup`, `reset`, `email`). Each wrong
   try is counted *before* the check, in one conditional update, and the 5th wrong try cancels the code. A new code
   cancels the older ones for the same purpose and address. Sending is limited to one a minute and 5 an hour per
   address (the `login_attempt` table from DEC-028).
5. **Forgotten password.** `/forgot-password` asks for the email and always answers the same way ("If an account
   uses that address, we sent it a code"). Only an active account with a **confirmed** email gets a code. The code
   page takes the code and the new password twice; success ends every login of that account. The page is limited to
   10 requests an hour per computer.
6. **Email on Profile.** Everyone sees their email and whether it is confirmed. Cashiers and admins can change it
   (current password + a code sent to the new address). The owner's email is fixed (S12); the owner can only
   confirm it. Accounts made before v0.27.0 have no email until they add one; until then they can't use Forgot
   password.
7. **Choose a new password.** "Require a new password" on Users sets a flag; from the next page that person sees, they
   are sent to `/password/new` (current password, new one twice) until they choose one (audit A5).
8. **Audit log** (table `audit_log`, page `/admin/audit` for admins): who changed which product, price, stock number,
   serving or add-on, ingredient, recipe line, shop details or account, when, with the old and new values. The
   line is written by the same `store/` function in the **same commit** as the change, so there is never a change
   without its line or a line without its change. Lines are never edited or deleted (like receipts, I8).
   Ingredient restock and count are not repeated there: they already have their own history with the person (I7).
9. **Links in emails** point at the address that works for the invitee: when the owner uses `127.0.0.1` on a setup
   that allows other devices, the link uses the computer's network address instead.

**Why.** The café can't use the system with the two demo accounts: everyone would share them, so no sale or change
could be traced to a person (DEC-003), and a forgotten password needed someone to edit the database. Invitations make
"who decided this person may sell here?" always answerable; the audit log makes "who changed this price?"
answerable; codes make email the way back in. Each part reuses what v0.26.0 built: email, the keyed hashes and the
record-first limits.

**Details checked.**

| Detail | Choice | Alternatives rejected |
|---|---|---|
| One owner | A partial unique index in the database | A check in Python only (two setups at once could make two owners) |
| Admins and the owner | `is_admin` = admin or owner; every admin check uses it | Giving the owner a second flag on an admin row (two fields that can disagree) |
| Removing someone | Switch off, keep the row | Delete (receipts and the audit log would point at nobody; their id could be reused, like I4) |
| Admins' powers | Cashiers only; the owner decides who may invite | Admins equal to the owner (an admin could make more admins or lock the owner's team out); only the owner manages anyone (a busy owner becomes a bottleneck) |
| Invitation token | 32 random bytes in the link, keyed hash in the database, looked up by hash and then compared with `compare_digest` | The token itself in the database (a database copy would hold working links); a short code to type (guessable) |
| Signup order | Username + password, then the code | Code first (an unfinished signup would leave a confirmed address with no account); no code (the link alone proves only that someone has the email, not that it is still theirs at the end) |
| Counting wrong code tries | One conditional update before checking | Read, compare, then add 1 (two guesses at once could both be counted as the 1st) |
| Forgot password answer | The same for every address | "No account with that email" (tells a stranger which emails belong to staff) |
| Forced new password asks the current one | Yes, with the A7 limit | Not asking (a stolen login could set a new password without knowing the old one) |
| Owner's email before v0.38.0 | Typed in setup, confirmed on Profile | Confirming inside setup (the setup can't wait for mail in an answers-file install; owner's decision 1) |
| Where audit lines are written | Inside each `store/` function, same commit | In the pages (they don't write, I1); a database trigger (can't know who is logged in; not on Firestore) |
| Audit details | The changed fields only, old → new, as JSON text | A copy of the whole row (hard to read); a separate table per kind (many tables for one page) |
| Link address in emails | Network address when the owner is on `127.0.0.1` and other devices are allowed | Always the address the owner used (a `127.0.0.1` link opens nothing on a phone); a new setting to type (one more thing to get wrong; can be added for the cloud package) |
| `add_users.py` | Deleted: it made accounts with the public demo passwords, which S12 forbids from v0.27.0 | Keeping it (a second way to make accounts outside invitations) |

**Honest limits.** Forgot password answers a little faster when no account has that address (no email is sent); with
10 requests an hour per computer and a few staff addresses, this tells a stranger very little. The emailed code on
every login, trusted devices and backup codes are v0.28.0; until then a login is still username and password. The
owner's email is typed during setup, not proven by a purchase, until v0.38.0. Google sign-in at signup is v0.29.0.

**Verdict:** Best choice. **Status:** Decided, 2026-10-24 (points 1 and 2 by the owner).

---

## DEC-030

**A code at every login, trusted devices, backup codes, the authenticator app and demo mode**
*(v0.28.0, F25; rules S1, S13, S14, D1, D2, P3; DEC-004, DEC-005, DEC-006, DEC-012, DEC-017)*

**Owner's decisions (2026-10-25), asked before building (C8):**

1. **Accounts with no email yet** (made before v0.27.0) can't get an emailed code. Their login is refused with "ask the
   owner to add your email"; the owner (or an admin, for a cashier) types that person's own address on Users, and
   the person's next login sends the code there, which also confirms it. The owner vouches for the address, as with
   an invitation. An account using an authenticator app needs no email.
2. **Two more public pages** in rule S1: `/verify` and `/verify/resend`. They work only within 5 minutes of a correct
   password; otherwise they go back to the login page.

**How it works.**

1. **Login, step 1:** the password, with the 5-tries limit (DEC-028), as before. A switched-off account is refused.
   Outside demo mode, the published demo passwords (`admin123`, `cashier123`) are refused (rule P3).
2. **Trusted device?** The browser's `trusted` cookie holds up to 10 random tokens (a shared counter computer can be
   trusted by each cashier separately). If one matches an unexpired row in `trusted_device` *for this user*, the
   person is logged in with no code (S13: trust skips only the code).
3. **Otherwise, half-logged-in:** the session remembers who typed the right password, for **5 minutes**, and only
   `/verify` opens. With the default method a 6-digit code is emailed (the v0.27.0 code rules, purpose `login`);
   with an authenticator app nothing is sent.
4. **`/verify`** accepts the emailed code, the app's code, or a **backup code**. Wrong tries count toward the same
   limit (5, then wait 5 minutes), recorded before checking. The box **"Trust this device for 30 days"** (7 for
   admins and the owner) creates the trusted-device row and cookie. Then the normal login starts (the login row of v0.20.3).
5. **Trust ends** on: Profile → Devices → Remove; **Log out everywhere** (new, on Profile); a password change or
   reset; switching the account off; a role change; and after 30 / 7 days.
6. **Backup codes:** 10 one-time codes like `k7mp-29xa`, shown **once** (Profile, password needed; the page is sent
   with `Cache-Control: no-store`), stored as keyed hashes (S14). Making new ones cancels the old ones.
7. **Authenticator app** (DEC-017, unchanged): Profile → Sign-in method → password → a QR code (drawn by `segno`, an
   SVG `data:` image, `no-store`) and the key as text → the app's current code proves the scan → switched, new backup
   codes shown, and an email says the sign-in method changed. Turning it off needs the password and a current app or
   backup code, and emails too. The key is stored **encrypted** with Fernet (`cryptography`); its key is
   `instance/totp_key.txt` (made once, never in Git, P1) or the `TOTP_ENCRYPTION_KEY` environment variable. A code
   is accepted for the current 30-second step or one either side, and **never for a step already used** (one
   conditional update of `totp_last_step`). An admin (for cashiers) or the owner can reset someone's method to email
   from Users: logged and emailed. Nobody can reset the owner's this way (DEC-017).
8. **Demo mode** (`DEMO_MODE=1`, rule P3): every email (codes, invitations, tests) is printed in the server window
   instead of being sent, so the demo works with no mail server and no internet. Start-up **refuses** demo mode
   when real mail settings exist, so it can't be left on in a shop. The demo passwords work only in demo mode.
9. **The automated tests of other features** log in with the password only (no code, demo passwords allowed) by
   setting `app.config['TEST_PLAIN_LOGIN'] = True`, like `CSRF_ENABLED`. The contract check fails if any file outside
   `tests/` sets it.

**Why.** A password alone fails the moment it is seen over a shoulder or guessed (DEC-004). The rest makes the code
bearable and safe: trust on the counter computer keeps staff from working around it (DEC-005), backup codes and
trusted devices keep the local package logging in when the Wi-Fi is down (DEC-012, rule D2), and the app option
works with no internet at all (DEC-017).

**Details checked.**

| Detail | Choice | Alternatives rejected |
|---|---|---|
| Half-logged-in state | A short session value (user, method, time), 5 minutes, opens only `/verify` | Logging in and then blocking every page (a forgotten check would leak a page); a separate cookie (one more thing to sign and expire) |
| Where trust is kept | A cookie of random tokens + hashed rows in the database | A signed cookie alone (can't be removed from Profile or ended by a password change); the IP address (Wi-Fi addresses change, and anyone on the Wi-Fi would be trusted) |
| Trust on a shared computer | Up to 10 tokens in one cookie, each tied to its own user | One token per browser (the second cashier's trust would replace the first's) |
| Trust on a role change | Ended | Kept (a cashier's 30 days would carry over to an admin, who should get 7) |
| Backup code format | 8 characters from 31 letters and digits that can't be confused (no 0/o, 1/l/i), shown as `xxxx-xxxx` | 6 digits (looks like a login code; fewer combinations); long hex (hard to type from paper) |
| Wrong tries at `/verify` | The login limit's table, per user, recorded first | Only the emailed code's own 5 tries (the app and backup codes would have no limit) |
| Authenticator key at rest | Fernet with its own key file | Encrypting with the Flask secret key (one leaked file would open both); plain text (DEC-017) |
| Demo passwords outside demo mode | Refused by the password itself | By username (a real shop may well call its owner "admin") |
| Tests of other features | A config switch like `CSRF_ENABLED`, checked by the contract | Typing codes in all 30 older test files (hundreds of lines that test nothing new); an environment variable (could be set on a shop's computer by mistake) |

**Packages (rule D1).** `cryptography` 50.0.2 (with `cffi` 2.1.1 and `pycparser` 3.12, which it needs on Windows)
and `segno` 1.6.6, approved for this version on 2026-10-24 (DEC-011, DEC-017), pinned and added to the D1 list, the
allowlist and `requirements/local.txt`. The code calculation itself (TOTP, RFC 6238) uses only `hmac`, `struct`,
`base64` and `time`.

**Honest limits.** A fake login page that forwards the password and code within seconds beats any code (DEC-017);
passkeys stop it but need HTTPS. A lost phone with no backup codes left needs an admin's reset, or for the owner,
the subscription seller. The login sequence diagram in the submitted report still shows v0.20.4; the report's
updated version gets the new one.

**Verdict:** Best choice. **Status:** Decided, 2026-10-25 (points 1 and 2 by the owner).

---

## DEC-031

**Sign in with Google, linking it from Profile, and joining with it** *(v0.29.0, F26; rules S1, S12, S13, S14, D1,
D2; plan §2.3; DEC-003, DEC-005)*

**Owner's decisions (2026-10-25), asked before building (C8):**

1. **Two more public pages** in rule S1: `/login/google` (sends the browser to Google) and `/auth/google/callback`
   (where Google sends it back). The callback accepts only an answer that matches what this browser started.
2. **The same email for everyone.** A Google account can be linked only if its verified email is the account's
   confirmed email (plan §2.3 asked this only of the owner). One identity per person, as with invitations.

**How it works.**

1. **The standard flow** (OpenID Connect, "authorization code" with PKCE), in `google_signin.py`: the browser is sent
   to Google with a random `state`, a random `nonce` and a PKCE challenge, all kept in the session for 10 minutes.
   Scopes: `openid email profile` only (no access to the Gmail inbox).
2. **Google's answer is checked here, not trusted:** `state` matches (`compare_digest`); the code is exchanged for an
   ID token (with the PKCE verifier); the token's **signature** is checked against Google's published keys
   (RS256 only); then issuer is Google, audience is this shop's client ID, not expired (1 minute leeway), `nonce`
   matches, and `email_verified` is true. Any failure is one plain sentence.
3. **Accounts are linked by Google's permanent id** (`sub`, a new unique `user.google_sub`), never by the email,
   because an address can change hands.
4. **Logging in with Google** finds the account by `sub`; a switched-off account is refused. Then exactly what a
   password login does: a trusted browser goes in, everyone else goes to `/verify` for the code (plan D-5).
5. **Linking from Profile:** the current password and a fresh code (emailed with purpose `link`, or the app's code),
   then Google; the Google email must equal the account's confirmed email (owner's decision 2). Unlinking needs the
   password. Both are logged and emailed to the person.
6. **Joining with Google** (DEC-003): on the invitation page the person chooses a username and taps **Continue with
   Google**; the Google email must be the invited address; the usual code to that address follows, then the account
   exists with Google linked. Such an account gets a random password nobody knows; "Forgot your password?" can set
   one later.
7. **Where it works** (plan §2.3, stated honestly): Google only accepts `http://localhost` or an `https` address as a
   return address. The button shows on `localhost` and on `https`; on `127.0.0.1` or the shop's network address the
   login page says where Google sign-in works instead.
8. **Settings:** `[google]` in `instance/config.toml` (client ID and secret, from `setup_shop.py`, optional), or the
   `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` environment variables. Downloaded `client_secret*.json` files are
   already refused by the contract check (P1, DEC-016).

**Why.** Many café staff already sign in to everything with Google; one less password to forget or reuse. The checks
are the ones Google's own guide lists, done in our code where the tests can see them, so a forged or replayed
answer is refused even though the tests never talk to Google.

**Details checked.**

| Detail | Choice | Alternatives rejected |
|---|---|---|
| Library | Authlib 1.9.1 (approved, DEC-011), `OAuth2Session` for the flow, `joserfc` (which Authlib uses) for the token | Writing the OAuth exchange by hand (where mistakes hide); Flask-Dance (not approved); Google's own `google-auth` (pulls in more packages) |
| Google's addresses | Fixed in the code (authorization, token, keys) | Fetching Google's discovery document at start-up (an extra request, and start-up would need internet) |
| Linking key | `sub` | The email (can change hands: a new person with a recycled address would get the account) |
| Which Google account | Same verified email as the account (owner's decision 2) | Any verified Google account (the account's email and its Google login could belong to different people) |
| Code after Google | Yes, unless trusted (plan D-5, S13) | Trusting Google's own second step (we can't see whether the person used one) |
| Linking needs | Password + a fresh code | Password only (a stolen unlocked till could link the thief's Google account); nothing (the same, worse) |
| Joining with Google | Username first, then Google, then the code | Taking the username from Google's name (clashes, spaces, changes) |
| Tests | Real signature and claim checks with a test key made in the test; only the two network calls replaced | A fake that returns "valid" (would test nothing of the checks); a real Google account (rule T3) |
| `127.0.0.1` | Explain, don't show a button that would fail | Sending a `localhost` return address from `127.0.0.1` (the session cookie belongs to the other name, so the state check would always fail) |

**Packages (rule D1).** Authlib 1.9.1 with joserfc 1.7.7; requests 2.34.2 with certifi 2026.10.23,
charset-normalizer 3.5.2, idna 3.20 and urllib3 2.8.0; approved for this version on 2026-10-24 (DEC-011), pinned and
added to the D1 list, the allowlist and `requirements/local.txt`.

**Honest limits.** Google sign-in needs the internet (rule D2: password, trusted devices and backup codes keep the
local package working) and, in the local package, the main computer at `localhost`. Each installation needs its own
Google Cloud project and OAuth client (plan §2.3); until it is verified by Google, "Testing" mode allows 100 named
users, enough for a café. The real exchange with Google is tried by hand with the owner's own client (TC-39.x).

**Verdict:** Best choice. **Status:** Decided, 2026-10-25 (points 1 and 2 by the owner).

---

## DEC-032

**Undo on the basket, a safe stock count, and undoing a count** *(v0.30.0, F27; plan §4.2, §4.8; rules I1, I7;
report §10.4 known limitations)*

**How it works.**

1. **Basket undo.** Before every change to the order (add, − / +, change the serving or add-ons, remove a line or a
   product) the order as it was is kept in the browser's session, up to the **last 5 changes**. **Undo** on New Sale
   puts back the newest one. Nothing in the database changes, because the basket only lives in the session. The
   undo list is emptied when the sale is completed (a sold order can never come back) and at log-in and log-out.
2. **A safe count (plan §4.8).** The count form now sends the amount the admin **saw** on the page. In one
   conditional step the count is saved only if the amount on hand is still that amount; the difference against it
   goes in the history (I7). If a sale or a delivery changed it in between, nothing is saved and the page says
   "it changed since you opened the page (now X): count again". A count without the amount seen (a page opened
   before this version) is refused the same way.
3. **Undo a count (plan §4.2).** For **5 minutes** after a count, Ingredients and the ingredient's page show
   **Undo count**. It adds the opposite history line (reason `count-undo`) and puts the amount back, in one
   conditional step. It is refused if anything else happened to that ingredient since (a sale, a delivery, another
   count): the shelf has changed, so the admin counts again instead.

**Why.** These were three known limitations in the report (§10.4): a wrong tap could only be fixed with another tap,
a count could silently overwrite a sale made at the same moment (breaking I1's promise for counts), and a mistyped
count (750 instead of 75) had no way back except a second count.

**Details checked.**

| Detail | Choice | Alternatives rejected |
|---|---|---|
| Basket undo kept where | The session, like the basket | The browser's own memory (lost on reload, and the server is the truth); the database (a write for every tap, for something not yet sold) |
| What is kept | Whole copies of the order, at most 5, and at most about 1,500 characters together | A list of "reverse operations" (more code, more ways to get wrong); unlimited (the session cookie has a 4 KB limit, and a cookie that is too big is dropped, logging the cashier out) |
| After completing a sale | The undo list is emptied | Keeping it (an undo could bring back an order that was already sold and charged) |
| A count that raced a sale | Refused, "count again" | Applying the difference to the new amount (it guesses whether the counted shelf was before or after the sale left it); overwriting (today's behaviour, loses the sale) |
| Comparing the amount seen | Within 0.0005 of the stored amount (the page shows 3 decimals) | Exact equality (ingredient amounts are decimals, so 999.7 on screen can be 999.69999… stored) |
| Undo window for a count | 5 minutes, and nothing else may have happened since | Any time (a sale since makes the old amount wrong); no undo (a typo needs a second count, and the history keeps a nonsense line either way) |
| Undoing writes | A new history line `count-undo` | Deleting the count's line (history lines are never edited or deleted, I7) |

**Honest limits.** The basket undo belongs to one browser and goes back 5 steps only. A count undo isn't possible
after the 5 minutes or once a sale has used that ingredient; then the admin simply counts again.

**Verdict:** Best choice. **Status:** Decided, 2026-10-25.

---

## DEC-033

**Voids and refunds: how they are asked for, approved, put back on the shelf and counted** *(v0.31.0, F28; plan
§4.1; rules I1, I2, I3, I7, I8, S14, S15; DEC-007; report §10.4 known limitations)*

**How it works.**

1. **A new record, never an edit.** A void or refund is a `sale_adjustment` row with one `adjustment_line` per
   receipt line (how many, the money, back on the shelf or waste). It names who asked, who decided, when, how
   (password or emailed code), the reason, and how the money went back (cash from the drawer, or GCash with the
   13-digit reference of the transfer made in the shop's GCash app). The receipt's own rows never change (I3, I8);
   the receipt page and the printed receipt show "VOIDED on …" or "Refunded ₱… of ₱…", with a link to a printable
   **slip** for each void or refund.
2. **Void** = the whole receipt, **only on the day of the sale** (until v0.32.0 brings the Z reading, the day ends
   at midnight on the shop's clock). Anyone may **ask** for it on the receipt (with a reason); nothing changes until
   an admin approves. An admin approves at the top of the **Sales Report** or on the receipt, typing **their own
   password**; an
   admin can also void a receipt at once (asked and approved by them, with their password). Approving puts
   **everything** back on the shelf. A request still waiting the next day can only be rejected; then a refund is
   used.
3. **No admin at the till: an emailed code.** The cashier picks an admin (one with a confirmed email) and presses
   Send. That admin gets the receipt, the items, who asks and why, and a 6-digit code. If they agree, they tell the
   cashier the code; the cashier types it and the void is approved **in that admin's name**. The code works for that
   void only, for 10 minutes, once, with 5 tries, and is kept only as a keyed hash (S14), like every other code.
   Sending is limited to one a minute and five an hour per admin, like other codes.
4. **Refund** = chosen lines and quantities, **any day**, **admins only**, confirmed with their password. Each line
   goes **back on the shelf** (an unopened pastry, a bottled drink) or is **waste** (a made drink). The page chooses
   waste first for anything made from a recipe.
5. **No double money, no double stock (I1, I2).** Approving changes the request from "requested" to "approved" and
   marks the sale voided, each with a conditional update, inside the same transaction as the stock: a second admin
   clicking at the same moment finds nothing to change and gets "already decided". A refund raises the sale's
   refunded total only `WHERE refunded_total + amount <= total` and each line's refunded quantity only `WHERE
   refunded_quantity + n <= quantity`; if either finds 0 rows, everything is rolled back. A GCash reference can be
   used once (a unique rule).
6. **Exactly the ingredients that line used.** From this version every receipt line keeps its own ingredients
   (`sale_item_usage`). Returning one latte of two returns exactly half of that line's milk and beans, even if the
   recipe has changed since. The history gets `void` or `refund` lines (+), and waste gets a `refund` line (+) and a
   `waste` line (−), so the shelf is unchanged but the owner can see what was thrown away (I7).
7. **Reports.** The Sales Report shows **Net sales** = gross − voids − refunds, with each part. A void counts on its
   sale's day (it can only happen that day); a refund counts on the day the money went back, even for an older
   receipt. "Cash" and "GCash" are what came in that way minus what went back that way, so Cash is what should be
   in the drawer. Units and top products count what the customers kept. Home's "revenue today" is net too. Voids
   and refunds are also in the audit log (area "Voids & refunds").
8. **One place for the money (owner's decision, 2026-10-25).** There is no separate Voids & refunds page: the void
   requests waiting for an admin sit at the top of the Sales Report (the red number in the menu is next to Sales
   Report), and the report lists the period's voids, refunds and rejected requests under its sales. Today's receipts
   stays its own page, for the cashiers.

**Why.** The report listed "no void or refund" as a known limitation (§10.4); the café's only way to fix a wrong sale
was to leave the numbers wrong. DEC-007 decided the principle (keep the receipt, add a correction, a second person
approves). This entry decides how it works day to day.

**Alternatives checked.**

| Detail | Choice | Alternatives rejected |
|---|---|---|
| Where admins find waiting voids | The top of the Sales Report, and each receipt (owner's decision) | A separate Voids & refunds page (first build; the owner found it one page too many, since the money is already on the report) |
| Approval at the till | The admin's own password on their own screen, or an emailed code | **The admin types their username and password on the cashier's screen** (a common "manager override"): it checks only the password, not the second step every login needs (S13), so a cashier who once saw the admin type it could approve their own voids. The emailed code proves the admin has their mailbox, works when they are not in the shop, and names them |
| Who gets the emailed code | The one admin the cashier chooses, each with their own code | One code to every admin (the void could not say *which* admin agreed); a link in the email that approves (the local package can't be reached from outside the shop, and a link can be clicked by a mail scanner) |
| Password on approval | Asked again, even though the admin is logged in | Not asked (anyone at an admin's unlocked screen could approve) |
| An admin's own void | Allowed at once, with their password | Requiring a second admin (impossible in a shop with one admin, who is often the owner) |
| Void after the day | Refused; a refund instead | Allowed any day (it would change a day already counted, and from v0.32.0 a day closed by the Z reading) |
| Refund on the same day | Allowed (a customer returns one of two drinks) | Only on later days (no safety gained: refunds are admin-only already) |
| Ingredients to return | Each line's own amounts, kept at the sale | Working them out again from today's recipe (the recipe or the options may have changed); returning them in proportion to the sale's total (wrong whenever a sale has two different drinks) |
| Lines sold before v0.31.0 | Void: the sale's own history lines are put back; refund of a recipe line: waste only | Guessing each line's share (could put back the wrong amounts) |
| Waste in the history | A `refund` (+) and a `waste` (−) line | No line (waste would be invisible to the owner); one `waste` line that changes the amount (the shelf did not change: the history would no longer add up to what is on hand) |
| Money back for a GCash sale | The admin chooses; GCash needs the reference of the transfer back | Always the sale's method (some customers prefer cash back); GCash with no reference (nothing to check it against later) |
| Where a refund counts in the report | The day the money went back | The sale's day (a report already printed and counted would change afterwards) |

**Honest limits.** The code by email needs the internet and a working mail server (the screen says so when it can't
send). Approving needs an admin with a confirmed email for the code route. A request waiting overnight can't be
approved any more. Refunds of the product's own count put units back on the shelf, which the admin should only choose
for things that can really be sold again.

**Verdict:** Best choice. **Status:** Decided, 2026-10-25.

---

## DEC-034

**Help on every page: a ? button with this page's help, and a Help page with every page** *(v0.32.0, F29; rules
C6, C7, D1, D2, S1, S11; owner's decisions 2026-10-25)*

**How it works.**

1. **A ? button on every page**, only an icon (a question mark in a circle), with "Help for this page" for screen
   readers and as its tooltip. On wide screens it is a small round button in the bottom right corner; on phones it
   is in the top bar; on the login pages it sits beside the theme switch.
2. **Pressing it slides in a side panel** (Bootstrap's offcanvas, already in the app) with that page's help: one
   sentence on what the page is for, a picture of the page, the main steps, and a link to the Help page. The page
   behind stays as it was, so nothing typed is lost.
3. **The Help page (`/help`, logged-in users)** lists every topic the person may read, each with its picture, steps
   and an "Open" link, and a row of chips at the top to jump to any page. The avatar menu links to it.
4. **Each person sees what they can do.** A cashier's Help leaves out the admin pages, and on shared pages (a
   receipt, Products, Home) each step is marked for everyone, admins or cashiers, so a cashier reads "Ask for a void"
   and an admin "Void now". On an admin page a cashier gets 403 as before, with no help.
5. **The words are in one file, `help_topics.py`**, as plain text (18 topics). Templates escape them like every other
   text (S11). Each topic names the pages it explains; a test fails if a page that can be opened has no topic, or a
   topic names a page that no longer exists, so the help can't silently fall behind the system.
6. **The pictures are screenshots of the demo shop** (generic names, rule P2), light theme, 1280 px wide, stored in
   `static/help/` as WebP (18 pictures, about 0.7 MB in all), so they work with no internet (D2). They were taken with
   a headless Edge on a scratch copy of the demo data; from v1.0.0 the Playwright browser tests can retake them.

**Why.** The owner wants to show what each page does quickly in the defense, and a client needs the same thing: a
café owner or a new cashier learns a page from a picture and three to five steps, on the page itself, without
calling anyone. It also covers a feature that can't be shown live (for example real email when the internet or
Gmail is down) with a picture of how it works.

**Alternatives checked.**

| Detail | Choice | Alternatives rejected |
|---|---|---|
| Where help lives | A panel on the page, plus a Help page | **Only a Help page** (the user leaves the page and loses their place); **a printed or PDF manual** (gets lost, goes out of date, not on the screen where the question comes up); **a video** (can't be searched, goes out of date with every change, heavy to store offline) |
| Kind of help | What the page is for + a picture + steps | **Tooltips on every field** (help only with one field, not with "what is this page for"; many more texts to keep up); **a guided tour that points at buttons** (needs a JavaScript library, a new dependency for rule D1, and breaks whenever a page's layout changes) |
| The button | Icon only, round, bottom right on wide screens; in the top bar on phones (owner's choice: icon only) | **In the sidebar footer beside the theme switch** (tried first: it squeezed the username to "ad…"); **in each page's heading** (18 templates to change and easy to forget on a new page); **a Help link with words in the menu** (takes a menu line; the owner asked for an icon) |
| What the button opens | This page's help in a side panel (owner's choice) | Jumping to this page's part of the Help page (leaves the page) |
| Cashiers | Only their own pages and steps (owner's choice) | Every page marked "Admins only" (shows a cashier things they can't use and can't try) |
| Where the words are kept | One Python list, tested | **Text in each template** (no single place to read or check them, and nothing would notice a page without help); **Markdown files** (needs a Markdown package, D1) |
| Pictures | One per page (owner's choice), WebP, stored in the app | **One per step** (30–40 pictures, more to retake after every change); **PNG** (about three times larger for the same look); **pictures taken by hand** (can't be retaken the same way after a change) |
| Dark theme | Light pictures, framed, inside a dark panel | **A second set of dark pictures** (twice the files and the work for little gain; the frame makes clear it is a picture) |

**Honest limits.** The pictures show the system as it is in v0.32.0; a page that changes needs its picture retaken
(the test only checks that each picture exists and is small, not that it is current). The help is in English only.

**Version numbers (owner's decision, 2026-10-25).** Help is v0.32.0 so the defense copy has it; every later version
in plan §6 moves down one number: shifts and X/Z readings v0.33.0, senior/PWD discounts v0.34.0, product restock and
archive v0.35.0, backup and restore v0.36.0, CSP v0.37.0, cloud package v0.38.0, licence check v0.39.0, Firebase
v0.40.0. Older entries in this file keep the numbers they were written with (they record what was decided then);
the rules, the plan and the code comments now use the new numbers.

**Verdict:** Best choice. **Status:** Decided, 2026-10-25.
