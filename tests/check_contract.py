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
PUBLIC_ROUTES = {'/', '/login'}                       # anyone, even when not logged in
ADMIN_ROUTES = {                                       # @login_required AND @admin_required
    '/products/add', '/products/edit/<int:product_id>', '/products/delete/<int:product_id>',
    '/options', '/ingredients', '/ingredients/<int:ingredient_id>', '/ingredients/history',
    '/recipe/<kind>/<int:item_id>', '/reports/sales',
}
USER_ROUTES = {                                        # @login_required (admin or cashier)
    '/logout', '/products', '/sales/new', '/sales/remove/<int:product_id>', '/sales/remove-line',
    '/sales/complete', '/sales/<int:sale_id>', '/profile', '/profile/remove', '/profile/password',
}
# ---- The only packages allowed in requirements.txt (AGENTS.md rule D1). Names are compared in lower case.
ALLOWED_PACKAGES = {'blinker', 'click', 'colorama', 'flask', 'flask-login', 'flask-sqlalchemy', 'greenlet',
                    'itsdangerous', 'jinja2', 'markupsafe', 'sqlalchemy', 'typing_extensions', 'werkzeug'}
# ---- Never committed to Git (AGENTS.md rule P1).
PRIVATE = [r'^instance/', r'\.db$', r'^static/avatars/', r'^static/products/', r'^local_demo/', r'secret_key',
           r'(^|/)\.env$', r'^venv/', r'^\.venv/']
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


# S1-S2: every route is classified and protected the way its list says
tree = ast.parse(read('app.py'))
seen = set()
for node in ast.walk(tree):
    if not isinstance(node, ast.FunctionDef):
        continue
    for d in node.decorator_list:
        if isinstance(d, ast.Call) and ast.unparse(d.func) == 'app.route':
            path = d.args[0].value
            seen.add(path)
            names = decorator_names(node)
            where = f'app.py line {node.lineno}: {path} ({node.name})'
            if path in ADMIN_ROUTES:
                result(f'S2 admin page {path} has @login_required and @admin_required',
                       names[:3] == ['app.route', 'login_required', 'admin_required'], where + ' - decorators must be @app.route, @login_required, @admin_required in that order')
            elif path in USER_ROUTES:
                result(f'S2 user page {path} has @login_required', names[:2] == ['app.route', 'login_required'], where)
            elif path in PUBLIC_ROUTES:
                result(f'S2 public page {path} is listed as public', True)
            else:
                result(f'S1 new page {path} is listed in tests/check_contract.py', False,
                       where + ' - add it to PUBLIC_ROUTES, USER_ROUTES or ADMIN_ROUTES (and to AGENTS.md if it is public)')
for missing in sorted((PUBLIC_ROUTES | ADMIN_ROUTES | USER_ROUTES) - seen):
    result(f'S1 listed page {missing} still exists in app.py', False, 'remove it from the lists in tests/check_contract.py')

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
result('S5 SQL text only built from pieces inside upgrade_database()', not any(f.startswith('S5') for f in failures))

# D1: dependencies
packages = {}
for line in read('requirements.txt').splitlines():
    line = line.strip()
    if line and not line.startswith('#'):
        name, _, version = line.partition('==')
        packages[name.strip().lower().replace('_', '-')] = version.strip()
allowed = {p.replace('_', '-') for p in ALLOWED_PACKAGES}
result('D1 requirements.txt only has allowed packages', set(packages) <= allowed, 'not allowed: ' + ', '.join(sorted(set(packages) - allowed)))
result('D1 every package has an exact version (name==1.2.3)', all(packages.values()), 'missing: ' + ', '.join(n for n, v in packages.items() if not v))

# D2: the only outside files a page may load (pinned versions; AGENTS.md rule D2)
ALLOWED_URLS = ('https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/', 'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/',
                'https://fonts.googleapis.com', 'https://fonts.gstatic.com')
outside = []
for folder in ['templates', os.path.join('static', 'css')]:
    for name in sorted(os.listdir(os.path.join(ROOT, folder))):
        for url in re.findall(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', read(os.path.join(folder, name))) + \
                   re.findall(r'url\(["\']?(https?://[^"\')]+)', read(os.path.join(folder, name))):
            if not url.startswith(ALLOWED_URLS):
                outside.append(f'{folder}/{name}: {url}')
result('D2 pages only load Bootstrap 5.3.3, Bootstrap Icons 1.11.3 and the Inter font from outside', not outside, '; '.join(outside[:5]))

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
