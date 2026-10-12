"""New Sale redesign (feature F19, v0.20.0, test cases TC-22.x): "Rush Hour + Stock Aware" tiles,
the running-low banner, − / + on basket lines, changing a drink's serving and add-ons from its
basket line (design 6a), the "Uses N ingredients" panel and the quick cash amounts."""
import re
from helpers import check, finish, text
from app import app, upgrade_database, quick_cash, MAX_QUANTITY
app.config['CSRF_ENABLED'] = False
from models import db, User, Product, Sale, MenuOption, Ingredient, RecipeItem
from werkzeug.security import generate_password_hash as g

# ---- A small café: Cafe Latte (Hot / Iced), Matcha Latte (no powder left), Croffle (no recipe)
with app.app_context():
    db.drop_all(); upgrade_database()
    db.session.add_all([User(username='admin', password_hash=g('a'), role='admin'),
                        User(username='cashier', password_hash=g('c'), role='cashier')])
    latte = Product(name='Cafe Latte', sku='L1', price=140, quantity=0, category='Coffee', has_options=True)
    matcha = Product(name='Matcha Latte', sku='M1', price=160, quantity=0, category='Non-Coffee')
    croffle = Product(name='Croffle', sku='C1', price=150, quantity=3, category='Pastries')
    hot = MenuOption(kind='size', name='Hot', price=0, sort_order=1)
    iced = MenuOption(kind='size', name='Iced', price=0, sort_order=2)
    oat = MenuOption(kind='addon', name='Sub Oat', price=40, sort_order=1)
    shot = MenuOption(kind='addon', name='Espresso', price=30, sort_order=2)
    db.session.add_all([latte, matcha, croffle, hot, iced, oat, shot])
    stock = {}   # name -> (unit, on hand, warn at)
    for name, unit, qty, low in [('Espresso beans', 'g', 3000, 200), ('Fresh milk', 'ml', 1000, 300), ('Oat milk', 'ml', 300, 50),
                                 ('Ice', 'g', 8000, 500), ('Iced cups', 'pcs', 2, 20), ('Hot cups', 'pcs', 0, 10), ('Matcha powder', 'g', 0, 50)]:
        stock[name] = Ingredient(name=name, unit=unit, quantity=qty, low_at=low)
    db.session.add_all(stock.values()); db.session.commit()
    for owner, ingredient, amount in [(latte, 'Espresso beans', 18), (latte, 'Fresh milk', 200), (matcha, 'Matcha powder', 5),
                                      (iced, 'Ice', 150), (iced, 'Iced cups', 1), (hot, 'Hot cups', 1),
                                      (oat, 'Fresh milk', -200), (oat, 'Oat milk', 200)]:
        key = 'product_id' if isinstance(owner, Product) else 'option_id'
        db.session.add(RecipeItem(ingredient_id=stock[ingredient].id, amount=amount, **{key: owner.id}))
    db.session.commit()
    L, M, C = latte.id, matcha.id, croffle.id
    HOT, ICED, OAT, SHOT = hot.id, iced.id, oat.id, shot.id
    I = {name: i.id for name, i in stock.items()}

a = app.test_client(); a.post('/login', data={'username': 'admin', 'password': 'a'})
c = app.test_client(); c.post('/login', data={'username': 'cashier', 'password': 'c'})
def page(client=c): return text(client.get('/sales/new'))
def tile(h, name):
    """The HTML of one product's tile."""
    m = re.search(r'<div class="sale-tile[^"]*">(?:(?!<div class="col").)*?' + re.escape(name) + r'</span>.*?(?=<div class="col"|<p class="text-body-secondary small mt-2)', h, re.S)
    return m.group(0) if m else ''
def lines(h): return re.findall(r'name="line" value="([^"]+)"', h.split('<!-- order lines -->')[1].split('<!-- end of order lines -->')[0]) if '<!-- order lines -->' in h else []
def basket():
    with c.session_transaction() as s: return dict(s.get('basket', {}))
def qty(change, line): return c.post('/sales/line-quantity', data={'line': line, 'change': change})
def opts(line, **d): return c.post('/sales/line-options', data=dict(line=line, **d))
def ingredient(name):
    with app.app_context(): return db.session.get(Ingredient, I[name]).quantity

# ---- TC-22.1 tiles: one button per serving, stock bar, the missing ingredient
h = page(); t = tile(h, 'Cafe Latte')
check('TC-22.1 drink tile: "+ Iced" adds 1 Iced (sends product, quantity 1 and size)',
      re.search(rf'value="{L}">\s*<input type="hidden" name="quantity" value="1">\s*<input type="hidden" name="size_id" value="{ICED}">', t) is not None)
