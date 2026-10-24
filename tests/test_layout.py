"""Cozy layout and foldable sidebar (v0.21.0, test cases TC-25.1-25.6)."""
import re
from helpers import check, finish, make_users, text
from app import app, upgrade_database
app.config['TEST_PLAIN_LOGIN'] = True   # v0.28.0: password-only login; this file isn't about the login code (DEC-030)
app.config['CSRF_ENABLED'] = False
from models import db, User

with app.app_context():
    db.drop_all(); upgrade_database(); make_users(db, User)

css = open('static/css/theme.css', encoding='utf-8').read()
admin = app.test_client(); admin.post('/login', data={'username': 'admin', 'password': 'admin123'})
pages = {'products': admin.get('/products'), 'new sale': admin.get('/sales/new'), 'login': app.test_client().get('/login')}
for name, r in pages.items():
    html = text(r)
    check(f'TC-25.1 {name}: exactly one fold button for the sidebar', html.count('js-sidebar-toggle"') == 1 if name != 'login' else True)
html = text(pages['products'])
check('TC-25.2 the fold button (an icon beside the system name, v0.21.1) is a plain button, not a link or a form (it changes nothing on the server)',
      re.search(r'<button type="button" class="fold-btn js-sidebar-toggle"', html) is not None)
check('TC-25.7 the fold button sits in the top row beside the system name, above the menu links (v0.21.1)',
      html.index('class="brand"') < html.index('js-sidebar-toggle"') < html.index('class="side-label"') and '<span>Fold menu</span>' not in html)
check('TC-25.3 the saved fold choice is applied before the page is drawn (no flash)',
      html.index("pos-sidebar") < html.index('</head>') and "classList.add('sidebar-rail')" in html)
check('TC-25.3 the click saves the choice in this browser only (localStorage)', "localStorage.setItem('pos-sidebar'" in html)
check('TC-25.4 every sidebar link has a tooltip with its name, for when only icons show',
      len(re.findall(r'class="side-link[^"]*" title="[^"]+"', html)) >= 5)
check('TC-25.5 folding only happens on wide screens (the phone menu is unchanged)',
      re.search(r'@media \(min-width: 992px\) \{[^@]*html\.sidebar-rail \.app-sidebar \{ width: 84px', css) is not None)
check('TC-25.6 both themes use the warm palette (cream light, espresso dark)',
      '--app-bg: #F6EFE5' in css and '--app-bg: #1E1815' in css and '#0F6E56;          /* teal' not in css)
# ---- v0.21.2: found by the layout audit
check('TC-25.8 folded: the theme icon is not pushed to the side by margin-left:auto (it sat off-centre under the avatar)',
      re.search(r'html\.sidebar-rail \.side-footer-row \.theme-toggle\s*\{\s*margin-left:\s*0', css) is not None)
check('TC-25.9 phones: the New ingredient panel floats inside the screen (it ran off the right edge)',
      re.search(r'\.new-ingredient-panel\s*\{\s*position:\s*fixed;\s*left:\s*1rem;\s*right:\s*1rem', css) is not None)
finish('LAYOUT')
