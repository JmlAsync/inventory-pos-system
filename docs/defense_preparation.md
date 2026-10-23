# Preparing for the one-to-one session with the professor

A casual "show it and answer questions" session. This page has four parts:

1. [Before you go](#1-before-you-go) (5-minute checklist)
2. [A 10-minute demo script](#2-a-10-minute-demo-script)
3. [Questions to ask the professor](#3-questions-to-ask-the-professor)
4. [Questions the professor may ask you](#4-questions-the-professor-may-ask-you), with short answers

Facts below come from `project_documentation_draft.md` (the report), `AGENTS.md` and the code.
Section numbers like "§7" mean the report.

---

## 1. Before you go

- [ ] `python tests/run_tests.py` ends with **"All 22 passed"** (it did on v0.21.0, 2026-10-23).
- [ ] `python seed_demo_data.py --fresh` so the demo starts clean (your old database is backed up first).
- [ ] `python app.py`, open http://127.0.0.1:5000, log in as `admin` / `admin123` and `cashier` / `cashier123`.
- [ ] Open the report in a second window (`project_documentation_draft.md`, §3, §7, §10, §12–§14).
- [ ] Have the diagrams ready (`diagrams/`), and the GitHub page with pull requests and tags.
- [ ] Be honest about the three open submission items in §10: the OBS video, the lecture-video comments
      document (**missing it = Fail**) and the Drive link. Know your status on each before you walk in.

## 2. A 10-minute demo script

| Min | Do this | Say this |
|---|---|---|
| 0–1 | Home page as admin | "A café inventory and point-of-sale system. Flask, SQLite, works offline." |
| 1–3 | Log in as cashier, **New Sale**: tap + Iced, + Hot, change with − / +, choose add-ons | "Tiles for speed; a basket held in the session." |
| 3–4 | Pay cash (quick-cash buttons, change shown), complete, show the receipt | "The receipt keeps its own copy of name and price (rule I3), so it never changes." |
| 4–5 | Type `/products/add` as cashier: **403** page | "Hiding a button is not enough. The server refuses (rule S2)." |
| 5–6 | Log in as admin, **Ingredients**: stock bars, the sale used up ingredients, history | "Each sale subtracts the recipe's ingredients and writes a history line (rule I7)." |
| 6–7 | **Sales report** for the week | "Revenue, top products, cash vs GCash." |
| 7–8 | Switch to dark theme, tap **Fold menu**; shrink the browser to phone width | "Same pages, light/dark, phone-friendly." |
| 8–9 | Terminal: `python tests/run_tests.py` | "22 test files, plus a contract check that enforces the rules on every pull request." |
| 9–10 | GitHub: pull requests, tags, defects list (§7) | "Incremental model: every tag is a working version. 58 defects found and fixed, each with a test." |

If something breaks live: say what you expected, show the test that covers it, move on. Calm beats perfect.

---

## 3. Questions to ask the professor

Asking good questions shows you care about the grade *and* the engineering. Pick the ones that fit.

### About grading and what is still needed
1. Which parts of the Section B list (items 1–39) do you consider the most important for the grade?
2. The report is currently a Markdown draft. Is it fine to convert it to Word or PDF as-is, or do you want a particular template or page limit?
3. For the OBS video: is there a length limit, and do you want every function walked through, or the main files and every feature?
4. For the lecture-video comments document: what format counts (screenshots only, or a short write-up each)? Is there a deadline separate from the project?
5. Is a Git history with 66 pull requests and tags enough for the "commit, push, merge, pull request" requirement, or do you want something extra?
6. How should I submit: Google Drive link by email, and should the repository be public or private?
7. Is the grade weighted more on the working system, the documentation, or the video?

### About scope and what the system lacks
8. I deliberately left out refunds/voids, a Philippine senior/PWD discount and X/Z readings (§7 limitations). Would you expect any of them in a final project, or is documenting them as future work enough?
9. Is it acceptable that GCash is recorded but not verified, since checking needs a merchant account?
10. The system is not a BIR-accredited POS. Should the report say more about that, or is the note enough?

### About engineering practice
11. I used incremental development with a stabilization rule (fix defects before new features). Does that match what you want to see for the process-model item?
12. Which would you value more for a project this size: more automated tests, or browser tests (Playwright) that click through the pages?
13. Money is stored as `Float` rounded to centavos. Would you expect `Decimal` or whole centavos for a final project?
14. SQLite allows one writer at a time. Do you consider that fine for the "small café" scope?
15. Would you want to see this move to a server database or a hosted deployment in Software Engineering 2?

### About feedback
16. If you had one week to improve one thing in this project, what would it be?
17. Which feature or part of the report was the weakest to you?
18. Is there anything in the UML diagrams (use case, sequence, class, state) that you would draw differently?

---

## 4. Questions the professor may ask you

Short answers you can say out loud. Know *why*, not just *what*.

### A. The project and the process
1. **What does the system do and who uses it?**
   A café inventory and POS. Admins manage products, servings (Hot/Iced), add-ons, ingredients and recipes and see reports. Cashiers sell (cash or GCash) and print receipts. (§1, §4)
2. **Which process model did you use and why?**
   Incremental. Each tag (v0.1.0 … v0.20.5) is a working version; I specified, built and tested a small piece at a time. Waterfall needs all requirements up front, and reuse-oriented did not fit a small custom app. (§2)
3. **What is the stabilization rule?**
   If a version has a known defect, release a patch (vX.Y.1) before starting the next feature. It stops defects piling up. (AGENTS.md C2)
4. **Why one file `app.py`?**
   Course scope: one file is easier to follow for a beginner. The cost is that it is long (about 1,600 lines); the next step would be Flask blueprints. (AGENTS.md §2)
5. **How did you manage versions?**
   One branch and one pull request per change, merged to `main`, then an annotated tag. Checks run on every pull request. (AGENTS.md W1–W6)
6. **Who wrote the code?**
   Be straight: an AI assistant (Claude) implemented much of it at my request because of the finals time constraint (stated in the report header). My part was deciding requirements, reviewing, running and checking it, and being able to explain it. Know how each feature works so you can show you understand it.

### B. Requirements and design
7. **Functional vs non-functional requirements — give examples.**
   Functional: "the cashier can complete a sale and print a receipt". Non-functional: works offline, a page loads quickly, passwords are hashed. (§11)
8. **Explain your architecture.**
   MVC and layered: templates (view), routes in `app.py` (controller), `models.py` (model), SQLite below. (§13.1)
9. **Show or explain the class model.**
   Product, User, LoginSession, Sale, SaleItem, MenuOption, Ingredient, RecipeItem, IngredientMovement. A Sale has many SaleItems (aggregation); a Product has a recipe made of RecipeItems that point at Ingredients. (§12.6, §13.4)
10. **Why does SaleItem copy the product name and price?**
    So an old receipt never changes if the product is renamed or repriced (rule I3).
11. **Why are ingredients tracked separately from product stock?**
    A drink is made of ingredients. Products with a recipe show "how many can still be made", computed from ingredients; products without one use their own quantity. (F16)
12. **Walk me through selling one drink.**
    Cashier taps + Iced, which adds a line to the basket in the session. At payment the server re-checks every value, then in **one transaction** inserts the Sale and SaleItems and subtracts stock/ingredients with conditional updates. If any update changes 0 rows, it rolls everything back. (§13.5, I1, I2)

### C. Data integrity
13. **What if two cashiers sell the last cup at the same time?**
    Stock is subtracted with `UPDATE … SET quantity = quantity - n WHERE quantity >= n`. The second update changes 0 rows, so that sale is rolled back with a friendly message. There is a race test (`test_race.py`). Reading, checking in Python, then writing would oversell (DEF in §7).
14. **What if someone double-clicks "Complete sale"?**
    A one-time sale ticket per basket (v0.20.4, DEF-48) with a unique index, so the same basket cannot become two receipts.
15. **How does the database get new columns without losing data?**
    `NEW_COLUMNS` and `upgrade_database()` at start-up add missing columns. A real project would use a migration tool such as Flask-Migrate. (DEF-11, I5)
16. **Why can't a sold product be deleted?**
    SQLite may reuse the id of a deleted product, so a new product would inherit old sales and recipes. You set its quantity to 0 instead. (I4, DEF in §7)
17. **Why not store money as a float?**
    Floats can drift (0.1 + 0.2). Amounts are rounded to centavos, which is fine at this scale, but `Decimal` or integer centavos would be better. It is listed under known limitations.

### D. Security
18. **How do you stop a cashier opening an admin page?**
    `@login_required` then `@admin_required` on every admin route; the server returns 403 even if the address is typed. `check_contract.py` verifies this on every route (S1, S2).
19. **What is CSRF and how do you prevent it?**
    Another website tricking your logged-in browser into sending a request. Every POST form carries a secret token that `check_csrf_token()` verifies, and cookies are `SameSite=Lax`. Delete and log out are POST buttons, never links. (S3, S6)
20. **How are passwords stored?**
    Only as hashes (`generate_password_hash`), never logged or shown. (S9)
21. **How do you avoid SQL injection?**
    SQLAlchemy queries, or `db.text()` with `:named` parameters. Never joining text with user input. A security audit with 6,417 hostile requests found none. (S5, `docs/security_audit_2026-10-11.md`)
22. **What stops password guessing?**
    5 wrong tries per username and computer, then a 5-minute wait (S10). The counter lives in memory, so a restart clears it; that is a known limitation.
23. **What happens to a stolen cookie after logout?**
    Before v0.20.3 it kept working. Now each login has a row in `LoginSession`; log out deletes it, so a copied cookie is dead (DEF-51).
24. **How do you check uploaded pictures?**
    By their first bytes (PNG, JPG, WebP), at most 2 MB, saved under a random name. The uploaded file name is never used. (S8)
25. **Is it safe to put on the internet?**
    Not yet. It is designed for a local shop computer. Missing: HTTPS, a Content-Security-Policy header, password reset, a server database. The audit lists risks for going online.

### E. Testing and quality
26. **How did you test it?**
    22 automated test files in `tests/` (standard library only) run in a temporary copy so the real database is never touched, plus a contract check for the project rules. Browser checks were done by hand and recorded with screenshots. 262 documented test cases in §6. (T1–T4)
27. **What is regression testing?**
    Re-running old tests after a change to be sure old features still work.
28. **Show a defect and how you fixed it.**
    Pick one you know well, for example DEF-58: a CSS class name shared between pages made the Ingredients warn tick shrink. Fix: rename the New Sale classes and add a test that fails if any are shared again. Rule C3: every fix has a test that failed before and passes after. (§7)
29. **How many defects?** 58 recorded, all fixed. Finding them is the purpose of testing (defect testing).
30. **What does your test not cover?**
    Real-browser clicking is not automated (it would need Playwright), and GCash payment is only recorded, not verified.

### F. Limits and future work
31. **What would you add next?**
    Void/refund with admin approval, an X/Z reading, senior/PWD discount, password reset by admin, per-product low-stock thresholds, product archive, Decimal money.
32. **Why is it not a legal POS in the Philippines?**
    A machine issuing official invoices needs BIR-accredited software and a Permit to Use. These receipts are order slips for the shop's own records. (§7 limitations)
33. **How would it scale to many tills?**
    SQLite allows one writer at a time. Move to PostgreSQL/MySQL, add a proper migration tool, and run behind a production server.
34. **Why does it work offline?**
    Bootstrap, icons and the Inter font are stored in `static/vendor/`; nothing loads from the internet (D2, v0.19.4).

### G. Curveballs
35. **Open `app.py` and explain this function.** Pick `complete_sale`, `login` and `validate_product_form` and re-read their comments tonight.
36. **Change X live** (for example the low-stock threshold). It is `LOW_STOCK_THRESHOLD` in `app.py`; know where constants live.
37. **What was the hardest part?** Prepare a real answer, for example overselling under concurrent sales, or keeping receipts immutable.
38. **What would you do differently?** For example start the tests and the rules file earlier, and split `app.py` into blueprints.
39. **What did you learn?** One concrete thing from each of: process, testing, security.

---

## Last-minute tips

- Answer the question asked, then stop. "I don't know, but here is where I would look" is a good answer.
- Never claim something is done when it is not; the report already lists limitations honestly, and that honesty is a strength.
- Use the report as evidence: "that is in §7, DEF-48" beats explaining from memory.
