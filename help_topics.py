"""The help for every page (v0.32.0, F29, DEC-034): what the page is for, the main steps, and a picture of it.

The ? button on each page opens the topic for that page in a side panel; the Help page (/help) shows them all.
The words are plain text: templates escape them like everything else (rule S11), so no HTML goes in here.

Each topic:
    key        also the picture's name: static/help/<key>.webp (a screenshot of the demo shop, never a real shop's, rule P2)
    title      the page's name as the menu shows it
    icon       the same Bootstrap icon as in the menu
    admins     True when only admins can open the page; a cashier's Help leaves those topics out
    endpoints  the pages it explains (Flask endpoint names), so the ? button knows which topic to open
    summary    one sentence: what the page is for
    steps      (who, text): who is 'all', 'admin' or 'cashier', so a cashier sees only what they can do
    note       one extra sentence, or ''
"""

TOPICS = [
    {'key': 'login', 'title': 'Logging in', 'icon': 'bi-box-arrow-in-right', 'admins': False,
     'endpoints': ['accounts.login', 'accounts.verify', 'accounts.forgot_password', 'accounts.forgot_code',
                   'accounts.choose_password', 'users.signup'],
     'summary': 'Everyone logs in with their username and password, then a 6-digit code sent to their email.',
     'steps': [('all', 'Type your username and password, then press Log in.'),
               ('all', 'Open the email "Your login code" and type the 6 digits. A code works for 10 minutes, once.'),
               ('all', 'On your own computer, tick "Trust this device": for a while the password alone is enough there.'),
               ('all', 'Forgot your password? Press "Forgot your password?" and a code to choose a new one is emailed to you.'),
               ('all', 'New staff join from the invitation link in their email; nobody can make their own account.')],
     'note': 'No internet? Use one of your printed backup codes instead of the emailed code.'},

    {'key': 'home', 'title': 'Home', 'icon': 'bi-house-door', 'admins': False,
     'endpoints': ['reports.home'],
     'summary': 'The shop at a glance: today\'s money, what is running low, and shortcuts to the pages used most.',
     'steps': [('all', 'Check "Revenue today" and today\'s number of sales.'),
               ('admin', 'A warning shows when ingredients run low; open Ingredients to restock them.'),
               ('cashier', 'A warning shows when ingredients run low; tell an admin so they can restock.'),
               ('admin', 'Use the shortcuts to start a sale, check the products or open the Sales Report.'),
               ('cashier', 'Use the shortcuts to start a sale or check the products.')],
     'note': ''},

    {'key': 'new_sale', 'title': 'New Sale', 'icon': 'bi-cart-plus', 'admins': False,
     'endpoints': ['sales.new_sale'],
     'summary': 'Ring up a customer: tap the drinks and food, choose how they pay, and print the receipt.',
     'steps': [('all', 'Tap a product tile to add it. Search or pick a category to find it faster.'),
               ('all', 'For a drink, tap + Hot or + Iced. For extras (oat milk, a syrup), tap its line in the order, choose them and press Done.'),
               ('all', 'Use − and + for the number, or Undo the last change.'),
               ('all', 'Choose Cash and type what the customer gave (the change is worked out), or GCash and its 13-digit reference.'),
               ('all', 'Press Complete Sale. The stock and ingredients go down and the receipt opens.')],
     'note': 'A product greys out when there is not enough of an ingredient to make it.'},

    {'key': 'receipt', 'title': 'Receipt, voids and refunds', 'icon': 'bi-receipt-cutoff', 'admins': False,
     'endpoints': ['sales.receipt', 'adjustments.slip'],
     'summary': 'The receipt of one sale, to print or reprint. A mistake is undone with a void (today) or a refund (later).',
     'steps': [('all', 'Press Print Receipt; only the receipt is printed.'),
               ('cashier', 'Rang up the wrong thing today? Press the Void button under the receipt, write the reason and press Ask for a void.'),
               ('cashier', 'An admin approves it on their screen, or emails you a code: type it and press Approve with the code.'),
               ('admin', 'Void now cancels today\'s sale at once (your password needed); the stock goes back on the shelf.'),
               ('admin', 'Refund items gives money back for some items of an older receipt.'),
               ('all', 'Every void or refund gets its own slip; the receipt itself never changes.')],
     'note': 'No money is given back until an admin approves.'},

    {'key': 'todays_receipts', 'title': 'Today\'s receipts', 'icon': 'bi-receipt', 'admins': False,
     'endpoints': ['adjustments.todays_receipts'],
     'summary': 'Every sale made today, newest first, to find a receipt quickly.',
     'steps': [('all', 'Find the sale by its time, its total or who served it.'),
               ('all', 'Open it to print it again or to ask for a void.'),
               ('all', 'The Status column shows a void waiting for approval, or one already done.')],
     'note': ''},

    {'key': 'products', 'title': 'Products', 'icon': 'bi-box-seam', 'admins': False,
     'endpoints': ['catalog.products'],
     'summary': 'The menu: every product with its price and how many can be sold now.',
     'steps': [('all', 'For drinks, the number you can still make is worked out from the ingredients on hand.'),
               ('admin', 'Press Add Product for a new item, or Edit and Delete on its row.'),
               ('admin', 'The recipe icon opens what one serving uses.'),
               ('cashier', 'Cashiers can look but not change anything ("View only").')],
     'note': 'A product that has been sold can\'t be deleted, so old receipts stay correct.'},

    {'key': 'product_form', 'title': 'Adding or changing a product', 'icon': 'bi-pencil-square', 'admins': True,
     'endpoints': ['catalog.add_product', 'catalog.edit_product'],
     'summary': 'The name, code (SKU), price, category and picture of one product.',
     'steps': [('admin', 'Fill in the name, a short unique code and the price.'),
               ('admin', 'Choose the category; drinks get servings and add-ons on New Sale.'),
               ('admin', 'Add a picture if you like (PNG, JPG or WebP, up to 2 MB).'),
               ('admin', 'Press Add Product or Save. Old receipts keep the old price.')],
     'note': ''},

    {'key': 'sales_report', 'title': 'Sales Report', 'icon': 'bi-bar-chart-line', 'admins': True,
     'endpoints': ['reports.sales_report'],
     'summary': 'How much the shop earned for any dates, how people paid, the best sellers, and voids waiting for you.',
     'steps': [('admin', 'Voids waiting for you are at the top: type your password to approve, or Reject.'),
               ('admin', 'Choose the dates and press Show.'),
               ('admin', 'Read the money in, voids, refunds and the net, split into Cash and GCash.'),
               ('admin', 'Top products and every sale are listed below; open a receipt from its number.')],
     'note': 'The red number beside Sales Report in the menu counts the voids waiting.'},

    {'key': 'refund', 'title': 'Refund', 'icon': 'bi-arrow-counterclockwise', 'admins': True,
     'endpoints': ['adjustments.refund'],
     'summary': 'Give money back for some or all items of an earlier receipt.',
     'steps': [('admin', 'Type how many of each item come back.'),
               ('admin', 'Choose whether each goes back on the shelf or is thrown away (waste).'),
               ('admin', 'Write the reason, choose Cash or GCash, type your password and press Refund.')],
     'note': 'The original receipt stays as it was; the refund prints its own slip.'},

    {'key': 'options', 'title': 'Servings & Add-ons', 'icon': 'bi-sliders', 'admins': True,
     'endpoints': ['catalog.manage_options'],
     'summary': 'The servings (Hot, Iced, sizes) and add-ons offered for drinks, with their extra price.',
     'steps': [('admin', 'Change a name or extra price and press Save on its row.'),
               ('admin', 'Add a new serving or add-on at the bottom of its list.'),
               ('admin', 'A serving\'s "recipe scale" makes a bigger cup use more of every ingredient.'),
               ('admin', 'Hide an option you no longer sell; old receipts still show it.')],
     'note': ''},

    {'key': 'recipe', 'title': 'Recipes', 'icon': 'bi-list-check', 'admins': True,
     'endpoints': ['ingredients.edit_recipe'],
     'summary': 'What one serving of a product, or one add-on, uses from the ingredients.',
     'steps': [('admin', 'Choose an ingredient and its amount (e.g. 18 g coffee beans), then press Add.'),
               ('admin', 'Change an amount and press Save, or remove a line.'),
               ('admin', 'Every sale then takes these amounts off the ingredients by itself.')],
     'note': ''},

    {'key': 'ingredients', 'title': 'Ingredients', 'icon': 'bi-droplet-half', 'admins': True,
     'endpoints': ['ingredients.ingredients'],
     'summary': 'Everything the drinks are made from, how much is left, and what needs buying.',
     'steps': [('admin', 'The bar shows how full each one is; "Needs attention" lists the low ones first.'),
               ('admin', 'Restock: add a delivery. Count: type what is really on the shelf.'),
               ('admin', 'A count can be undone for 5 minutes if it was typed wrong.'),
               ('admin', 'New ingredient adds one, with its unit and when to warn.')],
     'note': 'Every change is kept in the history with who made it.'},

    {'key': 'ingredient_detail', 'title': 'Ingredient history', 'icon': 'bi-clock-history', 'admins': True,
     'endpoints': ['ingredients.ingredient_detail', 'ingredients.ingredients_history'],
     'summary': 'Every change to the ingredients: sales, deliveries and counts, newest first.',
     'steps': [('admin', 'Open one ingredient to see the recipes that use it and its latest changes.'),
               ('admin', 'The history shows each change with when, why and who.'),
               ('admin', 'Pick an ingredient or a reason (sale, restock, count) and press Show to narrow it down.')],
     'note': ''},

    {'key': 'shop_settings', 'title': 'Shop details', 'icon': 'bi-shop', 'admins': True,
     'endpoints': ['shop.shop_settings'],
     'summary': 'The shop\'s name, address, TIN and footer printed on every receipt.',
     'steps': [('admin', 'Fill in the details and press Save shop details.'),
               ('admin', 'They appear on every receipt, old ones too when reprinted.')],
     'note': 'Every receipt also says "This is not an official receipt": official invoices come from the shop\'s registered POS.'},

    {'key': 'email_settings', 'title': 'Email', 'icon': 'bi-envelope', 'admins': True,
     'endpoints': ['shop.email_settings'],
     'summary': 'How the shop sends email (login codes, invitations), and a test message to check it works.',
     'steps': [('admin', 'Check the mail server and the address it sends from.'),
               ('admin', 'Type an address and press Send test message.'),
               ('admin', 'The settings are entered once on the shop\'s computer when the system is set up; the password is never shown here.')],
     'note': 'For Gmail, use an App Password, not the account\'s normal password.'},

    {'key': 'users', 'title': 'Users', 'icon': 'bi-people', 'admins': True,
     'endpoints': ['users.users'],
     'summary': 'Everyone who can log in, and inviting new staff.',
     'steps': [('admin', 'Invite someone: type their own email, choose Cashier or Admin, press Invite.'),
               ('admin', 'They get a link by email to choose their username and password.'),
               ('admin', 'Change a role, switch an account off, or make someone choose a new password.'),
               ('admin', 'The owner\'s account can\'t be switched off or made a cashier.')],
     'note': 'Only the owner, or an admin the owner allowed, can invite people.'},

    {'key': 'audit', 'title': 'Audit log', 'icon': 'bi-journal-text', 'admins': True,
     'endpoints': ['users.audit'],
     'summary': 'Who changed what, and when: prices, recipes, shop details, accounts, voids and refunds.',
     'steps': [('admin', 'Each line shows the person, the change, and the old and new values.'),
               ('admin', 'Choose a person or an area and press Show.'),
               ('admin', 'Lines are never edited or deleted.')],
     'note': 'Sales are on their receipts and in the Sales Report, not here.'},

    {'key': 'profile', 'title': 'Your profile', 'icon': 'bi-person-circle', 'admins': False,
     'endpoints': ['accounts.profile', 'accounts.authenticator_start', 'accounts.backup_codes'],
     'summary': 'Your own picture, email, password and how you log in.',
     'steps': [('all', 'Upload a picture, or confirm your email with a code.'),
               ('all', 'Change your password (at least 8 characters).'),
               ('all', 'Make backup codes and print them, for when there is no internet.'),
               ('all', 'Trusted devices lists the browsers that skip the code; remove one you no longer use.'),
               ('all', 'Log out everywhere if you think someone else knows your password.')],
     'note': ''},
]

BY_KEY = {topic['key']: topic for topic in TOPICS}
BY_ENDPOINT = {endpoint: topic for topic in TOPICS for endpoint in topic['endpoints']}


def topics_for(user):
    """The topics this person may read: everything for an admin; a cashier or a visitor gets no admin pages (v0.32.0)."""
    is_admin = bool(getattr(user, 'is_authenticated', False) and user.is_admin)
    return [topic for topic in TOPICS if is_admin or not topic['admins']]


def steps_for(topic, user):
    """The steps this person can do on that page: an admin's steps or a cashier's, plus the ones for everyone."""
    is_admin = bool(getattr(user, 'is_authenticated', False) and user.is_admin)
    return [text for who, text in topic['steps'] if who == 'all' or who == ('admin' if is_admin else 'cashier')]
