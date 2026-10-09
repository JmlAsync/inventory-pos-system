"""Profile pictures (feature F10, test cases TC-11.x). Starts from an old database to test the upgrade."""
import os, io, sqlite3
from helpers import check, finish, text, fixture
from app import app, upgrade_database, AVATAR_FOLDER
app.config['CSRF_ENABLED'] = False  # tests post forms directly (v0.13.2); test_security.py checks tokens
from models import db, User, Product
from werkzeug.security import generate_password_hash as g
app.config['PROPAGATE_EXCEPTIONS']=False
# --- old database (as on Yesha's computer before v0.8.0 cash columns & v0.12 avatar)
os.makedirs('instance',exist_ok=True)
c=sqlite3.connect('instance/inventory.db'); c.executescript("""
CREATE TABLE product (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, sku VARCHAR(50) NOT NULL UNIQUE, price FLOAT NOT NULL, quantity INTEGER, category VARCHAR(50));
CREATE TABLE user (id INTEGER PRIMARY KEY, username VARCHAR(50) NOT NULL UNIQUE, password_hash VARCHAR(200) NOT NULL, role VARCHAR(20) NOT NULL);
CREATE TABLE sale (id INTEGER NOT NULL PRIMARY KEY, created_at DATETIME NOT NULL, user_id INTEGER NOT NULL, total FLOAT NOT NULL);
INSERT INTO sale VALUES (1,'2026-10-08 10:00:00',1,12.5);
"""); c.execute("INSERT INTO user VALUES (1,'admin',?,'admin')",(g('admin123'),)); c.execute("INSERT INTO user VALUES (2,'maria.santos',?,'cashier')",(g('p'),)); c.commit(); c.close()
with app.app_context():
    upgrade_database(); upgrade_database()   # twice: must be safe
    cols=lambda t:[x['name'] for x in db.inspect(db.engine).get_columns(t)]
    check("old DB upgraded: user.avatar + sale cash columns added", 'avatar' in cols('user') and 'cash_received' in cols('sale') and 'change_due' in cols('sale'))
    check("existing data kept", User.query.count()==2)
    check("initials admin->AD, maria.santos->MS", (db.session.get(User,1).initials, db.session.get(User,2).initials)==('AD','MS'))
    db.session.add(Product(name='X',sku='X',price=1,quantity=5)); db.session.commit()
PNG=b'\x89PNG\r\n\x1a\n'+b'\x00'*100; JPG=b'\xff\xd8\xff\xe0'+b'\x00'*100; WEBP=b'RIFF\x00\x00\x00\x00WEBPVP8 '+b'\x00'*100
v=app.test_client(); check("profile needs login", v.get('/profile').status_code==302)
a=app.test_client(); a.post('/login',data={'username':'admin','password':'admin123'})
h=a.get('/products').get_data(as_text=True); check("navbar shows initials circle + menu", '>AD</span>' in h and 'Change picture' in h and 'Log out' in h)
def up(cl,data,name): return cl.post('/profile',data={'picture':(io.BytesIO(data),name)},content_type='multipart/form-data',follow_redirects=True)
r=up(a,PNG,'me.png'); h=r.get_data(as_text=True)
with app.app_context(): f1=db.session.get(User,1).avatar
check("PNG accepted, saved with random name, message", f1 and f1.startswith('user1_') and f1.endswith('.png') and os.path.exists(os.path.join(AVATAR_FOLDER,f1)) and 'Profile picture updated' in h)
check("navbar now shows <img>", f'avatars/{f1}' in a.get('/products').get_data(as_text=True))
r=up(a,JPG,'x.jpeg')
with app.app_context(): f2=db.session.get(User,1).avatar
check("JPG replaces it and old file deleted", f2.endswith('.jpg') and not os.path.exists(os.path.join(AVATAR_FOLDER,f1)))
r=up(a,b'<?php echo 1; ?> not an image','evil.png'); h=r.get_data(as_text=True)
with app.app_context(): check("fake .png refused, picture unchanged", "isn&#39;t a PNG, JPG or WebP" in h and db.session.get(User,1).avatar==f2)
r=up(a,b'GIF89a......','anim.gif'); check("GIF refused", "isn&#39;t a PNG" in r.get_data(as_text=True))
r=a.post('/profile',data={},content_type='multipart/form-data',follow_redirects=True); check("no file -> message", 'Choose a picture first' in r.get_data(as_text=True))
r=up(a,PNG+b'\x00'*(2*1024*1024),'big.png'); check("over 2 MB -> friendly message, no crash", r.status_code==200 and 'too big' in r.get_data(as_text=True))
c2=app.test_client(); c2.post('/login',data={'username':'maria.santos','password':'p'})
r=up(c2,WEBP,'w.webp')
with app.app_context(): fm=db.session.get(User,2).avatar
check("cashier can set own picture (WebP); admin's untouched", fm.startswith('user2_') and fm.endswith('.webp'))
os.remove(os.path.join(AVATAR_FOLDER,fm)); check("missing file falls back to initials", '>MS</span>' in c2.get('/products').get_data(as_text=True))
r=a.post('/profile/remove',follow_redirects=True)
with app.app_context(): check("remove deletes file and clears column", db.session.get(User,1).avatar is None and not os.path.exists(os.path.join(AVATAR_FOLDER,f2)))
check("GET /profile/remove not allowed", a.get('/profile/remove').status_code==405)
check("cash sale still works after upgrade", a.post('/sales/new',data={'product_id':'1','quantity':'1'}).status_code==302 and a.post('/sales/complete',data={'cash_received':'5'}).status_code==302)
finish('AVATAR')
