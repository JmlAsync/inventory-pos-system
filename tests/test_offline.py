"""Pages work without internet (v0.19.4, AGENTS.md rule D2): nothing is loaded from outside, and every
style sheet, script and font a page asks for is really in static/."""
import os
import re
from helpers import check, finish, make_users, text
from app import app
app.config['TEST_PLAIN_LOGIN'] = True   # v0.28.0: password-only login; this file isn't about the login code (DEC-030)
from models import db, User, Product

app.config['CSRF_ENABLED'] = False
with app.app_context():
    db.drop_all(); db.create_all(); make_users(db, User)
    db.session.add(Product(name='Latte', sku='L1', price=150, quantity=5)); db.session.commit()

admin = app.test_client(); admin.post('/login', data={'username': 'admin', 'password': 'admin123'})
pages = {'login (visitor)': (app.test_client(), '/login'), 'home': (admin, '/'), 'products': (admin, '/products'),
         'new sale': (admin, '/sales/new'), 'ingredients': (admin, '/ingredients'), 'report': (admin, '/reports/sales')}
assets = set()
for name, (client, path) in pages.items():
    html = text(client.get(path))
    outside = re.findall(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', html)
    check(f'{name}: nothing loaded from the internet', outside == [])
    assets.update(a for a in re.findall(r'(?:src|href)\s*=\s*["\'](/static/[^"\'?#]+)', html))
check('pages ask for Bootstrap, its icons and the Inter font from /static/vendor/',
      {'/static/vendor/bootstrap/bootstrap.min.css', '/static/vendor/bootstrap/bootstrap.bundle.min.js',
       '/static/vendor/bootstrap-icons/bootstrap-icons.min.css', '/static/vendor/inter/inter.css'} <= assets)
c = app.test_client()
check(f'every file the pages ask for exists ({len(assets)} files)', all(c.get(a).status_code == 200 for a in assets))
# fonts named inside the style sheets (url(...)) must exist too
fonts = []
for css in ['static/vendor/bootstrap-icons/bootstrap-icons.min.css', 'static/vendor/inter/inter.css']:
    folder = os.path.dirname(css)
    for url in re.findall(r'url\(["\']?([^"\')?#]+)', open(css, encoding='utf-8').read()):
        fonts.append(os.path.exists(os.path.join(folder, url)))
check(f'every font file named in the style sheets exists ({len(fonts)} files)', fonts and all(fonts))
check('the Inter font includes the peso sign (U+20B1, in the latin-ext range)', 'U+20AD-20C0' in open('static/vendor/inter/inter.css').read())
check('each bundled package keeps its licence', all(os.path.exists(f'static/vendor/{p}/LICENSE.txt') for p in ['bootstrap', 'bootstrap-icons', 'inter']))
finish('OFFLINE')
