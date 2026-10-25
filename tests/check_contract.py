"""Checks the rules in AGENTS.md that a program can check (v0.19.0).

Run:  python tests/check_contract.py      (also run first by tests/run_tests.py and on every pull request)

It only READS the project files; it changes nothing. Each rule prints PASS or FAIL with the
file and line to fix. If you deliberately change a rule, change AGENTS.md AND this file together.
"""
import ast
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- Every page (route) must be listed here, so a new page is a deliberate decision (AGENTS.md rule S1).
PUBLIC_ROUTES = {'/', '/login',                       # anyone, even when not logged in
                 '/signup/<token>', '/forgot-password', '/forgot-password/code',   # v0.27.0 (owner's decision, DEC-029)
                 '/verify', '/verify/resend',          # v0.28.0, within 5 minutes of a right password (DEC-030)
                 '/login/google', '/auth/google/callback'}   # v0.29.0, owner's decision (DEC-031)
ADMIN_ROUTES = {                                       # @login_required AND @admin_required
    '/products/add', '/products/edit/<int:product_id>', '/products/delete/<int:product_id>',
    '/options', '/ingredients', '/ingredients/<int:ingredient_id>', '/ingredients/history',
    '/recipe/<kind>/<int:item_id>', '/reports/sales',
    '/settings/shop',                                  # shop details on receipts (v0.22.0)
    '/settings/email',                                 # email settings and a test message (v0.26.0)
    '/admin/users', '/admin/users/invite', '/admin/users/<int:user_id>/role',   # Users and invitations (v0.27.0)
    '/admin/users/<int:user_id>/active', '/admin/users/<int:user_id>/require-password',
    '/admin/users/<int:user_id>/may-invite', '/admin/invitations/<int:invitation_id>/resend',
    '/admin/invitations/<int:invitation_id>/cancel', '/admin/audit',
    '/admin/users/<int:user_id>/email', '/admin/users/<int:user_id>/reset-second-step',   # v0.28.0
    '/ingredients/count/<int:movement_id>/undo',       # undo a stock count within 5 minutes (v0.30.0)
    '/voids/<int:adjustment_id>/approve', '/voids/<int:adjustment_id>/reject',   # voids and refunds (v0.31.0,
    '/sales/<int:sale_id>/void-now', '/sales/<int:sale_id>/refund',                          # rule S15, DEC-033)
}
USER_ROUTES = {                                        # @login_required (admin or cashier)
    '/logout', '/products', '/sales/new', '/sales/remove/<int:product_id>', '/sales/remove-line',
    '/sales/complete', '/sales/<int:sale_id>', '/profile', '/profile/remove', '/profile/password',
    '/sales/line-quantity', '/sales/line-options',     # order-line − / + and change add-ons (v0.20.0)
    '/sales/undo',                                    # undo the last change to the basket (v0.30.0)
    '/password/new', '/profile/email', '/profile/email/confirm',   # own account (v0.27.0)
    '/profile/devices/<int:device_id>/remove', '/profile/logout-everywhere', '/profile/backup-codes',   # v0.28.0
    '/profile/authenticator', '/profile/authenticator/confirm', '/profile/authenticator/off',
    '/profile/google', '/profile/google/code', '/profile/google/unlink',   # linking Google (v0.29.0)
    '/sales/today', '/sales/<int:sale_id>/void', '/sales/adjustment/<int:adjustment_id>',   # v0.31.0: ask for a void,
    '/voids/<int:adjustment_id>/ask', '/voids/<int:adjustment_id>/code',    # or approve it with an admin's emailed code
}
# ---- The only packages allowed in requirements.txt (AGENTS.md rule D1). Names are compared in lower case.
ALLOWED_PACKAGES = {'blinker', 'click', 'colorama', 'flask', 'flask-login', 'flask-sqlalchemy', 'greenlet',
                    'itsdangerous', 'jinja2', 'markupsafe', 'sqlalchemy', 'typing_extensions', 'werkzeug',
                    'alembic', 'flask-migrate', 'mako',   # v0.23.0: migrations (DEC-011, DEC-023); Mako comes with alembic
                    'waitress',                            # v0.24.0: the shop's web server (DEC-026)
                    'cryptography', 'cffi', 'pycparser',   # v0.28.0: the authenticator key, encrypted (DEC-017, DEC-030)
                    'segno',                               # v0.28.0: the authenticator QR code (DEC-017)
                    'authlib', 'joserfc', 'requests', 'certifi', 'charset-normalizer', 'idna', 'urllib3'}   # v0.29.0: Google (DEC-031)
