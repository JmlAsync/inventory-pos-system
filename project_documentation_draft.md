# Inventory & POS System — Project Documentation Draft

> **Living document.** Add to it after every iteration (version tag). Don't wait until the end.
> This draft covers the system up to **v0.8.1** (tagged 2026-10-08).
> Rebuilt on 2026-10-03 from the Git history and the source code, and tested against v0.7.0.
>
> This is a *draft*, not the final report. The final report will be written in LibreOffice Writer and must
> follow the professor's list in *Final_Project_Details.docx*, Section B. Section 10 below tracks which of
> those items are covered here and which are still to do.

---

## Contents

1. Project overview
2. Software process model (Lecture 2)
3. Version history
4. Actors (who uses the system)
5. User stories (Lecture 3, p. 21 style)
6. Test cases (Lecture 3, p. 31 style)
7. Defects found during testing
8. Use cases (Lecture 4 p. 65 and Lecture 5 p. 15–17 style)
9. Guide: drawing the use case diagram
10. Report checklist (professor's Section B)

---

## 1. Project overview

| Item | Detail |
|---|---|
| Project name | Inventory & POS (Point-of-Sale) System |
| Type | Web application |
| Developer | Solo project |
| Business purpose | Help a small store keep track of its products and stock, and (in later iterations) record sales at the counter |
| Language / framework | Python 3.11.9, Flask 3.1.3 |
| Database | SQLite, accessed through Flask-SQLAlchemy 3.1.1 |
| Login and security | Flask-Login 0.6.3; passwords hashed with Werkzeug (scrypt) |
| User interface | HTML templates (Jinja2) styled with Bootstrap 5.3.3 |
| Version control | Git + GitHub — `https://github.com/JmlAsync/inventory-pos-system` |
| Versioning scheme | Semantic versioning (`MAJOR.MINOR.PATCH`), one tag per finished increment |

**Glossary for beginners**

- **POS (Point of Sale):** the place, and the software, where a customer pays for items, like the cashier's counter at a grocery store.
- **SKU (Stock Keeping Unit):** a unique code a store gives each product (for example `BEV-001`), so two products never get mixed up even if their names are similar.
- **CRUD:** the four basic things you can do with stored data: **C**reate, **R**ead, **U**pdate, **D**elete.
- **Hashing:** turning a password into a scrambled string that can't be turned back into the password. When someone logs in, the system hashes what they typed and compares the two hashes. Even if someone steals the database, they don't get the real passwords.
- **Role-based access control (RBAC):** giving each user a *role* (here: `admin` or `cashier`) and deciding what each role is allowed to do.

---

## 2. Software process model (Lecture 2)

> *Professor's item: "Which one will be your project model — waterfall, incremental or reuse-oriented development. Explain in detail and why?"*

### Chosen model: **Incremental development**

**What it means.** In incremental development the system is built and delivered as a series of small working
versions called **increments**. Each increment adds one piece of functionality to the previous one. After each
increment the system can be run, shown and tested, and what was learned feeds into the next increment.
Specification, development and validation are *interleaved* (they overlap) instead of happening once, in strict order.

**How this project follows it.** Every Git tag is one increment, and every increment produced a version that runs:

| Increment | Added | Could be shown working? |
|---|---|---|
| v0.1.0 | Flask app with a home page | Yes: home page loads |
| v0.2.0 | Product data model and database | Yes: database file is created |
| v0.3.0 | Product list page with Bootstrap | Yes: products display in a table |
| v0.4.0 | Add-product form | Yes |
| v0.5.0 | Edit and delete products | Yes: full CRUD |
| v0.6.0 | Log in / log out | Yes |
| v0.7.0 | Admin vs. Cashier permissions | Yes |
| v0.7.1 | Bug fixes found by testing (patch) | Yes: invalid input now rejected with a message |
| v0.8.0 | Sale processing: basket, cash & change, stock deduction, printable receipt | Yes: a full checkout works end to end |
| v0.8.1 | Receipt fix found by hand testing (patch) | Yes: old receipts say "not recorded" |
| v0.9.0 → | Low-stock warning, sales report, demo data (planned) | — |

**Why incremental, and not the other two?**

| Model | Why it was / wasn't chosen |
|---|---|
| **Waterfall** | Waterfall needs all requirements fixed and signed off *before* coding starts, and nothing works until the end. I started the project as a complete beginner, so I couldn't predict every requirement or how hard each part would be. A mistake found late in waterfall is expensive to fix. **Not chosen.** |
| **Reuse-oriented** | This model builds the system mainly by configuring and combining existing systems or components (for example, adapting an off-the-shelf POS). The professor requires the code to be written by the student ("if you bring a ready code/project, you will get Fail"), so a system built mostly from existing products would not fit. **Not chosen as the main model.** |
| **Incremental** | ✔ Lets a beginner learn step by step. ✔ Always has a working version to show the professor. ✔ Each increment is small enough to test properly. ✔ Fits Git tagging naturally (one tag = one increment). ✔ If time runs out before the deadline, there is still a working system with the most important features. **Chosen.** |

**Honest note on reuse.** The project still *reuses* well-known components: Flask, Flask-Login,
SQLAlchemy and Bootstrap. Almost every modern project does this. Sommerville points out that most
real projects combine models. So the accurate description is: *an incremental process that reuses
standard framework components*. Saying this in the report shows a deeper understanding than claiming a
"pure" model.

**Weaknesses of incremental (worth stating in the report):** the overall structure can degrade as
increments are added (all routes currently live in one `app.py` file), and progress is harder to measure
against a fixed plan. Planned mitigation: refactor (reorganize code without changing what it does) before the UI polish increment.

---

## 3. Version history

Each version is marked with an **annotated tag**: a tag that also stores a message, a date and who made it.
The tag message summarizes what the increment added.

| Tag | Date | Commit | Tag message (what was added) |
|---|---|---|---|
| — | 2026-08-12 | `2cf8b49` | *(no tag)* Initial commit: add README |
| v0.1.0 | 2026-08-12 | `cb95116` | Walking skeleton: Flask running, GitHub connected |
| v0.2.0 | 2026-08-12 | `d3ca52b` | Walking skeleton plus working database layer (Product model) |
| v0.3.0 | 2026-08-12 | `e6ceedb` | Product list view with Bootstrap-styled templates |
| v0.4.0 | 2026-08-12 | `e2f3947` | Add product creation via form |
| v0.5.0 | 2026-08-12 | `51f0ecc` | Full product CRUD: create, read, update, delete |
| v0.6.0 | 2026-08-12 | `2d1a6ae` | User authentication (login/logout, no role restrictions yet) |
| v0.7.0 | 2026-08-13 | `6f552f9` | Role-based access: Admin can manage products, Cashier is view-only |
| — | 2026-10-03 | `e76f4a1` | *(no tag)* Add documentation draft, test results and use case diagram |
| v0.7.1 | 2026-10-04 | `6043cdb` | Product validation fixes: duplicate SKU, negative values, peso sign *(first feature branch + pull request #1)* |
| — | 2026-10-04 | `1d1dd0e` | *(no tag)* Update documentation for v0.7.1: test results and fixed defects |
| v0.8.0 | 2026-10-08 | `1343236` | Sale processing: basket checkout, cash and change, stock deduction, printable receipt *(pull request #2)* |
| v0.8.1 | 2026-10-08 | `538ce09` | Receipt fix: show 'not recorded' for sales made before cash tracking *(pull request #3)* |

**How the version numbers work (semantic versioning):** `MAJOR.MINOR.PATCH`.
- **MINOR** goes up when a new feature is added (v0.6.0 → v0.7.0).
- **PATCH** goes up for bug fixes only (v0.7.0 → v0.7.1). The defects in Section 7 would be a good v0.7.1.
- **MAJOR** goes from 0 to 1 when the system is complete and ready to hand in (v1.0.0). The professor's
  document uses 1.0.0, 1.0.1, 1.0.2 as examples, so the final submission should be tagged **v1.0.0**.

---

## 4. Actors (who uses the system)

An **actor** is anyone (or anything) outside the system that interacts with it.

| Actor | Description | Can currently do |
|---|---|---|
| **Visitor** | Anyone who opens the website but has not logged in | See the home page; go to the login page |
| **User** *(general)* | Any logged-in person. This is a "parent" actor: Admin and Cashier are both kinds of User | Log in, log out, view the product list |
| **Admin** | Store owner or manager. *Is a* User | Everything a User can do, **plus** add, edit and delete products |
| **Cashier** | Counter staff. *Is a* User | Everything a User can do (view only). Will process sales in v0.8.0 |

> **Why "User" as a parent?** Admin and Cashier share some abilities (log in, log out, view products).
> Instead of drawing the same lines twice, UML lets you draw them once on a general *User* actor and
> show that Admin and Cashier *inherit* them. This is called **generalization**. It matches the code: there is one
> `User` table, and a `role` column decides admin vs. cashier.

---

## 5. User stories (Lecture 3, p. 21 style)

> Sommerville's example ("A 'prescribing medication' story") is a short **narrative**: it follows a named
> person through a realistic situation and describes what they do and what the system does, in plain language.
> Characters used below: **Maria** (store owner, Admin) and **Jun** (cashier).

### Story F1 — Viewing the product list *(v0.3.0)*
Jun arrives for his morning shift at the store. A customer asks whether there is any 1.5-litre Coke left.
Jun logs in to the Inventory & POS system on the counter computer and opens the **Products** page. The
system shows a table of every product with its name, SKU, price, quantity in stock and category. Jun finds
"Coke 1.5L" in the table, sees that 24 are in stock, and tells the customer where to find it.

### Story F2 — Adding a new product *(v0.4.0)*
A supplier delivers a new brand of instant noodles. Maria logs in as Admin and opens the Products page,
where she sees an **Add Product** button (cashiers don't see it). She clicks it and a form appears asking for
the name, SKU, price, quantity and an optional category. She enters "Instant Noodles", SKU `FD-001`, price
15.00, quantity 10 and category "Food", then clicks **Add Product**. The system saves the product in the
database and takes her back to the product list, where the noodles now appear.

### Story F3 — Editing a product *(v0.5.0)*
The supplier raises the price of Coke 1.5L. Maria finds Coke in the product list and clicks its **Edit**
button. The system opens a form already filled in with the current details. She changes the price from 75.50
to 80.00 and the quantity to 20 after a stock count, then clicks **Save Changes**. The system updates the
record and returns her to the list showing the new values. If she had changed her mind, **Cancel** would
take her back without saving.

### Story F4 — Deleting a product *(v0.5.0)*
The store stops selling a product that no longer sells. Maria clicks **Delete** next to it. The browser asks
"Delete this product?" to protect against accidental clicks. She confirms, the system removes the product from
the database, and it disappears from the list.

### Story F5 — Logging in and out *(v0.6.0)*
Jun opens the system and clicks **Login**. He types his username and password. The first time, he mistypes
the password, so the system shows "Invalid username or password" without saying which of the two was wrong
(so a stranger can't learn which usernames exist). He tries again correctly and is taken to the product list.
The navigation bar now shows "cashier (cashier)" so he can see who is logged in. At the end of his shift he
clicks **Logout** and is returned to the home page. If anyone tries to open the Products page afterwards
without logging in, the system sends them to the login page.

### Story F6 — Admin and Cashier permissions *(v0.7.0)*
Maria wants cashiers to be able to look up products but not change prices or delete items. When Jun logs in
as a cashier, the product list shows "View only" where the Edit and Delete buttons would be, and there is no
Add Product button. Curious, Jun types the address of the add-product page (`/products/add`) directly into
the browser. The system refuses and shows a "403 – Access Denied" page with a button back to the products. The
check happens on the server, so hiding the buttons is not the only protection. When Maria logs in as admin,
all buttons are available to her.

### Story F7 — Processing a sale *(v0.8.0, fixed in v0.8.1)*
A customer at the counter brings two Cokes and three packs of noodles. Jun (or Maria, since the owner often covers the
counter) clicks **New Sale** in the navigation bar. He picks "Coke 1.5L" from a dropdown that shows each product's price
and how many are **available**, types 2, and clicks **Add to basket**; then does the same for the noodles. The basket shows
each line's subtotal and the total, ₱271.50, and the dropdown now shows fewer Cokes and noodles **available**, because
the ones in the basket are spoken for. (Adding a product that's already in the basket makes its line grow instead of
appearing twice; a wrong line can be taken out with **Remove**.) The customer hands over ₱500; as Jun types it into **Cash received**,
the page already shows the change, ₱228.50. He clicks **Complete Sale**. The system checks once more that every item
is still in stock, saves the sale, lowers the stock of each product, empties the basket and shows a **receipt** with the
receipt number, date and time, "Served by: cashier", every item, the total, the cash and the change. Jun clicks
**Print Receipt**; only the receipt is printed, without the menu or buttons. Had he typed ₱200, or tried to sell more
noodles than the shop has, the system would have refused with a clear message and saved nothing. Receipts from before
cash was recorded state "Cash and change not recorded" instead of showing a misleading ₱0.00 *(v0.8.1)*.

### Planned stories (to be confirmed before building)

**F8 — Low-stock warning *(planned v0.9.0)*.** When Maria opens the product list, products whose quantity has
fallen to or below a set threshold (for example 5) are highlighted, and a message at the top lists them, so she
knows what to reorder from the supplier.

**F9 — Sales report *(planned v0.10.0)*.** At the end of the day Maria opens **Sales Report**, chooses a date
range, and sees each sale, the number of items sold and the total revenue, so she can compare it with the
cash in the drawer.

---

## 6. Test cases (Lecture 3, p. 31 style)

> Sommerville's example ("Test case description for dose checking") gives, for each feature,
> the **Input**, the **Tests** to run, and the expected **Output**. Below, each feature has that summary,
> followed by a detailed table of individual test cases.
>
> **How these were run.** On 2026-10-03, every case was run against an untouched copy of v0.7.0 using
> Flask's built-in *test client* (a tool that sends requests to the app the way a browser would, but
> automatically), with a fresh database. TC-6.1 to TC-6.3, TC-6.6, TC-2.3, TC-2.5 and DEF-05 were **also confirmed
> by hand** in a real browser on the same day.
>
> **Reading the HTTP codes:** `200` = page shown OK · `302` = redirected to another page · `403` = forbidden ·
> `404` = not found · `405` = method not allowed · `500` = the server crashed.

### F1 — View product list

**Input:** a request to open `/products`, with or without being logged in.
**Tests:** 1. Open the page while logged out. 2. Open it while logged in. 3. Check that every saved product appears with all five fields.
**Output:** logged out → redirect to the login page; logged in → table of all products.

| ID | Precondition | Steps / input | Expected result | Actual result | Pass? |
|---|---|---|---|---|---|
| TC-1.1 | Not logged in | Open `/products` | Redirect to `/login` | 302 → `/login?next=/products` | ✅ |
| TC-1.2 | Logged in as admin, product "Coke 1.5L" exists | Open `/products` | Table shows Coke 1.5L, BEV-001, price, quantity, category | All fields shown | ✅ |
| TC-1.3 | Not logged in | Open `/` (home) | Home page loads | 200, home page shown | ✅ |

### F2 — Add product

**Input:** name (text, required), SKU (text, required, must be unique), price (decimal number), quantity (whole number), category (optional text).
**Tests:** 1. All fields valid. 2. Category left empty. 3. SKU already used. 4. Price not a number. 5. Negative price or quantity. 6. Empty name.
**Output:** valid input → product saved and shown in the list; invalid input → a clear error message and nothing saved.

| ID | Precondition | Steps / input | Expected result | Actual result | Pass? |
|---|---|---|---|---|---|
| TC-2.1 | Logged in as admin | Coke 1.5L, BEV-001, 75.50, 24, Beverages | Saved; redirect to list; shown as 75.50 | Saved, redirect, shown | ✅ |
| TC-2.2 | Admin | Noodles, FD-001, 15, 10, *(no category)* | Saved with empty category | Saved | ✅ |
| TC-2.3 | Admin, BEV-001 already exists | Dup, **BEV-001**, 1, 1 | Error message "SKU already exists"; nothing saved | **500 server crash** (database unique-constraint error not handled) *(also confirmed by hand: `IntegrityError`)* · **v0.7.1:** red message, nothing saved *(confirmed by hand)* | ❌→✅ DEF-01 |
| TC-2.4 | Admin | price = `abc` (sent without the browser's check) | Error message; nothing saved | **500 server crash** · **v0.7.1:** error message, nothing saved | ❌→✅ DEF-02 |
| TC-2.5 | Admin | price = **-5**, quantity = **-3** | Rejected: price and quantity cannot be negative | **Accepted and saved** with negative values *(negative price also confirmed by hand)* · **v0.7.1:** rejected by browser (`min="0"`) and by server | ❌→✅ DEF-03 |
| TC-2.6 | Admin | name = *(empty)*, sent without the browser's check | Rejected: name required | **Accepted**; product saved with no name · **v0.7.1:** rejected with message | ❌→✅ DEF-04 |

> **Why "sent without the browser's check"?** The form's HTML has `required` and `type="number"`, so a
> normal browser stops you before sending. But anyone can bypass the browser (with developer tools or a
> script), so the **server** must check again. This is called **server-side validation**, and it is a
> standard security rule: *never trust input from the client*.

### F3 — Edit product

**Input:** a product ID in the address (`/products/edit/<id>`) and the same fields as F2.
**Tests:** 1. Form opens pre-filled. 2. Valid change is saved. 3. Product ID doesn't exist. 4. SKU changed to one another product uses.
**Output:** changes saved and shown; a missing product gives "not found"; a duplicate SKU gives a clear error.

| ID | Precondition | Steps / input | Expected result | Actual result | Pass? |
|---|---|---|---|---|---|
| TC-3.1 | Admin, product 1 exists | Open `/products/edit/1` | Form pre-filled with current values | Pre-filled | ✅ |
| TC-3.2 | Admin | Change price 75.50 → 80, quantity 24 → 20, save | Saved; list shows new values | Saved (80.0, 20) | ✅ |
| TC-3.3 | Admin | Open `/products/edit/999` | 404 Not Found | 404 | ✅ |
| TC-3.4 | Admin, FD-001 belongs to another product | Change product 1's SKU to FD-001 | Error "SKU already exists" | **500 server crash** · **v0.7.1:** error message, nothing changed | ❌→✅ DEF-01 |

### F4 — Delete product

**Input:** a product ID, sent with a POST request (the Delete button).
**Tests:** 1. Delete an existing product. 2. Delete a product that doesn't exist. 3. Try to delete with a plain link visit (GET) instead of the button.
**Output:** product removed; missing ID → 404; GET → refused.

| ID | Precondition | Steps / input | Expected result | Actual result | Pass? |
|---|---|---|---|---|---|
| TC-4.1 | Admin, product 2 exists | Click Delete on product 2, confirm | Removed from database and list | Removed | ✅ |
| TC-4.2 | Admin | POST `/products/delete/999` | 404 | 404 | ✅ |
| TC-4.3 | Admin | Visit `/products/delete/2` as a normal link (GET) | Refused (deleting through a link is unsafe) | 405 Method Not Allowed | ✅ |
| TC-4.4 | Admin | Click Delete, then Cancel in the pop-up | Product kept | Pop-up is in the browser (`confirm()`); confirmed by code reading, **to test by hand** | ⏳ |

> **Why does TC-4.3 matter?** If deleting worked through a simple link, a web crawler or a malicious link in
> an email could delete products just by visiting it. Requiring POST (a form submission) prevents that.

### F5 — Log in / log out

**Input:** username and password.
**Tests:** 1. Correct details. 2. Wrong password. 3. Username that doesn't exist. 4. Username in different capitals. 5. Logout. 6. Protected page after logout. 7. Passwords are not stored in plain text.
**Output:** correct → logged in and sent to Products; wrong → the same general error message; logout → protected pages locked again.

| ID | Precondition | Steps / input | Expected result | Actual result | Pass? |
|---|---|---|---|---|---|
| TC-5.1 | Users exist | admin / admin123 | Redirect to Products; navbar shows "admin (admin)" | As expected | ✅ |
| TC-5.2 | — | admin / *wrong* | "Invalid username or password" | Shown | ✅ |
| TC-5.3 | — | ghost / x | Same message as TC-5.2 (doesn't reveal which part was wrong) | Same message | ✅ |
| TC-5.4 | — | **ADMIN** / admin123 | *Design decision:* usernames are case-sensitive → rejected | Rejected | ✅ |
| TC-5.5 | Logged in | Click Logout | Logged out; redirect to home | 302 → `/` | ✅ |
| TC-5.6 | Just logged out | Open `/products` | Redirect to login | 302 → `/login` | ✅ |
| TC-5.7 | Users created | Look at the `password_hash` column in the database | A hash, not the real password | Stored as `scrypt:32768:8:1$…` hash | ✅ |
| TC-5.8 | Not logged in | Open `/products/add` → log in | After login, return to the page originally requested | Always goes to `/products` (the `next` value is ignored) | ⚠️ minor, DEF-06 |

### F6 — Role-based access (Admin vs. Cashier)

**Input:** a logged-in user with role `admin` or `cashier`, requesting product-management pages.
**Tests:** 1. Cashier sees no management buttons. 2. Cashier types each admin address directly. 3. Cashier sends a hidden form submission. 4. Admin keeps full access.
**Output:** cashier → view only, every admin action refused with 403; admin → full access.

| ID | Precondition | Steps / input | Expected result | Actual result | Pass? |
|---|---|---|---|---|---|
| TC-6.1 | Logged in as cashier | Open `/products` | No Add button; "View only" instead of Edit/Delete | As expected *(also checked by hand)* | ✅ |
| TC-6.2 | Cashier | Type `/products/add` in the address bar | 403 Access Denied page | 403 page *(also checked by hand)* | ✅ |
| TC-6.3 | Cashier | Open `/products/edit/1` | 403 | 403 | ✅ |
| TC-6.4 | Cashier | Send a POST to `/products/add` with product data | 403; nothing saved | 403 | ✅ |
| TC-6.5 | Cashier | Send a POST to `/products/delete/1` | 403; product still exists | 403; product still exists | ✅ |
| TC-6.6 | Logged in as admin | Add / edit / delete | All allowed | Allowed *(also checked by hand)* | ✅ |

### F7 — Process sale *(v0.8.0, v0.8.1)*

**Input:** products and quantities added to a basket; cash received from the customer.
**Tests:** 1. Building the basket (adding, merging, removing). 2. Stock limits, including what is already in the basket. 3. Invalid quantities and products. 4. Cash checks. 5. Completing a sale and its effect on stock. 6. Receipts, including old ones. 7. Who can sell, and basket privacy.
**Output:** valid sale → saved, stock reduced, receipt shown; anything invalid → clear message and **nothing saved**.

> **How these were run.** On 2026-10-08 against the code tagged **v0.8.0** (`1343236`) using the Flask test client, plus a real
> browser (Chromium) for the JavaScript change preview; v0.8.1 (`538ce09`) was re-tested the same day, including on a
> **copy of the real database**. Cases marked *(by hand)* were also confirmed by Yesha in the running app.

| ID | Precondition | Steps / input | Expected result | Actual result | Pass? |
|---|---|---|---|---|---|
| TC-7.1 | Not logged in | Open `/sales/new` | Redirect to login | 302 → `/login` | ✅ |
| TC-7.2 | Cashier; Coke ₱75.50, Noodles ₱15 | Add Coke × 2, Noodles × 3 | Two lines; total ₱271.50 | As expected *(by hand: Sample Item × 1 + A × 2 = ₱26.19, screenshot S2)* | ✅ |
| TC-7.3 | Coke × 2 in basket | Add Coke × 1 again | One line, × 3 (not two lines) | One line, × 3 | ✅ |
| TC-7.4 | Noodles: 10 in stock | Add 3 → look at dropdown; add the other 7 | "7 available"; then Noodles leaves the dropdown; database stock stays 10 until the sale is completed | As expected *(by hand: A 39 / Sample Item 38 before; 37 / 37 available with A × 2 and Sample Item × 1 in the basket, screenshots S3–S4)* | ✅ (DEF-10) |
| TC-7.5 | Coke: 5 in stock, 3 in basket | Add Coke × 3 | "only 2 more can be added"; basket unchanged | As expected *(by hand: "Not enough stock for A: only 39 more can be added.", screenshot S5)* | ✅ |
| TC-7.6 | Cashier | Quantity 0, −2, `abc` | "Quantity must be a whole number of at least 1." | As expected | ✅ |
| TC-7.7 | Cashier | No product chosen; product ID 999 | "Please choose a product." | As expected | ✅ |
| TC-7.8 | Soap: 0 in stock | Look at dropdown; send a hand-made request for Soap × 1 | Not listed; request refused | Not listed; "only 0 more can be added" | ✅ |
| TC-7.9 | Two lines in basket | **Remove** one | Line gone; total updates | As expected | ✅ |
| TC-7.10 | Empty basket | **Complete Sale** | "The basket is empty." | As expected | ✅ |
| TC-7.11 | Basket total ₱226.50 | Cash ₱200; `abc`; nothing | "Cash received must be a number of at least ₱226.50."; no sale saved | As expected; 0 sales saved | ✅ |
| TC-7.12 | Noodles × 3 in basket; stock then lowered to 2 elsewhere | **Complete Sale** | "…no longer has enough stock"; nothing saved, no stock changed | As expected | ✅ |
| TC-7.13 | Basket Coke × 3 (₱226.50), Coke stock 5 | Cash ₱500 → **Complete Sale** | Receipt: number, date, "Served by", items, total ₱226.50, cash ₱500.00, change ₱273.50; Coke stock 5 → 2; basket emptied | As expected *(by hand: receipt #4 ₱12.40, ₱500 cash → ₱487.60 change; receipt #6 ₱3.10, ₱10 cash → ₱6.90 change; A's stock 39 → 37 after receipts #6 and #7, screenshots S8, S1)* | ✅ |
| TC-7.14 | Basket ₱15.00 | Cash exactly ₱15 | Change ₱0.00 | Change ₱0.00 | ✅ |
| TC-7.15 | Logged in as **admin** | Complete a sale | Allowed; "Served by: admin" | As expected | ✅ |
| TC-7.16 | Receipt for Coke at ₱75.50 exists | Change Coke's price, then delete Coke; reopen receipt | Receipt still shows "Coke 1.5L" at ₱75.50 | As expected | ✅ |
| TC-7.17 | Items in basket | Logout → log in as another user → New Sale | Basket empty | Empty | ✅ (DEF-09) |
| TC-7.18 | Two browsers logged in | Add items in one | Other browser's basket unaffected | Unaffected | ✅ |
| TC-7.19 | Basket ₱151.00 (browser) | Type cash 100, then 200 | Change box: "Not enough cash", then ₱49.00 | As expected; no script errors *(by hand: ₱3.10 total, cash 2 → "Not enough cash", cash 10 → ₱6.90, screenshots S6–S7)* | ✅ |
| TC-7.20 | Receipt open | **Print Receipt** → print preview | Only the receipt; no navbar or buttons | *(by hand, 2026-10-08)* Print preview of receipt #7 shows only the receipt card: no navigation bar, no Print/New Sale buttons (screenshot S9) | ✅ |
| TC-7.21 | Receipt #1–#3, made before cash was recorded | Open the receipt | No misleading cash amount | **v0.8.0:** "Cash ₱0.00 / Change ₱0.00" · **v0.8.1:** "Cash and change not recorded…"; #4 unchanged *(checked on a copy of the real database)* | ❌→✅ DEF-12 |
| TC-7.22 | Logged in | `/sales/999`; visit `/sales/complete` as a link (GET) | 404; 405 | 404; 405 | ✅ |
| TC-7.23 | Database from before v0.8.0's cash columns | **Complete Sale** | Sale saved | **Crash** "table sale has no column named cash_received" *(by hand)* → fixed by adding the columns; sale then saved | ❌→✅ DEF-11 |

#### Hand-test screenshots (v0.8.0, 2026-10-08, logged in as cashier)

| # | Test | Screenshot |
|---|---|---|
| S1 | TC-7.13: Products page after receipts #6 and #7, stock of A reduced to 37 | ![Products page with reduced stock](screenshots/v0.8.0_TC-7.13_stock_reduced.png) |
| S2 | TC-7.2: basket with two lines and total ₱26.19 | ![Basket with two lines](screenshots/v0.8.0_TC-7.2_basket.png) |
| S3 | TC-7.4: dropdown before adding to the basket (A 39, Sample Item 38 available) | ![Dropdown before basket](screenshots/v0.8.0_TC-7.4_before_basket.png) |
| S4 | TC-7.4: dropdown with items in the basket (both 37 available) | ![Dropdown showing available stock](screenshots/v0.8.0_TC-7.4_available.png) |
| S5 | TC-7.5: adding more than is available is refused | ![Not enough stock message](screenshots/v0.8.0_TC-7.5_stock_error.png) |
| S6 | TC-7.19: live change preview, ₱10 cash → ₱6.90 change | ![Change preview](screenshots/v0.8.0_TC-7.19_change_preview.png) |
| S7 | TC-7.19: cash lower than the total → "Not enough cash" | ![Not enough cash](screenshots/v0.8.0_TC-7.19_not_enough_cash.png) |
| S8 | TC-7.13: receipt #6 with cash and change | ![Receipt with cash and change](screenshots/v0.8.0_TC-7.13_receipt.png) |
| S9 | TC-7.20: print preview shows only the receipt | ![Print preview](screenshots/v0.8.0_TC-7.20_print_preview.png) |

> Still to capture: **TC-7.21 (v0.8.1)**, an old receipt (`/sales/1`) showing "Cash and change not recorded…"
> (file name `v0.8.1_TC-7.21_not_recorded.png`).

### Test summary (v0.7.0 → v0.8.1)

| Feature | Cases | ✅ Pass | ❌ Fail | ⚠️/⏳ Other |
|---|---|---|---|---|
| F1 View list | 3 | 3 | 0 | 0 |
| F2 Add | 6 | 2 → **6** | 4 → **0** | 0 |
| F3 Edit | 4 | 3 → **4** | 1 → **0** | 0 |
| F4 Delete | 4 | 3 | 0 | 1 |
| F5 Login/out | 8 | 7 | 0 | 1 |
| F6 Roles | 6 | 6 | 0 | 0 |
| F7 Process sale | 23 | 20 → **23** | 2 → **0** | 1 → **0** |
| **Total** | **54** | **44 → 52** | **7 → 0** | **3 → 2** |

*F1–F6: numbers shown as v0.7.0 → v0.7.1; on 2026-10-04 the full suite was re-run against the merged v0.7.1 code (`6043cdb`): all five failures now pass, and every test that passed before still passes. Checking that old features still work after a change is called **regression testing**. F7: numbers shown as first run → v0.8.1; on 2026-10-08 the F1–F6 suite was re-run against v0.8.0 and still passes.*

> Failing tests are **not** a bad thing to show in a report. Finding defects is the *purpose* of testing
> (Sommerville calls this **defect testing**). Showing a defect, its fix, and the test passing afterwards
> demonstrates the full cycle.

---

## 7. Defects found during testing

| ID | Severity | Description | Found by | Fix | Status / target |
|---|---|---|---|---|---|
| DEF-01 | **High** | Adding or editing a product with an SKU that already exists crashes the server (500) instead of showing a message | TC-2.3, TC-3.4 | Before saving, check `Product.query.filter_by(sku=...)` (excluding the product being edited); if found, show the form again with an error | ✅ Fixed v0.7.1 |
| DEF-02 | Medium | Non-number price/quantity crashes the server if the browser check is bypassed | TC-2.4 | Wrap `float()` / `int()` in `try/except ValueError` and show an error | ✅ Fixed v0.7.1 |
| DEF-03 | **High** | Negative price and negative quantity are accepted | TC-2.5 | Server check: `price >= 0`, `quantity >= 0`; also add `min="0"` to the form inputs | ✅ Fixed v0.7.1 |
| DEF-04 | Medium | Empty name/SKU accepted if the browser check is bypassed | TC-2.6 | Server check: `.strip()` the value and reject if empty | ✅ Fixed v0.7.1 |
| DEF-05 | Low | Prices display with a `$` sign, but the store is in the Philippines | Code review; confirmed by hand | Change the `$` in `products.html` to `₱` | ✅ Fixed v0.7.1 |
| DEF-06 | Low | After logging in, the user is always sent to Products instead of the page they first asked for | TC-5.8 | Read `request.args.get('next')` and redirect there (only if it is a page within this site) | later |
| DEF-07 | Security, before submission | `SECRET_KEY` is written directly in `app.py` and pushed to a public GitHub repository | Code review | Read it from an environment variable; keep a development fallback | v1.0.0 |
| DEF-08 | Security, before submission | Forms have no **CSRF protection** (CSRF = Cross-Site Request Forgery: another website tricking a logged-in user's browser into submitting a form) | Code review | Use Flask-WTF's `CSRFProtect` | v1.0.0 |
| DEF-09 | **High** | Logging out did not empty the basket, so on a shared counter computer the next user saw the previous cashier's items | Testing during development (TC-7.17) | `session.pop('basket', None)` in `logout()` | ✅ Fixed before v0.8.0 release |
| DEF-10 | Medium (usability) | The New Sale dropdown showed database stock, ignoring items already in the basket, so it looked like more could be sold | Hand testing by Yesha (TC-7.4) | Dropdown shows **available = stock − basket**; products fully in the basket are hidden; message says how many *more* can be added | ✅ Fixed before v0.8.0 merge |
| DEF-11 | **High** (deployment) | After upgrading the code, **Complete Sale** crashed: "table sale has no column named cash_received". `db.create_all()` creates missing *tables* but never adds *columns* to existing ones | Hand testing by Yesha (TC-7.23) | One-time **migration** script `add_cash_columns_once.py` (SQL `ALTER TABLE … ADD COLUMN`), database backed up first. The crashed sale saved nothing, because the save is one transaction | ✅ Fixed 2026-10-08 (database change, no code change) |
| DEF-12 | Low | Receipts for sales made before cash tracking showed "Cash ₱0.00 / Change ₱0.00", which looks like a real but impossible payment | Hand testing (TC-7.21) | `receipt.html` shows "Cash and change not recorded…" when cash is 0; no data invented | ✅ Fixed v0.8.1 (PR #3) |
| DEF-13 | Medium (reliability) | **Race condition:** two cashiers completing a sale for the last item at the same moment could both pass the stock check, leaving stock at −1 | Design review | **Atomic update**: subtract stock only *if enough is left*, in one database step; cancel the sale otherwise | Planned v0.8.2 |

> **How the v0.7.1 fix works.** All checks live in one function, `validate_product_form()` in `app.py`, used by
> both Add and Edit (the **DRY** principle: Don't Repeat Yourself). It returns either clean data or an error
> message; on error the form is shown again with a red Bootstrap alert and nothing touches the database.
> The browser checks (`required`, `min="0"`) are a convenience; the server check is the real protection.

> **Lesson from DEF-11 (worth a sentence in the report):** changing the *shape* of an existing database (adding a
> column) needs a **migration**: a small, deliberate script run once, after a backup. Real projects use a migration
> tool (e.g. Flask-Migrate) to keep these in order.

> **Known limitations after v0.8.1** (future increments): **cash only**, so GCash/card would need a payment-method choice,
> recorded but not connected to GCash itself, which needs a merchant account; **no refunds or voids**, to be handled by
> a *void with admin approval* flow (Completed → Void requested → Voided / Rejected), which also gives the state
> diagram; and **DEF-13**, the race condition.

> DEF-07 and DEF-08 are also good material for the professor's Lecture 11 items (*security terminology*
> and *vulnerability avoidance techniques*).

---

## 8. Use cases

A **use case** is one goal an actor achieves with the system ("Add product", "Log in"). Below: the full list,
then a tabular description of each, in the format of Sommerville's Lecture 5 p. 16 example
(*Actors / Description / Data / Stimulus / Response / Comments*).

### 8.1 Use case list

| ID | Use case | Primary actor | Status |
|---|---|---|---|
| UC-01 | View home page | Visitor | Built (v0.1.0) |
| UC-02 | Log in | Visitor → becomes User | Built (v0.6.0) |
| UC-03 | Log out | User | Built (v0.6.0) |
| UC-04 | View product list | User (Admin and Cashier) | Built (v0.3.0) |
| UC-05 | Add product | Admin | Built (v0.4.0) |
| UC-06 | Edit product | Admin | Built (v0.5.0) |
| UC-07 | Delete product | Admin | Built (v0.5.0) |
| UC-08 | Process sale | Cashier and Admin | Built (v0.8.0, fixed v0.8.1) |
| UC-09 | View low-stock warning | Admin | Planned (v0.9.0) |
| UC-10 | View sales report | Admin | Planned (v0.10.0) |

**Relationships between use cases** (needed for the diagram):
- UC-05, UC-06, UC-07 and UC-08 all **«include»** a hidden step, *Check permission (role)*. «include» means
  "always happens as part of". The `@admin_required` decorator in `app.py` is exactly this.
- UC-09 **«extend»s** UC-04: the low-stock warning appears on the product list *only when* some stock is low.
  «extend» means "sometimes adds extra behaviour, under a condition".

### 8.2 Tabular use case descriptions

**UC-02 Log in**

| | |
|---|---|
| **Actors** | Visitor (becomes Admin or Cashier) |
| **Description** | A person enters a username and password to gain access according to their role |
| **Data** | Username, password; stored User record (username, password hash, role) |
| **Stimulus** | The visitor submits the login form |
| **Response** | If the details match: a session starts and the user is sent to the product list, with their name and role in the navbar. If not: "Invalid username or password" is shown |
| **Comments** | The password is checked against a hash and never stored in plain text. The same message is shown for a wrong username or a wrong password, so attackers can't find out which usernames exist |

**UC-03 Log out**

| | |
|---|---|
| **Actors** | User (Admin or Cashier) |
| **Description** | The user ends their session |
| **Data** | The current session |
| **Stimulus** | The user clicks Logout |
| **Response** | The session ends and the user is sent to the home page; protected pages now require login again |
| **Comments** | Important on a shared counter computer, so the next person can't act under someone else's account |

**UC-04 View product list**

| | |
|---|---|
| **Actors** | Admin, Cashier |
| **Description** | Shows every product with its name, SKU, price, quantity and category |
| **Data** | All Product records |
| **Stimulus** | The user opens the Products page |
| **Response** | A table of products. Admins also see Add, Edit and Delete buttons; cashiers see "View only" |
| **Comments** | Not available to visitors who haven't logged in (they are sent to the login page) |

**UC-05 Add product**

| | |
|---|---|
| **Actors** | Admin |
| **Description** | Creates a new product record |
| **Data** | Name, SKU (unique), price, quantity, category (optional) |
| **Stimulus** | The admin submits the Add Product form |
| **Response** | The product is saved and the admin is returned to the updated list |
| **Comments** | Includes *Check permission*: cashiers get 403. Known defects: DEF-01, 02, 03, 04 |

**UC-06 Edit product**

| | |
|---|---|
| **Actors** | Admin |
| **Description** | Changes the details of an existing product |
| **Data** | Product ID; new name, SKU, price, quantity, category |
| **Stimulus** | The admin clicks Edit, changes the pre-filled form and clicks Save Changes |
| **Response** | The record is updated and the admin is returned to the list. An unknown ID gives 404 |
| **Comments** | Includes *Check permission*. Known defect: DEF-01 |

**UC-07 Delete product**

| | |
|---|---|
| **Actors** | Admin |
| **Description** | Permanently removes a product |
| **Data** | Product ID |
| **Stimulus** | The admin clicks Delete and confirms the pop-up |
| **Response** | The product is removed and the list is shown without it |
| **Comments** | Includes *Check permission*. Only works as a POST (form submission), not a link, for safety |

**UC-08 Process sale** *(built v0.8.0)*

| | |
|---|---|
| **Actors** | Cashier, Admin |
| **Description** | Records a customer purchase of one or more products, takes cash, gives change and lowers stock |
| **Data** | Basket (in the session): product IDs and quantities. Saved: **Sale** (date and time, user, total, cash received, change due) and one **SaleItem** per line (product, name and unit price *at the time of sale*, quantity) |
| **Stimulus** | The user adds items to the basket, enters the cash received and clicks Complete Sale |
| **Response** | Stock and cash are checked; the sale and its items are saved and stock reduced in **one transaction**; the basket is emptied; a printable receipt is shown. Invalid input → message, nothing saved |
| **Comments** | Includes *Check permission* (must be logged in). Stock can't go negative through normal use; simultaneous sales of the last item are DEF-13 (v0.8.2). Receipts keep a snapshot of names and prices, so old receipts stay correct |

**UC-09 View low-stock warning** *(planned)*

| | |
|---|---|
| **Actors** | Admin |
| **Description** | Highlights products whose quantity is at or below a threshold |
| **Data** | Product quantities; the threshold value (to decide: fixed, e.g. 5, or set per product?) |
| **Stimulus** | Opening the product list when at least one product is low |
| **Response** | Low products are highlighted and listed in a warning message |
| **Comments** | «extend»s UC-04 View product list |

**UC-10 View sales report** *(planned)*

| | |
|---|---|
| **Actors** | Admin |
| **Description** | Summarizes sales over a chosen period |
| **Data** | Sale records; start and end dates |
| **Stimulus** | The admin opens Sales Report and chooses a date range |
| **Response** | A list of sales with the items sold and total revenue |
| **Comments** | Depends on UC-08 existing first |

---

## 9. Guide: drawing the use case diagram

### 9.1 Which tool?

The professor says *"A professional drawing software is a must like a Microsoft Visio, or Microsoft Office."*

| Tool | Cost | Good for | Notes |
|---|---|---|---|
| **draw.io** (also called diagrams.net) — app.diagrams.net | Free, in the browser or as a desktop app | Every UML diagram the report needs | **Recommended.** Has a UML shape library and exports to PNG/PDF/SVG. Can import PlantUML text (see 9.3) |
| Microsoft Visio | Paid; sometimes free through a school Microsoft 365 account | Everything | The tool the professor names. Check whether your school email gives you access |
| Lucidchart | Free plan limits how many diagrams you can make | Everything | Easy, but the free plan may run out with 25+ diagrams |
| PlantUML (planttext.com) | Free | Quick drafts from text | You type a description and it draws the diagram. Less control over the layout |

> **Before relying on draw.io, ask the professor (on Discord) whether it counts as "professional drawing
> software".** It is widely used in industry, but he names Visio and Office specifically, so a one-line question avoids
> losing marks.

### 9.2 The symbols (UML use case notation)

| Symbol | Meaning | In this project |
|---|---|---|
| Stick figure | **Actor**: someone outside the system | Visitor, User, Admin, Cashier |
| Oval | **Use case**: one goal | "Add product" |
| Big rectangle around the ovals | **System boundary**: what is inside the software | Labelled "Inventory & POS System" |
| Plain line actor → oval | **Association**: this actor performs this use case | Admin — Add product |
| Line with a hollow triangle head | **Generalization**: "is a kind of" | Admin ▷ User, Cashier ▷ User |
| Dashed arrow labelled «include» | Always part of | Add product ··> Check permission |
| Dashed arrow labelled «extend» | Sometimes adds to, under a condition | Low-stock warning ··> View product list |

### 9.3 Fastest way: import the ready-made text into draw.io

A file **`diagrams/use_case_diagram.puml`** is included in your project folder. It describes the diagram in
PlantUML text.

1. Go to **app.diagrams.net** → choose where to save (Device is fine) → **Create New Diagram** → **Blank Diagram**.
2. In the top menu: **Arrange → Insert → Advanced → PlantUML…**
3. Open `use_case_diagram.puml` in VS Code, select everything (**Ctrl + A**), copy (**Ctrl + C**) and paste it into the box.
4. Click **Insert**. The diagram appears.
5. Check it matches Section 8 and adjust anything you've decided differently (for example who can process a sale).
6. Export: **File → Export as → PNG**, set zoom to **200%** or more, leave **Transparent background** *unticked*
   (a white background prints and reads better), and save it into the `diagrams/` folder.

> A preview image made from the same text is already in your folder: **`diagrams/use_case_diagram_draft.png`**.
> Use it to check your version, but draw your own for the report.

> **Catch:** a diagram imported from PlantUML in draw.io is inserted as one *picture*, so you can't move single shapes. That is
> fine for a first draft. For the final report, drawing it by hand (9.4) gives a cleaner layout, and you
> learn the notation properly, which helps when the professor asks about it in your video.

### 9.4 Drawing it by hand in draw.io (step by step)

1. **Open a blank diagram** as in 9.3, step 1.
2. **Turn on the UML shapes:** at the bottom of the left panel click **+ More Shapes** → tick **UML** → **Apply**.
3. **System boundary:** drag a plain **Rectangle** (General section) onto the page and make it large. Double-click it
   and type `Inventory & POS System`. Then use the top-right **Arrange** tab and **Edit Style** to set
   `verticalAlign=top;` so the title sits at the top.
4. **Use cases:** from the **UML** section drag an **Ellipse** (oval) inside the rectangle. Double-click and type
   `Log in`. Copy and paste (**Ctrl + D** duplicates) to make one oval per use case in Section 8.1. Planned ones too: type
   e.g. `Process sale (planned)` or give them a dashed outline so you can tell them apart.
5. **Actors:** drag the **Actor** (stick figure) shape *outside* the rectangle. Make four: **Visitor** and **User** on
   the left, **Admin** and **Cashier** below User.
6. **Associations:** hover over an actor until blue arrows appear, then drag from it to an oval. Select the line → in the right
   panel set the **line end** to *none*, so it's a plain line. Connect:
   - Visitor — View home page, Log in
   - User — Log out, View product list
   - Admin — Add product, Edit product, Delete product, View low-stock warning, View sales report
   - Cashier — Process sale
7. **Generalization:** draw a line from **Admin** to **User**, then set its **line end** to the *hollow triangle*
   (called "block" with fill off). Do the same for **Cashier → User**. The triangle points at the *parent* (User).
8. **«include»:** add an oval `Check permission`. Draw lines from Add, Edit, Delete and Process sale **to** it,
   set each line to **dashed** with an **open arrow** end, and double-click the line to type `«include»`.
   *(Type the « » marks by copy-paste, or just write <<include>>.)*
9. **«extend»:** dashed open arrow **from** `View low-stock warning` **to** `View product list`, labelled `«extend»`.
10. **Tidy up:** select everything → **Arrange → Align** and **Distribute** so ovals line up. Avoid crossing lines
    by moving actors closer to their use cases.
11. **Save** as `use_case_diagram.drawio` (so you can edit it later) **and** export a PNG at 200% for the report.

### 9.5 What else the professor wants about use cases (from Section B)

| Item | Lecture ref | What to make | Status |
|---|---|---|---|
| Use case diagram of all use cases | L4 p. 65 | The one above | Guide ready |
| Every use case's UML diagram | L5 p. 15 | One small diagram per use case: one actor + one oval (+ include/extend) | To do |
| Tabular description of use cases | L5 p. 16 | Section 8.2 | ✅ Drafted |
| Each agent's use cases | L5 p. 17 | One diagram per actor: Admin's use cases, Cashier's use cases, Visitor's | To do |

---

## 10. Report checklist (professor's Section B)

Status key: ✅ drafted here · 🟡 partly · ⬜ not started

| # | Item | Status |
|---|---|---|
| 1 | Process model and why (L2) | ✅ §2 |
| 2 | Full story of each feature (L3 p. 21) | ✅ §5 (F7–F9 to finish after building) |
| 3 | Detailed test case of each feature (L3 p. 31) | ✅ §6 for F1–F6 |
| 4 | Requirements definition: user and system requirements (L4 p. 7) | ⬜ |
| 5 | Nonfunctional requirements (L4 p. 18) | ⬜ |
| 6 | Nonfunctional requirements metrics table (L4 p. 21) | ⬜ |
| 7 | Requirements of each part (L4 p. 39) | ⬜ |
| 8 | Structured requirements of each part (L4 p. 42–43) | ⬜ |
| 9 | Tabular computation of each function (L4 p. 45) | ⬜ (the sale total / stock update in F7 is the obvious example) |
| 10 | Detailed scenarios (L4 p. 62–63) | 🟡 the stories in §5 are a starting point |
| 11 | Use case diagram (L4 p. 65) | 🟡 §9 guide + `.puml` file |
| 12 | Context UML diagram (L5 p. 10) | ⬜ |
| 13 | Process model UML diagram (L5 p. 12) | ⬜ |
| 14 | Every use case's UML diagram (L5 p. 15) | ⬜ |
| 15 | Tabular use case descriptions (L5 p. 16) | ✅ §8.2 |
| 16 | Each agent's use cases (L5 p. 17) | ⬜ |
| 17 | Sequence diagrams of every action (L5 p. 19–20) | ⬜ |
| 18 | Class associations (L5 p. 23–24) | ⬜ |
| 19 | Class models (L5 p. 25) | ⬜ |
| 20 | Generalization hierarchy (L5 p. 30–31) | ⬜ |
| 21 | Aggregation associations (L5 p. 33) | ⬜ (Sale ◇— SaleItem will be the example) |
| 22 | Activity model (L5 p. 36) | ⬜ |
| 23 | Application processes (L5 p. 37) | ⬜ |
| 24 | State diagram (L5 p. 40) | ⬜ |
| 25 | Structured forms of states (L5 p. 41–42) | ⬜ |
| 26 | Software architecture (L6 p. 42, 49) | ⬜ (this app follows MVC: Model–View–Controller) |
| 27 | Context diagram (L7 p. 9) | ⬜ |
| 28 | High-level architecture (L7 p. 13) | ⬜ |
| 29 | All object classes (L7 p. 19) | ⬜ |
| 30 | Detailed usage scenario (L8 p. 53) | ⬜ |
| 31 | Reliability terminology (L11 p. 25) | ⬜ |
| 32 | Safety terminology (L11 p. 35) | ⬜ |
| 33 | Security terminology (L11 p. 42) | ⬜ (use DEF-07, DEF-08, password hashing) |
| 34 | Vulnerability avoidance techniques (L11 p. 45) | 🟡 server-side validation, hashing, POST-only delete, 403 checks already exist |
| 35 | Risk classification table (L12 p. 15) | ⬜ |
| 36 | Software fault tree (L12 p. 18) | ⬜ |
| 37 | Safety requirements (L12 p. 23) | ⬜ |
| 38 | Functional reliability requirements (L12 p. 39) | ⬜ |
| 39 | Threat and control analysis (L12 p. 46) | ⬜ |

**Other submission requirements (Section C/D):**
- ⬜ Code comments explaining every block (currently there are none)
- 🟡 Use branches and pull requests (required: "commit, push, merge, pull request"): first one done, PR #1 for v0.7.1; keep using one branch + PR per feature
- ⬜ README describing the project and how to run it
- ⬜ 1080p OBS video with microphone, explaining every piece of code and demonstrating every feature
- ⬜ Word/PDF document with screenshots of your comments on all 14 lecture videos (**missing it = Fail**)
- ⬜ Video link saved as text in the project folder; whole project zipped to Google Drive; link emailed to the professor
