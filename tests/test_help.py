"""Help: the ? button on every page and the Help page (v0.32.0, F29, DEC-034), test cases TC-42.x."""
import os
import re
from decimal import Decimal
from helpers import check, finish, make_users, text, logged_in

from app import app
app.config['TEST_PLAIN_LOGIN'] = True   # password-only login; this file isn't about the login code (DEC-030)
from models import db, User, Product, Sale, SaleItem
import help_topics
from help_topics import TOPICS, BY_ENDPOINT

app.config['CSRF_ENABLED'] = False
with app.app_context():
    db.drop_all(); db.create_all(); make_users(db, User)
    db.session.add(Product(name='Test Latte', sku='TL-1', price=Decimal('120.00'), quantity=5))
    db.session.flush()
    sale = Sale(user_id=1, total=Decimal('120.00'), cash_received=Decimal('120.00'), change_due=Decimal('0'))
    db.session.add(sale); db.session.flush()
    db.session.add(SaleItem(sale_id=sale.id, product_id=1, product_name='Test Latte', unit_price=Decimal('120.00'), quantity=1))
    db.session.commit()
    SALE_ID = sale.id

admin = logged_in(app, 'admin', 'admin123')
cashier = logged_in(app, 'cashier', 'cashier123')
visitor = app.test_client()


def help_buttons(html):
    """Every ? button on a page, from <button ...> to </button>."""
    return re.findall(r'<button[^>]*class="help-toggle[^"]*"[^>]*>.*?</button>', html, re.S)


def panel(html):
    """The help side panel's HTML, or '' when the page has none."""
    start = html.find('<div class="offcanvas offcanvas-end help-panel')
    return html[start:html.find("<!-- Bootstrap's JavaScript", start)] if start >= 0 else ''


# ---- TC-42.1 every page someone can open has a topic, and every topic names real pages
NOT_PAGES = {'static', 'help.help_page',                          # files; the Help page itself
             'accounts.google_login', 'accounts.google_callback'}  # these only send the browser on to Google and back
with app.app_context():
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    pages = {rule.endpoint for rule in app.url_map.iter_rules() if 'GET' in rule.methods} - NOT_PAGES
missing = sorted(pages - set(BY_ENDPOINT))
check('TC-42.1 every page that can be opened has a help topic' + (f' (missing: {", ".join(missing)})' if missing else ''), not missing)
stale = sorted(set(BY_ENDPOINT) - endpoints)
check('TC-42.1 every page a topic names still exists' + (f' (gone: {", ".join(stale)})' if stale else ''), not stale)
check('TC-42.1 no page is explained by two topics', len(BY_ENDPOINT) == sum(len(t['endpoints']) for t in TOPICS))

# ---- TC-42.2 every topic has a small WebP picture stored in the app (works offline, rule D2)
sizes = []
for topic in TOPICS:
    path = os.path.join('static', 'help', topic['key'] + '.webp')
    data = open(path, 'rb').read() if os.path.exists(path) else b''
    sizes.append(len(data))
    check(f"TC-42.2 {topic['key']}: the picture exists and is a WebP image", data[:4] == b'RIFF' and data[8:12] == b'WEBP')
    check(f"TC-42.2 {topic['key']}: the picture is at most 150 KB", 0 < len(data) <= 150_000)
check('TC-42.2 all the pictures together are under 1.5 MB', sum(sizes) <= 1_500_000)
extra = sorted(set(os.listdir(os.path.join('static', 'help'))) - {t['key'] + '.webp' for t in TOPICS})
check('TC-42.2 no picture without a topic is left in static/help', not extra)

# ---- TC-42.3 the words: plain text, complete, steps marked for who can do them
for topic in TOPICS:
    words = [topic['title'], topic['summary'], topic['note']] + [s for _, s in topic['steps']]
    check(f"TC-42.3 {topic['key']}: has a title, a one-line summary and at least two steps",
          topic['title'] and topic['summary'] and len(topic['steps']) >= 2)
    check(f"TC-42.3 {topic['key']}: no HTML in the words (they are shown as plain text, rule S11)",
          not any('<' in w or '>' in w for w in words))
    check(f"TC-42.3 {topic['key']}: every step is for 'all', 'admin' or 'cashier'",
          all(who in ('all', 'admin', 'cashier') for who, _ in topic['steps']))
    check(f"TC-42.3 {topic['key']}: an admin page's steps are all for admins",
          not topic['admins'] or all(who == 'admin' for who, _ in topic['steps']))
    check(f"TC-42.3 {topic['key']}: a Bootstrap icon", topic['icon'].startswith('bi-'))

# ---- TC-42.4 the ? button: only an icon, with words for screen readers, opening this page's help
html = text(admin.get('/products'))
buttons = help_buttons(html)
check('TC-42.4 Products: two ? buttons (top bar on phones, bottom corner on wide screens)', len(buttons) == 2)
check('TC-42.4 the button is only an icon, no words on it',
      buttons and all(re.sub(r'<[^>]+>', '', b).strip() == '' for b in buttons))
check('TC-42.4 screen readers and the tooltip get "Help for this page"',
      buttons and all('aria-label="Help for this page"' in b and 'title="Help for this page"' in b for b in buttons))