# ---- Never committed to Git (AGENTS.md rule P1).
PRIVATE = [r'^instance/', r'\.db$', r'^static/avatars/', r'^static/products/', r'^local_demo/', r'secret_key',
           r'(^|/)\.env$', r'^venv/', r'^\.venv/',
           r'client_secret[^/]*\.json$', r'(?i)service-?account[^/]*\.json$']   # Google sign-in and cloud keys (2026-10-24)
MAX_AGENTS_LINES = 500

failures = []


def result(rule, ok, detail=''):
    print(f"  {'PASS' if ok else 'FAIL'}  {rule}" + (f'\n          {detail}' if detail and not ok else ''))
    if not ok:
        failures.append(rule)


def read(path):
    with open(os.path.join(ROOT, path), 'rb') as f:
        data = f.read()
    for bom, codec in [(b'\xff\xfe', 'utf-16'), (b'\xfe\xff', 'utf-16'), (b'\xef\xbb\xbf', 'utf-8-sig')]:
        if data.startswith(bom):
            return data.decode(codec)
    return data.decode('utf-8')


def python_files():
    for folder, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in {'.git', 'venv', '.venv', '__pycache__', 'instance', 'local_demo', 'node_modules'}]
        for name in files:
            if name.endswith('.py'):
                yield os.path.relpath(os.path.join(folder, name), ROOT)


def decorator_names(function):
    names = []
    for d in function.decorator_list:
        target = d.func if isinstance(d, ast.Call) else d
        names.append(ast.unparse(target))
    return names


# S1-S2: every route is classified and protected the way its list says.
# v0.25.0: pages are in app.py and in the blueprints (blueprints/*.py, decorated with @bp.route)
PAGE_FILES = ['app.py'] + sorted(os.path.join('blueprints', f) for f in os.listdir(os.path.join(ROOT, 'blueprints'))
                                 if f.endswith('.py') and f != '__init__.py')
seen = set()
for page_file in PAGE_FILES:
    tree = ast.parse(read(page_file))
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for d in node.decorator_list:
            if isinstance(d, ast.Call) and ast.unparse(d.func) in ('app.route', 'bp.route'):
                path = d.args[0].value
                seen.add(path)
                names = decorator_names(node)
                route = ast.unparse(d.func)
                where = f'{page_file} line {node.lineno}: {path} ({node.name})'
                if path in ADMIN_ROUTES:
                    result(f'S2 admin page {path} has @login_required and @admin_required',
                           names[:3] == [route, 'login_required', 'admin_required'], where + ' - decorators must be @route, @login_required, @admin_required in that order')
                elif path in USER_ROUTES:
                    result(f'S2 user page {path} has @login_required', names[:2] == [route, 'login_required'], where)
                elif path in PUBLIC_ROUTES:
                    result(f'S2 public page {path} is listed as public', True)
                else:
                    result(f'S1 new page {path} is listed in tests/check_contract.py', False,
                           where + ' - add it to PUBLIC_ROUTES, USER_ROUTES or ADMIN_ROUTES (and to AGENTS.md if it is public)')
for missing in sorted((PUBLIC_ROUTES | ADMIN_ROUTES | USER_ROUTES) - seen):
    result(f'S1 listed page {missing} still exists', False, 'remove it from the lists in tests/check_contract.py')

# I1 (v0.25.0, DEC-027): the pages never write to the database; every change goes through store/.
# So stock can only change in store/, where the conditional updates are (rule I1).
WRITES = [(r'db\.session\.(add|add_all|commit|delete|merge|flush)\(', 'db.session write'),
          (r'\.update\(\{', 'a query .update({...})'), (r'\.delete\(\)', 'a query .delete()'),
          (r'\.quantity\s*=[^=]', 'setting a stock quantity')]
