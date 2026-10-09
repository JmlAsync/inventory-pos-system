"""Shared helpers for the automated tests (v0.19.0).

Every test file in this folder is a plain Python script. It is run by tests/run_tests.py
inside a TEMPORARY COPY of the project, so it can delete and rebuild the database freely
without touching your real instance/ folder or uploaded pictures.

A test file:
  1. imports check() and finish() from here,
  2. calls check('what is being tested', condition) many times,
  3. ends with finish('SUITE NAME'), which prints PASS/FAIL and sets the exit code
     (0 = everything passed, 1 = something failed) so run_tests.py and GitHub can see it.
"""
import os
import sys
import logging
import http.cookiejar
import urllib.parse
import urllib.request
import urllib.error

# Safety: a test deletes and rebuilds the database, so it may only run inside the temporary
# copy made by run_tests.py, never in your real project folder.
if os.environ.get('POS_TEST_COPY') != '1':
    sys.exit('Run the tests with:  python tests/run_tests.py   (it protects your real database).')

# The project copy is the current folder: make "from app import app" work.
sys.path.insert(0, os.getcwd())
# Hide Flask's request log so only PASS/FAIL lines are printed.
logging.disable(logging.CRITICAL)

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
_failed = []
_passed = [0]


def check(name, ok):
    """Record one test: print PASS or FAIL with its name."""
    if ok:
        _passed[0] += 1
        print('  PASS  ' + name)
    else:
        _failed.append(name)
        print('  FAIL  ' + name)


def finish(suite):
    """Print the suite result and exit with 0 (all passed) or 1 (something failed)."""
    if _failed:
        print(f'{suite} FAIL ({len(_failed)} failed, {_passed[0]} passed)')
        sys.exit(1)
    print(f'{suite} PASS ({_passed[0]} checks)')
    sys.exit(0)


def fixture(name):
    """Bytes of a file in tests/fixtures/."""
    with open(os.path.join(FIXTURES, name), 'rb') as f:
        return f.read()


def text(response):
    """The HTML of a Flask test-client response."""
    return response.get_data(as_text=True)


def make_users(db, User, admin=('admin', 'admin123'), cashier=('cashier', 'cashier123')):
    """Add one admin and one cashier (passwords are hashed, like the real app)."""
    from werkzeug.security import generate_password_hash
    db.session.add_all([User(username=admin[0], password_hash=generate_password_hash(admin[1]), role='admin'),
                        User(username=cashier[0], password_hash=generate_password_hash(cashier[1]), role='cashier')])
    db.session.commit()


def logged_in(app, username, password):
    """A Flask test client (a pretend browser) that is already logged in."""
    client = app.test_client()
    client.post('/login', data={'username': username, 'password': password})
    return client


class Browser:
    """A tiny real-HTTP browser (standard library only) for tests that need a running
    server with many cashiers at the same moment. It keeps its own login cookie."""
    def __init__(self, base):
        self.base = base
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
                                                  _NoRedirect())

    def post(self, path, data):
        body = urllib.parse.urlencode(data).encode()
        try:
            with self.opener.open(self.base + path, data=body, timeout=30) as r:
                return r.status
        except urllib.error.HTTPError as e:   # 3xx (not followed), 4xx and 5xx arrive here
            return e.code


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Do not follow redirects, so a completed sale shows up as 302."""
    def redirect_request(self, *args, **kwargs):
        return None


def start_server(app):
    """Run the app on a free port in a background thread; return (base_url, server)."""
    import threading
    from werkzeug.serving import make_server
    server = make_server('127.0.0.1', 0, app, threaded=True)   # port 0 = any free port
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f'http://127.0.0.1:{server.server_port}', server