check('TC-22.1 "+ Hot" is greyed with the reason: no Hot cups', 'serve-out" disabled' in t and 'no Hot cups' in t and f'name="size_id" value="{HOT}"' not in t)
check('TC-22.1 note and bar: "Only 2 left" (2 Iced cups), bar 10% (2 of 20)', 'Only 2 left' in t and 'width: 10%' in t and 'level-low' in t)
tm = tile(h, 'Matcha Latte')
check('TC-22.1 drink that can\'t be made: "Out of Matcha powder", "Can\'t make now", no add form',
      'Out of Matcha powder' in tm and "Can&#39;t make now" in tm and 'name="product_id"' not in tm)
tc = tile(h, 'Croffle')
check('TC-22.1 product without servings: one "+ Add" button, "Only 3 left"', '+ Add' in tc and 'Only 3 left' in tc and 'size_id' not in tc)
check('TC-22.1 the old drink window is gone (design 6a: add-ons are changed in the basket)', 'optionsDialog' not in h)

# ---- TC-22.2 running-low banner: names, link only for the admin
check('TC-22.2 banner names the low and the out ingredients',
      re.search(r'Running low: Iced cups.*Hot cups, Matcha powder are out', ' '.join(h.split())) is not None)
check('TC-22.2 cashier: warning only, no link to Ingredients', '<div class="low-banner">' in h and 'href="/ingredients"' not in h)
ha = page(a)
check('TC-22.2 admin: the banner opens Ingredients', '<a href="/ingredients" class="low-banner"' in ha)

# ---- TC-22.3 − and + on a basket line
c.post('/sales/new', data={'product_id': L, 'quantity': '1', 'size_id': ICED})
line = f'{L}:{ICED}:'
check('TC-22.3 tap "+ Iced" -> one line "Cafe Latte, Iced"', basket() == {line: 1} and 'basket-options">Iced<' in page())
r = qty('1', line)
check('TC-22.3 "+" makes it 2', r.status_code == 302 and basket() == {line: 2})
r = qty('1', line)
check('TC-22.3 "+" past the stock is refused with the reason, basket unchanged', 'Not enough Iced cups' in text(r) and basket() == {line: 2})
for bad in ['5', '-3', 'abc', '']:
    qty(bad, line)
check('TC-22.3 only -1 and +1 are accepted (5, -3, abc, empty change nothing)', basket() == {line: 2})
qty('1', 'does-not-exist')
check('TC-22.3 an unknown line is harmless', basket() == {line: 2})
qty('-1', line)
check('TC-22.3 "−" makes it 1', basket() == {line: 1})
qty('-1', line)
check('TC-22.3 "−" at 1 takes the line out', basket() == {})
with c.session_transaction() as s: s['basket'] = {str(C): MAX_QUANTITY}
check('TC-22.3 "+" can never go past the maximum quantity', f'at most {MAX_QUANTITY:,}' in text(qty('1', str(C))))
with c.session_transaction() as s: s['basket'] = {}

# ---- TC-22.4 change serving and add-ons from the basket line (6a)
c.post('/sales/new', data={'product_id': L, 'quantity': '1', 'size_id': ICED})
h = page()
check('TC-22.4 each basket line has a change panel with the servings and add-ons, current choice ticked',
      'id="lineEdit1"' in h and re.search(rf'value="{ICED}" data-price="0\.0"\s*checked', h) is not None and 'name="addon_ids"' in h)
r = opts(line, size_id=ICED, addon_ids=[OAT])
check('TC-22.4 tick Sub Oat -> the line becomes "Iced, Sub Oat", ₱180.00', r.status_code == 302 and basket() == {f'{L}:{ICED}:{OAT}': 1}
      and 'basket-options">Iced, Sub Oat<' in page() and '1 × ₱180.00' in page())
h = page()
check('TC-22.4 "Uses" panel follows the change: Oat milk instead of Fresh milk', 'Oat milk</strong>' in h and 'Fresh milk</strong>' not in h)
c.post('/sales/new', data={'product_id': L, 'quantity': '1', 'size_id': ICED})   # a second, plain Iced latte
r = opts(line, size_id=ICED, addon_ids=[OAT])
check('TC-22.4 joining it to the Sub Oat line would need 400 ml oat milk (300 on hand): refused', 'Not enough Oat milk' in text(r)
      and basket() == {f'{L}:{ICED}:{OAT}': 1, line: 1})