for page_file in PAGE_FILES:
    for number, line in enumerate(read(page_file).splitlines(), 1):
        if line.strip().startswith('#'):
            continue
        for pattern, what in WRITES:
            if re.search(pattern, line):
                result(f'I1 {page_file} line {number} writes to the database itself ({what})', False,
                       line.strip() + '  - call a function in store/ instead')
result('I1 the pages (app.py, blueprints/) never write to the database; store/ does', True)

# S3: every POST form carries the CSRF token
templates = os.path.join(ROOT, 'templates')
form_count = 0
for name in sorted(os.listdir(templates)):
    html = read(os.path.join('templates', name))
    # A form may get its token from a macro in the same file, like {{ hidden_fields(...) }}
    token_macros = [m.group(1) for m in re.finditer(r'{%-?\s*macro\s+(\w+)\((.*?){%-?\s*endmacro', html, re.S) if 'csrf_token()' in m.group(0)]
    for m in re.finditer(r'<form\b[^>]*>(.*?)</form>', html, re.S | re.I):
        if re.search(r'method\s*=\s*["\']?post', m.group(0)[:m.group(0).find('>') + 1], re.I):
            form_count += 1
            line = html[:m.start()].count('\n') + 1
            result(f'S3 POST form in templates/{name} line {line} has csrf_token()', 'csrf_token()' in m.group(1) or any(f'{macro}(' in m.group(1) for macro in token_macros),
                   'add <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"> inside the form')
result(f'S3 POST forms found in templates ({form_count})', form_count > 0)

# S4-S5: no debug mode, no secret written in code, no raw SQL built from text pieces
for path in python_files():
    source = read(path)
    for number, line in enumerate(source.splitlines(), 1):
        if re.search(r'debug\s*=\s*True', line) and not path.startswith('tests'):
            result(f'S4 no debug=True ({path} line {number})', False, line.strip())
        # v0.28.0 (S13, DEC-030): only tests may log in with the password alone
        if re.search(r"TEST_PLAIN_LOGIN'\]\s*=\s*True", line) and not path.startswith('tests'):
            result(f'S13 TEST_PLAIN_LOGIN only switched on in tests ({path} line {number})', False, line.strip())
        if re.search(r'''(SECRET_KEY['"]?\]?\s*=|secret_key\s*=)\s*['"]''', line) and not path.startswith('tests'):
            result(f'S4 no secret key written in code ({path} line {number})', False, line.strip())
    if path.startswith('tests'):
        continue
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef):
            for inner in ast.walk(node):
                if (isinstance(inner, ast.Call) and ast.unparse(inner.func).endswith('text') and inner.args
                        and isinstance(inner.args[0], (ast.JoinedStr, ast.BinOp)) and node.name != 'upgrade_database'):
                    result(f'S5 SQL text is not built with f-strings or + ({path} line {inner.lineno}, in {node.name})', False,
                           'use :named parameters, e.g. db.text("... WHERE id = :i"), {"i": value}')
result('S4 no debug=True and no secret key in any .py file', not any(f.startswith('S4') for f in failures))
result('S13 the password-only test login is switched on only in tests/', not any(f.startswith('S13') for f in failures))
result('S5 SQL text only built from pieces inside upgrade_database()', not any(f.startswith('S5') for f in failures))

# D1: dependencies
packages = {}
REQUIREMENT_FILES = ['requirements.txt']   # v0.24.0: "-r requirements/local.txt" lines are followed too
for path in REQUIREMENT_FILES:
    for line in read(path).splitlines():
        line = line.strip()
        if line.startswith('-r '):
            REQUIREMENT_FILES.append(os.path.normpath(os.path.join(os.path.dirname(path), line[3:].strip())))
        elif line and not line.startswith('#'):
            name, _, version = line.partition('==')
            packages[name.strip().lower().replace('_', '-')] = version.strip()
