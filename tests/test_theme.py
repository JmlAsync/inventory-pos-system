"""Light / dark switch (feature F11, v0.13.0; icon-only since v0.19.1) and the avatar menu beside it (v0.19.2), test cases TC-12.x."""
import re
from helpers import check, finish, make_users, text
from app import app
from models import db, User

app.config['CSRF_ENABLED'] = False
with app.app_context():
    db.drop_all(); db.create_all(); make_users(db, User)


def toggles(html):
    """Every theme switch button on a page, from <button ...> to </button>."""
    return re.findall(r'<button[^>]*js-theme-toggle[^>]*>.*?</button>', html, re.S)


admin = app.test_client(); admin.post('/login', data={'username': 'admin', 'password': 'admin123'})
pages = {'login page': text(app.test_client().get('/login')), 'home (visitor)': text(app.test_client().get('/')),
         'products (logged in)': text(admin.get('/products'))}
for name, html in pages.items():
    found = toggles(html)
    check(f'{name}: exactly one theme switch', len(found) == 1)
    button = found[0] if found else ''
    words = re.sub(r'<[^>]+>', '', button).strip()
    check(f'{name}: the switch is only an icon, no words on it (v0.19.1)', words == '')
    check(f'{name}: sun shown in light theme, moon in dark (icon = current theme)',
          re.search(r'bi-sun when-light', button) is not None and re.search(r'bi-moon-stars when-dark', button) is not None)
    check(f'{name}: screen readers still get a label', 'aria-label="' in button)
html = pages['products (logged in)']
footer = html[html.find('side-footer-row'):html.find('</aside>')]
check('logged in: the icon sits in the same row as the user chip, after it', 'user-chip' in footer and footer.find('user-chip') < footer.find('js-theme-toggle'))
check('the tooltip text is set by the page script ("Switch to dark mode")', "'Switch to dark mode'" in html and "setAttribute('title'" in html)
menu = re.search(r'<ul class="dropdown-menu[^"]*"', html).group(0)
check('avatar menu is not squeezed to the name button\'s width (DEF-46, v0.19.2)', 'user-menu' in menu and 'w-100' not in menu)
css = open('static/css/theme.css', encoding='utf-8').read()
check('avatar menu grows to fit its longest line, each line on one line (DEF-46)',
      re.search(r'\.user-menu \{[^}]*min-width: 100%;[^}]*width: max-content;', css) is not None and 'white-space: nowrap' in css.split('.user-menu')[-1])
finish('THEME')
