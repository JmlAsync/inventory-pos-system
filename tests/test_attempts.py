"""Wrong passwords counted in the database (v0.26.0, DEC-028, audit R2 and A7), test cases TC-33.x:
migration 0004, the limit surviving a restart (DEF-70), Change password limited too (DEF-69), keys that never
hold what was typed, and tries arriving at the same moment."""
import os
import subprocess
import sys
import threading
from datetime import timedelta
from helpers import check, finish, make_users, text, Browser, start_server

from app import app, upgrade_database, MIGRATIONS_FOLDER
from models import db, User, LoginAttempt
from alembic import command

app.config['CSRF_ENABLED'] = False
app.config['PROPAGATE_EXCEPTIONS'] = False


def tables():
    return set(db.inspect(db.engine).get_table_names())


# ---- TC-33.1 migration 0004 adds the login_attempt table (with its two indexes) and can be undone
with app.app_context():
    db.drop_all(); upgrade_database()
    config = app.extensions['migrate'].migrate.get_config(MIGRATIONS_FOLDER)
    command.downgrade(config, '0003')
    check('TC-33.1 before 0004 there is no login_attempt table', 'login_attempt' not in tables())
    command.upgrade(config, 'head')
    indexes = {i['name'] for i in db.inspect(db.engine).get_indexes('login_attempt')}
    check('TC-33.1 migration 0004 adds login_attempt, indexed by key and by time',
          'login_attempt' in tables() and {'ix_login_attempt_key', 'ix_login_attempt_created_at'} <= indexes)
    command.downgrade(config, '0003'); db.session.remove()
    check('TC-33.1 undoing 0004 removes the table again', 'login_attempt' not in tables())
    command.upgrade(config, 'head')
    make_users(db, User)


def login(client, username, password):
    return client.post('/login', data={'username': username, 'password': password})


def rows():
    with app.app_context():
        return LoginAttempt.query.all()


def clear_tries():
    with app.app_context():
        LoginAttempt.query.delete(); db.session.commit()


def age_tries(minutes):
    with app.app_context():
        for row in LoginAttempt.query:
            row.created_at -= timedelta(minutes=minutes)
        db.session.commit()


# ---- TC-33.2 the login limit is unchanged for the user: 5 wrong, then even the right password waits
c = app.test_client()
for i in range(5):
    login(c, 'cashier', f'wrong{i}')
check('TC-33.2 each wrong password is a row in login_attempt', len(rows()) == 5)
check('TC-33.2 the 6th try within 5 minutes is refused (429), even with the right password',
      login(c, 'cashier', 'cashier123').status_code == 429)
for _ in range(3):
    login(c, 'cashier', 'wrong')
check('TC-33.2 a refused try is not kept, so waiting really ends the lock (still 5 rows)', len(rows()) == 5)
age_tries(6)
check('TC-33.2 after 5 minutes the right password works', login(c, 'cashier', 'cashier123').status_code == 302)
check('TC-33.2 ... and the right password clears the count (old rows tidied, its own removed)', rows() == [])

# ---- TC-33.3 the table never holds what was typed
login(app.test_client(), 'kape-2026-secret', 'wrong')   # a password typed into the username box by mistake
with app.app_context():
    stored = [(row.key, str(row.created_at)) for row in LoginAttempt.query]
    with app.test_request_context(environ_base={'REMOTE_ADDR': '127.0.0.1'}):
        from blueprints.accounts import attempt_key
        expected = attempt_key('login', 'kape-2026-secret', '127.0.0.1')
check('TC-33.3 the key is a 64-character hash, not the username typed',
      len(stored) == 1 and len(stored[0][0]) == 64 and 'kape' not in ''.join(stored[0]))
check('TC-33.3 ... the keyed hash of "login | username | computer"', stored[0][0] == expected)
clear_tries()

# ---- TC-33.4 (DEF-70, audit R2) the limit survives a restart: a new process sees the earlier wrong passwords
TRY = """
import logging, sys; logging.disable(50)
from app import app
app.config['CSRF_ENABLED'] = False
c = app.test_client()
for password in sys.argv[1:]:
    print(c.post('/login', data={'username': 'cashier', 'password': password}).status_code)
"""
first = subprocess.run([sys.executable, '-c', TRY, 'w1', 'w2', 'w3', 'w4', 'w5'], capture_output=True, text=True)
second = subprocess.run([sys.executable, '-c', TRY, 'cashier123'], capture_output=True, text=True)
check('TC-33.4 5 wrong passwords in one run of the app', first.stdout.split() == ['200'] * 5)
check('TC-33.4 after a restart the 6th try is still refused (DEF-70; it used to be forgotten)',
      second.stdout.split() == ['429'])
clear_tries()

# ---- TC-33.5 Change password has the same limit (DEF-69, audit A7)
cashier = app.test_client(); login(cashier, 'cashier', 'cashier123')


def change(client, current, new='Kape-sa-umaga-1', confirm=None):
    r = client.post('/profile/password', data={'current_password': current, 'new_password': new,
                                               'confirm_password': new if confirm is None else confirm},
                    follow_redirects=True)
    return text(r)


answers = [change(cashier, f'guess{i}') for i in range(5)]
check('TC-33.5 5 wrong current passwords: each says it is wrong', all('Current password is wrong' in a for a in answers))
locked = change(cashier, 'cashier123')
check('TC-33.5 the 6th try is refused even with the right current password (DEF-69; it used to change it)',
      'Too many wrong current passwords' in locked and 'Password changed' not in locked)
check('TC-33.5 ... and the password was not changed', login(app.test_client(), 'cashier', 'cashier123').status_code == 302)
admin = app.test_client(); login(admin, 'admin', 'admin123')
check('TC-33.5 another user is not affected', 'do not match' in change(admin, 'admin123', 'Kape-sa-umaga-1', 'other'))
age_tries(6)
check('TC-33.5 after 5 minutes the right current password works again',
      'do not match' in change(cashier, 'cashier123', 'Kape-sa-umaga-1', 'other'))
answers = [change(cashier, f'guess{i}') for i in range(4)] + [change(cashier, 'cashier123', 'x', 'y')]
answers += [change(cashier, f'again{i}') for i in range(5)]
check('TC-33.5 the right current password resets the count (5 more wrong ones are all checked)',
      all('Current password is wrong' in a for a in answers[5:]))
check('TC-33.5 Change password tries do not lock the login page', login(app.test_client(), 'cashier', 'cashier123').status_code == 302)
clear_tries()

# ---- TC-33.6 tries at the same moment: recorded first, then counted, so no more than 5 get checked
base, server = start_server(app)
barrier = threading.Barrier(10)
statuses = []


def one_try():
    browser = Browser(base)
    barrier.wait()
    statuses.append(browser.post('/login', {'username': 'admin', 'password': 'wrong'}))


threads = [threading.Thread(target=one_try) for _ in range(10)]
for t in threads: t.start()
for t in threads: t.join()
server.shutdown()
check(f'TC-33.6 10 wrong passwords at the same moment: at most 5 are checked, the rest wait ({sorted(statuses)})',
      len(statuses) == 10 and statuses.count(200) <= 5 and statuses.count(429) >= 5 and set(statuses) <= {200, 429})
check('TC-33.6 ... and at most 5 tries are kept', len(rows()) <= 5)

finish('ATTEMPTS')