with app.app_context(): db.session.get(Ingredient, I['Oat milk']).quantity = 1000; db.session.commit()
opts(line, size_id=ICED, addon_ids=[OAT])
check('TC-22.4 same drink + same choices -> the two lines become one (2 × ₱180.00)', basket() == {f'{L}:{ICED}:{OAT}': 2} and '2 × ₱180.00' in page())
oat_line = f'{L}:{ICED}:{OAT}'
r = opts(oat_line, size_id=HOT, addon_ids=[OAT])
check('TC-22.4 switch to Hot with no Hot cups: refused with the reason', 'Not enough Hot cups' in text(r) and basket() == {oat_line: 2})
for data, why in [({'size_id': OAT}, 'an add-on sent as the serving'), ({'size_id': '9999'}, 'an unknown serving'),
                  ({'size_id': ICED, 'addon_ids': [HOT]}, 'a serving sent as an add-on'), ({'size_id': ICED, 'addon_ids': ['x']}, 'a non-number add-on')]:
    r = opts(oat_line, **data)
    check(f'TC-22.4 refused: {why}', r.status_code == 200 and ('servings offered' in text(r) or 'add-ons from the list' in text(r)) and basket() == {oat_line: 2})
with app.app_context(): db.session.get(MenuOption, SHOT).active = False; db.session.commit()
check('TC-22.4 a hidden add-on is refused', 'add-ons from the list' in text(opts(oat_line, size_id=ICED, addon_ids=[SHOT])))
with app.app_context(): db.session.get(MenuOption, SHOT).active = True; db.session.commit()
opts(oat_line, size_id=ICED)
check('TC-22.4 untick every add-on -> back to plain Iced', basket() == {line: 2})
opts(line, size_id=ICED, addon_ids=[SHOT, OAT, OAT])
check('TC-22.4 add-ons in any order / twice give the same line key', basket() == {f'{L}:{ICED}:{min(OAT, SHOT)}.{max(OAT, SHOT)}': 2})
c.post('/sales/new', data={'product_id': C, 'quantity': '1'})
check('TC-22.4 a product without servings can\'t be "changed"', 'no servings or add-ons to change' in text(opts(str(C), size_id=ICED)))
check('TC-22.4 an unknown line is harmless', opts('does-not-exist', size_id=ICED).status_code == 302)
with c.session_transaction() as s: s['basket'] = {}

# ---- TC-22.5 "Uses N ingredients": amounts, before -> after, opens when something will be low
c.post('/sales/new', data={'product_id': L, 'quantity': '1', 'size_id': ICED})
h = ' '.join(page().split())
check('TC-22.5 panel lists every ingredient with − amount and before → after',
      'Uses 4 ingredients' in h and 'Iced cups</strong> <span class="text-body-secondary">−1 pcs' in h and '2 → 1 pcs · for Cafe Latte' in h
      and '1,000 → 800 ml' in h)
check('TC-22.5 opens by itself and says what will be low', '<details class="uses-panel warn" open>' in h and 'Iced cups will be low' in h)
check('TC-22.5 worst first: the Low row comes before the OK rows', h.index('uses-low') < h.index('uses-ok'))
check('TC-22.5 cashier sees no link to Ingredients in the panel', 'Open Ingredients' not in h)
check('TC-22.5 admin does (the admin\'s basket is its own, so add one there)',
      (a.post('/sales/new', data={'product_id': L, 'quantity': '1', 'size_id': ICED}), 'Open Ingredients' in page(a))[1])
qty('1', line)
check('TC-22.5 the last cup: "Runs out"', 'Iced cups will run out' in page() and 'uses-out' in page())
qty('-1', line)
with c.session_transaction() as s: s['basket'] = {str(C): 1}
h = page()
check('TC-22.5 no recipe in the basket -> no panel', 'uses-panel' not in h)

# ---- TC-22.6 quick cash
check('TC-22.6 quick cash = next ₱100 / ₱500 / ₱1,000: 310 -> 400, 500, 1,000; 600 -> 700, 1,000; 1,000 -> 1,100, 1,500, 2,000',
      quick_cash(310) == [400, 500, 1000] and quick_cash(600) == [700, 1000] and quick_cash(1000) == [1100, 1500, 2000] and quick_cash(0) == [])
check('TC-22.6 never above the cash limit', quick_cash(999_999.5) == [1_000_000])
check('TC-22.6 the page shows Exact, the amounts and an "Other amount" box (₱150 basket)', 'data-cash="150.00">Exact' in h and 'data-cash="200">₱200' in h
      and 'data-cash="1000">₱1,000' in h and 'placeholder="Other amount"' in h)