allowed = {p.replace('_', '-') for p in ALLOWED_PACKAGES}
result('D1 the requirements files only have allowed packages', set(packages) <= allowed, 'not allowed: ' + ', '.join(sorted(set(packages) - allowed)))
result('D1 every package has an exact version (name==1.2.3)', all(packages.values()), 'missing: ' + ', '.join(n for n, v in packages.items() if not v))
# v0.21.6 (DEF-64, audit R11): saved as plain UTF-8, which every tool reads (PowerShell's "pip freeze >" writes UTF-16)
plain_utf8 = True
for path in REQUIREMENT_FILES:   # every requirements file, including the ones in requirements/ (v0.24.0)
    with open(os.path.join(ROOT, path), 'rb') as f:
        raw = f.read()
    try:
        raw.decode('utf-8')
        plain_utf8 = plain_utf8 and not raw.startswith((b'\xff\xfe', b'\xfe\xff', b'\xef\xbb\xbf'))
    except UnicodeDecodeError:
        plain_utf8 = False
result('D1 the requirements files are plain UTF-8 (not UTF-16, no byte-order mark)', plain_utf8,
       'save it as UTF-8: python -c "import pathlib;p=pathlib.Path(\'requirements.txt\');p.write_text(p.read_text(\'utf-16\'),\'utf-8\')"')

# D2: pages load nothing from the internet (AGENTS.md rule D2, changed in v0.19.4 for offline use)
ALLOWED_URLS = ()   # no outside address is allowed in a src, href or url(...)
VENDOR_FILES = ['bootstrap/bootstrap.min.css', 'bootstrap/bootstrap.bundle.min.js', 'bootstrap/LICENSE.txt',
                'bootstrap-icons/bootstrap-icons.min.css', 'bootstrap-icons/fonts/bootstrap-icons.woff2',
                'bootstrap-icons/LICENSE.txt', 'inter/inter.css', 'inter/LICENSE.txt']
missing = [f for f in VENDOR_FILES if not os.path.exists(os.path.join(ROOT, 'static', 'vendor', f))]
result('D2 Bootstrap, its icons and the Inter font are stored in static/vendor/ with their licences', not missing,
       'missing: ' + ', '.join(missing))
outside = []
for folder in ['templates', os.path.join('static', 'css')]:
    for name in sorted(os.listdir(os.path.join(ROOT, folder))):
        for url in re.findall(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', read(os.path.join(folder, name))) + \
                   re.findall(r'url\(["\']?(https?://[^"\')]+)', read(os.path.join(folder, name))):
            if not ALLOWED_URLS or not url.startswith(ALLOWED_URLS):
                outside.append(f'{folder}/{name}: {url}')
result('D2 no page loads anything from the internet (no http:// or https:// in src, href or url())', not outside, '; '.join(outside[:5]))

# P1: private files are not in Git
try:
    tracked = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    bad = [f for f in tracked if any(re.search(p, f) for p in PRIVATE)]
    result('P1 no private files in Git (database, secret key, uploads, local_demo)', not bad, ', '.join(bad[:10]))
except (OSError, subprocess.CalledProcessError):
    print('  SKIP  P1 (not a Git folder)')
ignored = read('.gitignore').split()
result('P1 .gitignore keeps instance/, uploads and local_demo/ out of Git',
       all(p in ignored for p in ['instance/', 'static/avatars/', 'static/products/', 'local_demo/']))

# A1: the contract file itself
agents = read('AGENTS.md') if os.path.exists(os.path.join(ROOT, 'AGENTS.md')) else ''
result(f'A1 AGENTS.md exists and is under {MAX_AGENTS_LINES} lines', 0 < len(agents.splitlines()) < MAX_AGENTS_LINES)
result('A1 AGENTS.md says which version it was last reviewed for', re.search(r'Last reviewed for v\d+\.\d+\.\d+', agents) is not None)
claude = read('CLAUDE.md') if os.path.exists(os.path.join(ROOT, 'CLAUDE.md')) else ''
result('A1 CLAUDE.md points to AGENTS.md', '@AGENTS.md' in claude)

print()
if failures:
    print(f'CONTRACT FAIL ({len(failures)} rule(s) broken). Fix them, or if a rule really changed, update AGENTS.md and this file.')
    sys.exit(1)
print('CONTRACT PASS')