check('TC-42.4 the button opens the panel', buttons and all('data-bs-target="#helpPanel"' in b for b in buttons))
one = panel(html)
check("TC-42.4 the panel has the Products topic: title, summary and picture",
      'Products' in one and BY_ENDPOINT['catalog.products']['summary'].replace("'", '&#39;') in one
      and '/static/help/products.webp' in one)
check('TC-42.4 the panel links to that topic on the Help page', 'href="/help#products"' in one)
check('TC-42.4 the button and panel are left out when printing', 'help-toggle d-print-none' in html and 'help-panel d-print-none' in one)
check('TC-42.4 the avatar menu links to the Help page', 'href="/help"' in html)

# ---- TC-42.5 the login page has help too, without a link to the Help page (that needs a login)
html = text(visitor.get('/login'))
one = panel(html)
check('TC-42.5 login page: one ? button beside the theme switch', len(help_buttons(html)) == 1)
check('TC-42.5 login page: the panel explains logging in', 'Logging in' in one and 'login.webp' in one)
check('TC-42.5 login page: no link to the Help page for a visitor', 'href="/help' not in one)
check('TC-42.5 Forgot password uses the same topic', 'Logging in' in panel(text(visitor.get('/forgot-password'))))

# ---- TC-42.6 each person sees the steps they can do
cashier_receipt = panel(text(cashier.get(f'/sales/{SALE_ID}')))
admin_receipt = panel(text(admin.get(f'/sales/{SALE_ID}')))
check('TC-42.6 a cashier is told how to ask for a void', 'Ask for a void' in cashier_receipt)
check("TC-42.6 a cashier isn't told about Void now or Refund items", 'Void now' not in cashier_receipt and 'Refund items' not in cashier_receipt)
check('TC-42.6 an admin is told about Void now and Refund items', 'Void now' in admin_receipt and 'Refund items' in admin_receipt)
check("TC-42.6 an admin isn't told to ask for a void", 'Ask for a void' not in admin_receipt)
check('TC-42.6 a cashier on Products is told it is view only', 'View only' in panel(text(cashier.get('/products'))))

# ---- TC-42.7 the Help page: logged in only; a cashier gets no admin pages
response = visitor.get('/help')
check('TC-42.7 a visitor is sent to the login page', response.status_code == 302 and '/login' in response.headers['Location'])
admin_help, cashier_help = text(admin.get('/help')), text(cashier.get('/help'))
everyone = [t for t in TOPICS if not t['admins']]
check(f'TC-42.7 an admin sees all {len(TOPICS)} topics', admin_help.count('class="card app-card help-topic') == len(TOPICS))
check(f'TC-42.7 a cashier sees only the {len(everyone)} topics for everyone',
      cashier_help.count('class="card app-card help-topic') == len(everyone))
check("TC-42.7 a cashier's Help has no Users, Audit log or Sales Report section",
      all(f'id="{key}"' not in cashier_help for key in ('users', 'audit', 'sales_report')))
check('TC-42.7 admin pages are marked "Admins only" for an admin',
      admin_help.count('Admins only') == len([t for t in TOPICS if t['admins']]))
check('TC-42.7 every topic shows its picture', all(f"/static/help/{t['key']}.webp" in admin_help for t in TOPICS))
check('TC-42.7 the contents jump to each topic', all(f'href="#{t["key"]}"' in admin_help for t in TOPICS))
check('TC-42.7 pages that need no number get an "Open" link; a receipt does not',
      'href="/sales/new"' in admin_help and f'href="/sales/{SALE_ID}"' not in admin_help)
check("TC-42.7 the Help page has no ? button of its own", not help_buttons(admin_help))

# ---- TC-42.8 a cashier who types an admin page's address gets 403 and no help for that page
response = cashier.get('/admin/users')
check("TC-42.8 cashier on Users: still 403, and no admin help shown",
      response.status_code == 403 and not panel(text(response)) and not help_buttons(text(response)))

# ---- TC-42.9 the words are escaped like everything else (rule S11)
original = help_topics.BY_ENDPOINT['sales.new_sale']['summary']
help_topics.BY_ENDPOINT['sales.new_sale']['summary'] = '<b>bold</b>'
html = text(admin.get('/sales/new'))
help_topics.BY_ENDPOINT['sales.new_sale']['summary'] = original
check('TC-42.9 text that looks like HTML is shown, not run', '&lt;b&gt;bold&lt;/b&gt;' in html and '<b>bold</b>' not in html)

# ---- TC-42.10 the look: the button and panel use the theme's colours (both themes) and fit a phone
css = open('static/css/theme.css', encoding='utf-8').read()
check('TC-42.10 the panel is never wider than a phone screen', 'min(440px, 100vw)' in css)
check("TC-42.10 the button and panel use the theme's colour variables (light and dark)",
      re.search(r'\.help-toggle \{[^}]*var\(--app-border\)[^}]*var\(--app-muted\)', css) is not None
      and re.search(r'\.help-panel \{[^}]*var\(--app-surface\)', css) is not None)
finish('HELP')