# ---- TC-22.7 a sale made with the new buttons is saved and deducted correctly
with c.session_transaction() as s: s['basket'] = {}
c.post('/sales/new', data={'product_id': L, 'quantity': '1', 'size_id': ICED}); qty('1', line); qty('-1', line)
c.post('/sales/new', data={'product_id': C, 'quantity': '1'}); qty('1', str(C))
r = c.post('/sales/complete', data={'payment_method': 'cash', 'cash_received': '500'})
with app.app_context():
    sale = Sale.query.order_by(Sale.id.desc()).first()
    check('TC-22.7 sale: 1 Iced latte + 2 croffles = ₱440.00, change ₱60.00', r.status_code == 302 and sale.total == 440 and sale.change_due == 60)
    check('TC-22.7 stock: Iced cups 2 -> 1, croffles 3 -> 1', db.session.get(Ingredient, I['Iced cups']).quantity == 1 and db.session.get(Product, C).quantity == 1)

# ---- TC-22.8 safety: login, CSRF token on every form, token checked on the new routes
anon = app.test_client()
for path in ['/sales/line-quantity', '/sales/line-options']:
    r = anon.post(path, data={'line': line, 'change': '1'})
    check(f'TC-22.8 {path}: logged out -> sent to the login page', r.status_code == 302 and '/login' in r.headers['Location'])
c.post('/sales/new', data={'product_id': C, 'quantity': '1'})
h = page()
forms = h.count('method="POST"')
check(f'TC-22.8 every POST form on New Sale carries a token ({forms} forms)', forms > 5 and h.count('name="csrf_token"') == forms)
app.config['CSRF_ENABLED'] = True
check('TC-22.8 "+" without the token is refused (400) and changes nothing',
      c.post('/sales/line-quantity', data={'line': str(C), 'change': '1'}).status_code == 400 and basket() == {str(C): 1})
check('TC-22.8 changing a line without the token is refused (400)', c.post('/sales/line-options', data={'line': str(C)}).status_code == 400)
app.config['CSRF_ENABLED'] = False

# ---- TC-22.11 (v0.20.1, DEF-57) New Sale uses the whole screen width
css = open('static/css/theme.css', encoding='utf-8').read()
check('TC-22.11 New Sale has no 1180px width limit (other pages keep it)',
      re.search(r'\.app-content:has\(\.sale-page\)\s*\{\s*max-width:\s*none', css) is not None and '<div class="sale-page">' in h
      and re.search(r'\.app-content\s*\{[^}]*max-width:\s*1180px', css) is not None)
check('TC-22.11 as many tiles per row as fit (auto-fill grid), not a fixed 3', 'class="tile-grid"' in h and 'row-cols-sm-3' not in h
      and re.search(r'\.tile-grid\s*\{[^}]*repeat\(auto-fill', css) is not None)
check('TC-22.11 the basket gets a fixed share (380-460px) and the menu takes the rest', 'clamp(380px, 30%, 460px)' in css and '<div class="sale-side">' in h)
check('TC-22.11 bar and "N left" share one line in the tile', '<div class="tile-stock">' in h)

# ---- TC-22.13 (v0.20.5, DEF-58) New Sale styles don't leak onto other pages
# v0.20.0 reused the name "stock-bar", which the Ingredients page already had: its warn-level tick shrank to a speck.
import glob
block = css[css.index('New Sale (v0.20.0)'):css.index('/* Phone basket bar (v0.14.3) */')]
SHARED_ON_PURPOSE = {'app-content', 'btn-check'}   # only ever used together with a New Sale name (":has(.sale-page)", "+ .toggle-btn")
leading = set()
for selector_list in re.findall(r'(?m)^([^{}@/][^{]*)\{', block):
    for selector in selector_list.split(','):
        first = re.match(r'\s*(?:\[[^\]]*\]\s*)?\.([a-z][a-z0-9-]*)', selector)   # the first class of the selector
        if first:
            leading.add(first.group(1))
leading -= SHARED_ON_PURPOSE
clashes = {}
for path in glob.glob('templates/*.html'):
    if path.endswith('new_sale.html'):
        continue
    page = open(path, encoding='utf-8').read()
    for name in leading:
        if re.search(r'class="[^"]*(?<![\w-])' + re.escape(name) + r'(?![\w-])', page):
            clashes.setdefault(name, []).append(path)
check(f'TC-22.13 no New Sale style name ({len(leading)} checked) is used on another page {clashes or ""}', not clashes and len(leading) > 30)
rest = css.replace(block, '')
check('TC-22.13 ... and no other part of theme.css styles the New Sale bar names',
      not re.search(r'\.(tile-bar|tile-note|tile-stock)\b', rest))

finish('NEW SALE')
