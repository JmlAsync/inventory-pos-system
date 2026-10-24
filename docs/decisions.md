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
