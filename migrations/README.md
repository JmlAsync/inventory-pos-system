# Database migrations (v0.23.0)

Every change to the database's shape is a numbered script in `versions/`: `0001`, `0002`, `0003`… Alembic
(through Flask-Migrate) runs the ones a database hasn't had yet, in order, and records the last one in a small
table called `alembic_version`. Why this way: `docs/decisions.md`, DEC-023. The rule: `AGENTS.md`, I5.

**You don't run anything by hand.** `python app.py` and `python seed_demo_data.py` call `upgrade_database()`,
which backs up the database first (`instance/inventory_backup_<date>_before_<number>.db`) and then runs any
missing migrations.

## Adding a change (for developers)

1. Change the model in `models.py`.
2. Let Alembic draft the script, with the next number:
   `flask --app app db migrate --rev-id 0002 -m "what changed (vX.Y.Z)"`
3. Read the draft in `versions/` and fix it by hand: give new `NOT NULL` columns a `server_default`, fill in
   existing rows if needed, and write a `downgrade()` that undoes it (or refuses, with a reason, if undoing would
   lose data).
4. Run `python tests/run_tests.py`. `test_migrations.py` fails if `models.py` and the migrations don't match.

`0001` is special: it brings **any** older database (made before v0.23.0, or empty) to the v0.22.0 shape. It
only creates what is missing, so it is safe on every database, and it can't be undone.
