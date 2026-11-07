"""HireLoop: HTTP server and REST API. Python 3.10+, standard library only."""
import argparse
import csv
import hashlib
import hmac
import io
import ipaddress
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import closing
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from seed import seed

# Absolute paths, so the server works from any working directory.
ROOT = Path(__file__).resolve().parent
# JOBBOARD_DB lets a host keep the database on a persistent disk.
DB_PATH = Path(os.environ.get('JOBBOARD_DB', str(ROOT / 'data' / 'hireloop.sqlite3')))
PUBLIC = ROOT / 'public'

# Allowlist of writable columns: SQL identifiers never come from the client.
RESOURCES = {
    'companies': ['name','industry','location','website','description','color'],
    'categories': ['name'],
    'people': ['name','email','phone','role','company_id','headline','location','bio','website'],
    'ads': ['company_id','category_id','contact_id','title','summary','description','requirements','location','contract','work_mode','salary_min','salary_max','working_time','featured','status'],
    'applications': ['ad_id','person_id','message','status','notes'],
}
# Fields required on creation; PATCH only checks the fields it receives.
REQUIRED = {
    'companies': ['name','industry','location','description'], 'categories': ['name'],
    'people': ['name','email'],
    'ads': ['company_id','category_id','contact_id','title','summary','description','requirements','location','contract','work_mode','salary_min','salary_max'],
    'applications': ['ad_id','person_id','message'],
}
CONTRACTS = ('CDI','CDD','Stage','Alternance','Freelance')
WORK_MODES = ('Hybride','Sur site','Télétravail')
ROLES = ('candidate','admin','company_admin')
AD_STATUSES = ('draft','published','closed')
APPLICATION_STATUSES = ('Reçue','En cours','Entretien','Acceptée','Refusée')
FINAL_STATUSES = ('Acceptée','Refusée')
INTEGER_FIELDS = ('company_id','category_id','contact_id','ad_id','person_id','salary_min','salary_max','featured')
# Per-field length limits; other text fields accept up to 12,000 characters.
MAX_LENGTH = {'name':160,'email':254,'phone':40,'title':160,'headline':160,'location':120,'industry':120,
              'website':300,'working_time':60,'summary':500,'password':200,'color':7}

EMAIL = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
PHONE = re.compile(r'^[0-9+().\s-]*$')
# Abuse limits: (maximum count, window in seconds).
LOGIN_FAILURE_LIMIT = (15, 300)
SIGNUP_LIMIT = (10, 3600)
APPLICATION_ACCOUNT_LIMIT = (20, 3600)
APPLICATION_IP_LIMIT = (60, 3600)

# Each job ad joined with its company and category.
AD_SELECT = '''SELECT a.*, c.name AS company_name,c.color AS company_color,c.industry,
 c.description AS company_description,c.website AS company_website,c.location AS company_location,k.name AS category_name
 FROM ads a JOIN companies c ON c.id=a.company_id JOIN categories k ON k.id=a.category_id'''
# Public columns of a person: password_hash is deliberately excluded.
PERSON_COLUMNS = 'id,name,email,phone,role,company_id,headline,location,bio,website,last_login_at,created_at'

# Admin lists read from these enriched sources so the UI gets names instead of bare IDs.
# Scope rules (see Handler.scope) use unqualified column names that exist in every source.
LIST_SOURCES = {
    'ads': '''SELECT a.*, c.name AS company_name, c.color AS company_color, k.name AS category_name,
        p.name AS contact_name,
        (SELECT count(*) FROM applications x WHERE x.ad_id=a.id) AS applications_count,
        (SELECT count(*) FROM applications x WHERE x.ad_id=a.id AND x.status='Reçue') AS new_applications
        FROM ads a JOIN companies c ON c.id=a.company_id JOIN categories k ON k.id=a.category_id
        JOIN people p ON p.id=a.contact_id''',
    'applications': '''SELECT x.*, a.title AS ad_title, a.company_id, c.name AS company_name, c.color AS company_color
        FROM applications x JOIN ads a ON a.id=x.ad_id JOIN companies c ON c.id=a.company_id''',
    'people': f'''SELECT {", ".join("p." + c for c in PERSON_COLUMNS.split(","))}, c.name AS company_name,
        (SELECT count(*) FROM applications x WHERE x.person_id=p.id) AS applications_count
        FROM people p LEFT JOIN companies c ON c.id=p.company_id''',
    'companies': '''SELECT c.*,
        (SELECT count(*) FROM ads a WHERE a.company_id=c.id AND a.status='published') AS open_ads,
        (SELECT count(*) FROM ads a WHERE a.company_id=c.id) AS ads_count,
        (SELECT count(*) FROM people p WHERE p.company_id=c.id) AS members
        FROM companies c''',
    'categories': '''SELECT k.*, (SELECT count(*) FROM ads a WHERE a.category_id=k.id) AS ads_count FROM categories k''',
}
LIST_FILTERS = {
    'ads': ('status','company_id','category_id','contract'),
    'applications': ('status','ad_id','company_id'),
    'people': ('role','company_id'),
    'companies': (), 'categories': (),
}
LIST_SEARCH = {
    'ads': ('title','company_name','location'),
    'applications': ('applicant_name','applicant_email','ad_title'),
    'people': ('name','email'),
    'companies': ('name','industry','location'),
    'categories': ('name',),
}

# Columns added after the first release, for databases created by older versions.
COLUMN_MIGRATIONS = [
    ('people','headline',"TEXT NOT NULL DEFAULT ''"),
    ('people','location',"TEXT NOT NULL DEFAULT ''"),
    ('people','bio',"TEXT NOT NULL DEFAULT ''"),
    ('people','website',"TEXT NOT NULL DEFAULT ''"),
    ('people','last_login_at',"TEXT NOT NULL DEFAULT ''"),
    ('people','applications_seen_at',"TEXT NOT NULL DEFAULT ''"),
    ('ads','status',"TEXT NOT NULL DEFAULT 'published' CHECK (status IN ('draft','published','closed'))"),
    ('ads','views','INTEGER NOT NULL DEFAULT 0'),
    ('ads','updated_at',"TEXT NOT NULL DEFAULT ''"),
    ('applications','notes',"TEXT NOT NULL DEFAULT ''"),
    ('applications','status_updated_at',"TEXT NOT NULL DEFAULT ''"),
]


def now_iso(offset=0):
    # UTC timestamp in the same format SQLite stores; offset is in seconds.
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() + offset))


def hash_password(password):
    # PBKDF2 with a random salt, stored as "salt$digest".
    salt = secrets.token_hex(16)
    value = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000).hex()
    return f'{salt}${value}'


def verify_password(password, stored):
    if not stored or not isinstance(password, str) or stored.count('$') != 1:
        return False
    salt, value = stored.split('$')
    # Constant-time comparison.
    return hmac.compare_digest(hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000).hex(), value)


def connect():
    # The caller is responsible for closing the connection.
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db


def initialize():
    # Creates or upgrades the database, then adds the production admin or the demo data.
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as db, db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript((ROOT / 'schema.sql').read_text(encoding='utf-8'))
        migrate_people(db)
        migrate_application_contacts(db)
        migrate_columns(db)
        # In production there are no demo accounts: the first admin comes from secret variables.
        if os.environ.get('JOBBOARD_ENV') == 'production':
            if not db.execute('SELECT 1 FROM people LIMIT 1').fetchone():
                email = os.environ.get('ADMIN_EMAIL', '').strip().lower()
                password = os.environ.get('ADMIN_PASSWORD', '')
                if not EMAIL.fullmatch(email) or len(password) < 16:
                    raise RuntimeError('Set ADMIN_EMAIL and ADMIN_PASSWORD (at least 16 characters) before first production startup.')
                db.execute('INSERT INTO people(name,email,phone,password_hash,role) VALUES(?,?,?,?,?)',
                           ('Administrator', email, '', hash_password(password), 'admin'))
        else:
            seed(db)
        backfill_events(db)


def migrate_application_contacts(db):
    # Copies the candidate's name, email and phone into applications created before these columns existed.
    columns = {r['name'] for r in db.execute('PRAGMA table_info(applications)')}
    for field, person_field in (('applicant_name', 'name'), ('applicant_email', 'email'), ('applicant_phone', 'phone')):
        if field not in columns:
            db.execute(f"ALTER TABLE applications ADD COLUMN {field} TEXT NOT NULL DEFAULT ''")
            db.execute(f'UPDATE applications SET {field}=(SELECT {person_field} FROM people WHERE people.id=applications.person_id)')


def migrate_columns(db):
    # Adds missing columns one by one; existing rows keep their data.
    for table, column, definition in COLUMN_MIGRATIONS:
        if column not in {r['name'] for r in db.execute(f'PRAGMA table_info({table})')}:
            db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
    db.execute("UPDATE ads SET updated_at=created_at WHERE updated_at=''")
    db.execute('CREATE INDEX IF NOT EXISTS idx_ads_status ON ads (status, featured DESC, created_at DESC)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_applications_status ON applications (status)')


def backfill_events(db):
    # Every application has at least one history entry: its current status at creation time.
    db.execute('''INSERT INTO application_events(application_id,status,created_at)
        SELECT id,status,created_at FROM applications
        WHERE id NOT IN (SELECT application_id FROM application_events)''')


def migrate_people(db):
    """Upgrade the legacy role constraint without changing IDs or related records."""
    if 'company_id' in {r['name'] for r in db.execute('PRAGMA table_info(people)')}:
        return
    # Finish the open transaction before turning off foreign keys for the table swap.
    db.commit()
    db.execute('PRAGMA foreign_keys=OFF')
    try:
        db.execute('BEGIN')
        definition = (ROOT / 'schema.sql').read_text(encoding='utf-8').split('CREATE TABLE', 2)[1]
        definition = definition.replace('IF NOT EXISTS people', 'people_new').strip()
        db.execute('CREATE TABLE ' + definition)
        columns = 'id,name,email,phone,password_hash,role,created_at'
        db.execute(f'INSERT INTO people_new({columns}) SELECT {columns} FROM people')
        db.execute('DROP TABLE people')
        db.execute('ALTER TABLE people_new RENAME TO people')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('Migration : relations invalides.')
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.execute('PRAGMA foreign_keys=ON')


class APIError(Exception):
    # Expected business error, returned to the browser with its HTTP status.
    def __init__(self, status, message):
        self.status, self.message = status, message


class Raw:
    # Non-JSON response body, such as a CSV export.
    def __init__(self, content_type, body, filename=None):
        self.content_type, self.body, self.filename = content_type, body, filename


def csv_safe(value):
    # Spreadsheets run cells that start with these characters as formulas.
    text = '' if value is None else str(value)
    return "'" + text if text[:1] in ('=', '+', '-', '@', '\t', '\r') else text


class Handler(BaseHTTPRequestHandler):
    server_version = 'HireLoop/2.0'

    # ------------------------------------------------------------------ responses
    def send_json(self, status, data, cookie=None):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        # API responses can contain personal data.
        self.send_header('Cache-Control','no-store')
        if cookie:
            self.send_header('Set-Cookie',cookie)
        self.security_headers()
        self.end_headers()
        self.wfile.write(body)

    def send_raw(self, status, raw):
        self.send_response(status)
        self.send_header('Content-Type', raw.content_type)
        self.send_header('Content-Length', str(len(raw.body)))
        self.send_header('Cache-Control','no-store')
        if raw.filename:
            self.send_header('Content-Disposition', f'attachment; filename="{raw.filename}"')
        self.security_headers()
        self.end_headers()
        self.wfile.write(raw.body)

    def security_headers(self):
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','same-origin')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")

    def body(self):
        # Reads a JSON object body of at most 64 KiB.
        try:
            length = int(self.headers.get('Content-Length','0'))
            if length < 0:
                raise APIError(400,'Longueur de requête invalide.')
            if length > 65536:
                raise APIError(413,'Le formulaire est trop volumineux.')
            if 'application/json' not in self.headers.get('Content-Type',''):
                raise APIError(415,'Utilisez Content-Type: application/json.')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data,dict):
                raise ValueError()
            return data
        except (ValueError, json.JSONDecodeError):
            raise APIError(400,'Corps JSON invalide.')

    # ------------------------------------------------------------------ visitors and limits
    def client_ip(self):
        # TRUST_PROXY=1 only behind a proxy: otherwise this header can be forged.
        headers = getattr(self, 'headers', None)
        if os.environ.get('TRUST_PROXY') == '1' and headers:
            # The proxy appends the real address on the right; forged values stay on the left
            # and the proxy's internal hops are private addresses.
            for part in reversed(','.join(headers.get_all('X-Forwarded-For') or []).split(',')):
                try:
                    address = ipaddress.ip_address(part.strip())
                except ValueError:
                    continue
                if not address.is_private:
                    return str(address)
        return self.client_address[0]

    def address_string(self):
        return self.client_ip()

    def rate_check(self, bucket, key, limit, message, record=True):
        # Refuses the request when the limit is reached; record=True also counts this attempt.
        maximum, window = limit
        now = time.time()
        with self.server.rate_lock:
            hits = self.server.rate_hits
            if len(hits) > 10000:
                for stale in [k for k, v in hits.items() if not v or v[-1] < now - 3600]:
                    del hits[stale]
            recent = [t for t in hits.get((bucket, key), []) if t > now - window]
            hits[(bucket, key)] = recent
            if len(recent) >= maximum:
                raise APIError(429, message)
            if record:
                recent.append(now)

    def rate_record(self, bucket, key):
        with self.server.rate_lock:
            self.server.rate_hits.setdefault((bucket, key), []).append(time.time())

    # ------------------------------------------------------------------ sessions
    def session_token_hash(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie',''))
            return hashlib.sha256(cookie['hireloop_session'].value.encode()).hexdigest()
        except (KeyError, CookieError):
            return None

    def revoke_sessions(self, db, person):
        # Ends a person's sessions, except the one making this request.
        db.execute('DELETE FROM sessions WHERE person_id=? AND token_hash IS NOT ?',(person,self.session_token_hash()))

    def current_user(self, db):
        token_hash = self.session_token_hash()
        if not token_hash:
            return None
        return db.execute(f'SELECT {", ".join("p."+x for x in PERSON_COLUMNS.split(","))} FROM people p JOIN sessions s ON s.person_id=p.id WHERE s.token_hash=? AND s.expires_at>?',
            (token_hash, int(time.time()))).fetchone()

    def require_user(self, db, admin=False):
        user = self.current_user(db)
        if not user:
            raise APIError(401,'Connectez-vous pour accéder à cette page.')
        if admin and user['role'] not in ('admin', 'company_admin'):
            raise APIError(403,'Cet espace est réservé aux administrateurs.')
        return user

    def new_session(self, db, person):
        # 24-hour session: the raw token stays in the cookie, only its hash is stored.
        token = secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE expires_at<?',(int(time.time()),))
        db.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),person,int(time.time())+86400))
        secure = '; Secure' if os.environ.get('COOKIE_SECURE') == '1' else ''
        return f'hireloop_session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=86400{secure}'

    @staticmethod
    def expired_cookie():
        return 'hireloop_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'

    # ------------------------------------------------------------------ validation
    def validate(self, resource, data, partial=False):
        # Checks allowed fields, types and formats; returns values ready for SQLite.
        allowed = RESOURCES[resource] + (['password'] if resource == 'people' else [])
        unknown = set(data) - set(allowed)
        if unknown:
            raise APIError(400,'Champ inconnu : '+', '.join(sorted(unknown)))
        cleaned = {}
        for key,value in data.items():
            if resource == 'people' and key == 'company_id' and value in (None, ''):
                cleaned[key] = None
                continue
            if key in INTEGER_FIELDS:
                # Booleans are refused even though Python treats them as integers.
                if isinstance(value,bool) or not str(value).isdigit():
                    raise APIError(400,f'{key} doit être un entier positif.')
                value = int(value)
            else:
                if not isinstance(value,str) or len(value) > 12000:
                    raise APIError(400,f'Valeur invalide pour {key}.')
                # Passwords are kept exactly as typed.
                value = value if key == 'password' else value.strip()
                if len(value) > MAX_LENGTH.get(key, 12000):
                    raise APIError(400,f'Texte trop long pour {key}.')
            cleaned[key] = value
        for key in REQUIRED[resource]:
            if (not partial or key in cleaned) and (key not in cleaned or cleaned[key] == ''):
                raise APIError(400,f'Champ obligatoire : {key}.')
        enums = {'contract': CONTRACTS, 'work_mode': WORK_MODES, 'role': ROLES}
        if resource == 'ads':
            enums['status'] = AD_STATUSES
        if resource == 'applications':
            enums['status'] = APPLICATION_STATUSES
        for key, choices in enums.items():
            if key in cleaned and cleaned[key] not in choices:
                raise APIError(400,f'Valeur non autorisée pour {key}.')
        if 'featured' in cleaned and cleaned['featured'] not in (0, 1):
            raise APIError(400,'Valeur non autorisée pour featured.')
        if 'email' in cleaned:
            cleaned['email'] = cleaned['email'].lower()
            if not EMAIL.fullmatch(cleaned['email']):
                raise APIError(400,'Adresse e-mail invalide.')
        if 'phone' in cleaned and not PHONE.fullmatch(cleaned['phone']):
            raise APIError(400,'Numéro de téléphone invalide.')
        if 'password' in cleaned:
            if len(cleaned['password']) < 10:
                raise APIError(400,'Le mot de passe doit contenir au moins 10 caractères.')
            cleaned['password_hash'] = hash_password(cleaned.pop('password'))
        if 'website' in cleaned and cleaned['website'] and not re.match(r'^https?://[^\s]+$',cleaned['website']):
            raise APIError(400,'Le site doit commencer par https:// ou http://.')
        if 'color' in cleaned and not re.fullmatch(r'#[0-9a-fA-F]{6}',cleaned['color']):
            raise APIError(400,'Couleur invalide (exemple : #355d50).')
        return cleaned

    # ------------------------------------------------------------------ reading records
    def record(self,db,resource,ident):
        # Reads one row by ID, without the password hash; 404 if it does not exist.
        columns = PERSON_COLUMNS if resource == 'people' else '*'
        row = db.execute(f'SELECT {columns} FROM {resource} WHERE id=?',(ident,)).fetchone()
        if not row:
            raise APIError(404,'Cet enregistrement n’existe pas.')
        return dict(row)

    def admin_record(self, db, resource, ident):
        # Enriched version of a record for the admin area.
        row = db.execute(f'SELECT * FROM ({LIST_SOURCES[resource]}) t WHERE id=?', (ident,)).fetchone()
        if not row:
            raise APIError(404,'Cet enregistrement n’existe pas.')
        data = dict(row)
        if resource == 'applications':
            data['events'] = self.events(db, [ident]).get(ident, [])
            person = db.execute('SELECT headline,location,bio,website FROM people WHERE id=?', (data['person_id'],)).fetchone()
            data['candidate'] = dict(person) if person else None
        return data

    def events(self, db, application_ids):
        # Status history for several applications, grouped by application.
        if not application_ids:
            return {}
        marks = ','.join('?' for _ in application_ids)
        grouped = {}
        for row in db.execute(f'''SELECT e.application_id,e.status,e.created_at,p.name AS actor_name
                FROM application_events e LEFT JOIN people p ON p.id=e.actor_id
                WHERE e.application_id IN ({marks}) ORDER BY e.created_at,e.id''', list(application_ids)):
            item = dict(row)
            grouped.setdefault(item.pop('application_id'), []).append(item)
        return grouped

    def add_event(self, db, application_id, status, actor_id=None):
        db.execute('INSERT INTO application_events(application_id,status,actor_id,created_at) VALUES(?,?,?,?)',
                   (application_id, status, actor_id, now_iso()))

    def can_manage_ad(self, user, ad):
        return bool(user) and (user['role'] == 'admin' or (user['role'] == 'company_admin' and user['company_id'] == ad['company_id']))

    # ------------------------------------------------------------------ routing
    def route(self,db,path,query):
        # Returns (HTTP status, data, optional cookie).
        method = self.command
        # /api/admin/... requires an admin before reusing the shared handlers.
        admin_view = path.startswith('/api/admin/')
        admin_user = self.require_user(db, True) if admin_view else None
        if admin_view:
            path = path.replace('/api/admin/', '/api/', 1)

        if path == '/api/health' and method == 'GET':
            db.execute('SELECT 1')
            return 200, {'status':'ok'}, None

        # ---- accounts
        if path == '/api/auth/me' and method == 'GET':
            user = self.current_user(db)
            if not user:
                return 200, {'user':None}, None
            return 200, {'user':dict(user), 'updates':self.unseen_updates(db, user['id']),
                         'saved':[r[0] for r in db.execute('SELECT ad_id FROM saved_ads WHERE person_id=?', (user['id'],))]}, None
        if path in ('/api/auth/register','/api/auth/login') and method == 'POST':
            data = self.body()
            if path.endswith('register'):
                # `role` is not accepted, which prevents privilege escalation.
                if set(data) - {'name','email','phone','password'}:
                    raise APIError(400,'Champs d’inscription invalides.')
                self.rate_check('signup',self.client_ip(),SIGNUP_LIMIT,'Trop d’inscriptions depuis cette adresse. Réessayez plus tard.')
                if not data.get('password'):
                    raise APIError(400,'Le mot de passe est obligatoire.')
                values = self.validate('people',data)
                if db.execute('SELECT 1 FROM people WHERE email=?',(values['email'],)).fetchone():
                    raise APIError(409,'Cette adresse est déjà connue. Connectez-vous ou utilisez une autre adresse.')
                values['last_login_at'] = now_iso()
                keys = list(values)
                ident = db.execute(f'INSERT INTO people({",".join(keys)}) VALUES({",".join("?" for _ in keys)})',list(values.values())).lastrowid
                cookie = self.new_session(db,ident)
                return 201, {'user':self.record(db,'people',ident)}, cookie
            email, password = data.get('email',''), data.get('password','')
            if not isinstance(email,str) or not isinstance(password,str):
                raise APIError(400,'Identifiants invalides.')
            # Only failures count, so one visitor cannot lock others out.
            ip = self.client_ip()
            self.rate_check('login',ip,LOGIN_FAILURE_LIMIT,'Trop de tentatives. Réessayez dans cinq minutes.',record=False)
            user = db.execute('SELECT * FROM people WHERE email=?',(email.strip().lower(),)).fetchone()
            if not user or not verify_password(password,user['password_hash']):
                self.rate_record('login',ip)
                raise APIError(401,'Adresse e-mail ou mot de passe incorrect.')
            db.execute('UPDATE people SET last_login_at=? WHERE id=?', (now_iso(), user['id']))
            return 200, {'user':self.record(db,'people',user['id'])}, self.new_session(db,user['id'])
        if path == '/api/auth/logout' and method == 'POST':
            db.execute('DELETE FROM sessions WHERE token_hash=?',(self.session_token_hash(),))
            return 200, {'message':'Vous êtes déconnecté.'}, self.expired_cookie()
        if path == '/api/account' and method == 'PATCH':
            user = self.require_user(db)
            data = self.body()
            if set(data) - {'name','email','phone','password','current_password','headline','location','bio','website'}:
                raise APIError(400,'Champs de profil invalides.')
            current_password = data.pop('current_password',None)
            values = self.validate('people',data,True)
            # Changing the email or password requires the current password.
            if 'password_hash' in values or ('email' in values and values['email'] != user['email'].lower()):
                if not verify_password(current_password,self.password_hash(db, user['id'])):
                    raise APIError(400,'Votre mot de passe actuel est requis pour ce changement.')
            self.update(db,'people',user['id'],values)
            if 'password_hash' in values:
                self.revoke_sessions(db,user['id'])
            return 200, {'user':self.record(db,'people',user['id'])}, None
        if path == '/api/account' and method == 'DELETE':
            user = self.require_user(db)
            data = self.body()
            if not verify_password(data.get('current_password'), self.password_hash(db, user['id'])):
                raise APIError(400,'Votre mot de passe actuel est requis pour ce changement.')
            self.protect_admin(db,'people',user['id'],{'role':'candidate'},dict(user))
            if db.execute('SELECT 1 FROM ads WHERE contact_id=? LIMIT 1', (user['id'],)).fetchone():
                raise APIError(409,'Vous êtes encore le contact d’une offre. Confiez-la à quelqu’un d’autre avant de supprimer votre compte.')
            db.execute('DELETE FROM people WHERE id=?', (user['id'],))
            return 200, {'message':'Votre compte a été supprimé.'}, self.expired_cookie()

        # ---- candidate space
        if path == '/api/my-applications' and method == 'GET':
            user = self.require_user(db)
            return 200, {'items':self.my_applications(db, user)}, None
        if path == '/api/my-applications/seen' and method == 'POST':
            user = self.require_user(db)
            db.execute('UPDATE people SET applications_seen_at=? WHERE id=?', (now_iso(), user['id']))
            return 200, {'updates':0}, None
        match = re.fullmatch(r'/api/my-applications/(\d+)', path)
        if match and method == 'DELETE':
            user = self.require_user(db)
            row = db.execute('SELECT id,status FROM applications WHERE id=? AND person_id=?', (int(match[1]), user['id'])).fetchone()
            if not row:
                raise APIError(404,'Cet enregistrement n’existe pas.')
            if row['status'] in FINAL_STATUSES:
                raise APIError(400,'Cette candidature a reçu une réponse et ne peut plus être retirée.')
            db.execute('DELETE FROM applications WHERE id=?', (row['id'],))
            return 200, {'message':'Candidature retirée.'}, None
        if path == '/api/saved' and method == 'GET':
            user = self.require_user(db)
            rows = db.execute(AD_SELECT.replace('FROM ads a', ', s.created_at AS saved_at FROM saved_ads s JOIN ads a ON a.id=s.ad_id', 1)
                              + " WHERE s.person_id=? AND a.status<>'draft' ORDER BY s.created_at DESC, a.id DESC", (user['id'],)).fetchall()
            return 200, {'items':[dict(r) for r in rows]}, None
        match = re.fullmatch(r'/api/saved/(\d+)', path)
        if match and method in ('PUT', 'DELETE'):
            user = self.require_user(db)
            ad_id = int(match[1])
            if method == 'DELETE':
                db.execute('DELETE FROM saved_ads WHERE person_id=? AND ad_id=?', (user['id'], ad_id))
                return 200, {'saved':False, 'message':'Offre retirée de vos favoris.'}, None
            ad = db.execute('SELECT status FROM ads WHERE id=?', (ad_id,)).fetchone()
            if not ad or ad['status'] == 'draft':
                raise APIError(404,'Cette offre n’existe pas.')
            db.execute('INSERT OR IGNORE INTO saved_ads(person_id,ad_id) VALUES(?,?)', (user['id'], ad_id))
            return 200, {'saved':True, 'message':'Offre sauvegardée.'}, None

        # ---- public catalogue
        if path == '/api/stats' and method == 'GET':
            if admin_view:
                counts = {}
                for table in ('ads','companies','applications','people'):
                    clause, params = self.scope(admin_user, table)
                    counts[table] = db.execute(f'SELECT count(*) FROM {table} WHERE {clause}', params).fetchone()[0]
                return 200, counts, None
            return 200, {
                'ads': db.execute("SELECT count(*) FROM ads WHERE status='published'").fetchone()[0],
                'companies': db.execute("SELECT count(DISTINCT company_id) FROM ads WHERE status='published'").fetchone()[0],
                'applications': db.execute('SELECT count(*) FROM applications').fetchone()[0],
                'people': db.execute('SELECT count(*) FROM people').fetchone()[0],
            }, None
        if path == '/api/dashboard' and method == 'GET' and admin_view:
            return 200, self.dashboard(db, admin_user), None
        if path == '/api/applications/export' and method == 'GET' and admin_view:
            return 200, self.export_applications(db, admin_user, query), None
        if path == '/api/meta' and method == 'GET':
            return 200, {
                'companies':[dict(r) for r in db.execute('SELECT id,name FROM companies ORDER BY name')],
                'categories':[dict(r) for r in db.execute("SELECT k.id,k.name,(SELECT count(*) FROM ads a WHERE a.category_id=k.id AND a.status='published') AS count FROM categories k ORDER BY k.name")],
                'locations':[r[0] for r in db.execute("SELECT DISTINCT location FROM ads WHERE status='published' ORDER BY location")],
                'contracts': list(CONTRACTS), 'work_modes': list(WORK_MODES),
                'application_statuses': list(APPLICATION_STATUSES),
            }, None
        if path == '/api/directory/companies' and method == 'GET':
            rows = db.execute('''SELECT c.id,c.name,c.industry,c.location,c.website,c.description,c.color,
                (SELECT count(*) FROM ads a WHERE a.company_id=c.id AND a.status='published') AS open_ads
                FROM companies c ORDER BY open_ads DESC, c.name''').fetchall()
            return 200, {'items':[dict(r) for r in rows]}, None
        match = re.fullmatch(r'/api/directory/companies/(\d+)', path)
        if match and method == 'GET':
            company = db.execute('SELECT id,name,industry,location,website,description,color FROM companies WHERE id=?', (int(match[1]),)).fetchone()
            if not company:
                raise APIError(404,'Cet enregistrement n’existe pas.')
            ads = db.execute(AD_SELECT+" WHERE a.company_id=? AND a.status='published' ORDER BY a.featured DESC, a.created_at DESC", (company['id'],)).fetchall()
            return 200, {**dict(company), 'ads':[dict(r) for r in ads]}, None
        match = re.fullmatch(r'/api/companies/(\d+)/ads',path)
        if match and method == 'GET':
            self.record(db,'companies',int(match[1]))
            return 200, {'items':[dict(r) for r in db.execute(AD_SELECT+" WHERE a.company_id=? AND a.status='published' ORDER BY a.id DESC",(int(match[1]),))]}, None
        match = re.fullmatch(r'/api/ads/(\d+)/similar', path)
        if match and method == 'GET':
            ad = db.execute('SELECT id,company_id,category_id,status FROM ads WHERE id=?', (int(match[1]),)).fetchone()
            if not ad or ad['status'] == 'draft':
                raise APIError(404,'Cette offre n’existe pas.')
            rows = db.execute(AD_SELECT+''' WHERE a.status='published' AND a.id<>?
                ORDER BY (a.category_id=?) DESC, (a.company_id=?) DESC, a.featured DESC, a.created_at DESC LIMIT 3''',
                (ad['id'], ad['category_id'], ad['company_id'])).fetchall()
            return 200, {'items':[dict(r) for r in rows]}, None
        match = re.fullmatch(r'/api/ads/(\d+)/applications',path)
        if match and method == 'POST':
            return self.apply(db, int(match[1]))

        # ---- generic resources: five tables, optional numeric ID
        match = re.fullmatch(r'/api/(ads|companies|categories|people|applications)(?:/(\d+))?',path)
        if not match:
            raise APIError(404,'Route introuvable.')
        resource, ident = match[1], int(match[2]) if match[2] else None
        if method == 'GET' and resource == 'ads' and ident and not admin_view:
            return 200, self.public_ad(db, ident), None
        if method == 'GET' and resource == 'ads' and not admin_view:
            return 200, self.list_ads(db, query), None
        # Beyond public routes, every generic operation requires an administrator.
        user = admin_user if admin_user is not None else self.require_user(db, True)
        clause, params = self.scope(user, resource)
        # The requested record must also belong to the admin's scope.
        if ident:
            existing = self.record(db, resource, ident)
            if not db.execute(f'SELECT id FROM {resource} WHERE ({clause}) AND id=?', params + [ident]).fetchone():
                raise APIError(403, 'Cet enregistrement appartient à une autre entreprise.')
        if user['role'] == 'company_admin' and method != 'GET':
            if resource in ('people', 'categories') or (resource in ('companies', 'applications') and method not in ('PATCH', 'PUT')):
                raise APIError(403, 'Cette action est réservée à l’administrateur du projet.')
        if method == 'GET':
            if ident:
                return 200, self.admin_record(db, resource, ident), None
            return 200, self.list_resource(db, resource, clause, params, query), None
        if method == 'POST' and not ident:
            data = self.body()
            # A recruiter's ads always belong to their company, with themselves as contact.
            if resource == 'ads' and user['role'] == 'company_admin':
                data.setdefault('company_id', user['company_id'])
                data.setdefault('contact_id', user['id'])
            values = self.validate(resource,data)
            self.authorize_values(db, user, resource, values)
            if resource == 'applications':
                person = self.record(db, 'people', values['person_id'])
                values.update(applicant_name=person['name'], applicant_email=person['email'], applicant_phone=person['phone'])
            if resource == 'ads':
                values['updated_at'] = now_iso()
            keys = list(values)
            ident = db.execute(f'INSERT INTO {resource}({",".join(keys)}) VALUES({",".join("?" for _ in keys)})',list(values.values())).lastrowid
            if resource == 'applications':
                self.add_event(db, ident, values.get('status', 'Reçue'), user['id'])
            return 201, self.admin_record(db,resource,ident), None
        if method in ('PATCH','PUT') and ident:
            values = self.validate(resource,self.body(),method=='PATCH')
            self.authorize_values(db, user, resource, values, ident, existing)
            self.protect_admin(db,resource,ident,values,existing)
            if resource == 'ads':
                merged = existing | values
                if merged['salary_max'] < merged['salary_min']:
                    raise APIError(400,'Le salaire maximum doit être supérieur au minimum.')
                values['updated_at'] = now_iso()
                # The publication date is the day a draft goes live.
                if existing['status'] == 'draft' and values.get('status') == 'published':
                    values['created_at'] = now_iso()
            status_changed = resource == 'applications' and 'status' in values and values['status'] != existing['status']
            if status_changed:
                values['status_updated_at'] = now_iso()
            self.update(db,resource,ident,values)
            if status_changed:
                self.add_event(db, ident, values['status'], user['id'])
            if resource == 'people' and 'password_hash' in values:
                self.revoke_sessions(db,ident)
            return 200, self.admin_record(db,resource,ident), None
        if method == 'DELETE' and ident:
            self.protect_admin(db,resource,ident,{'role':'candidate'},existing)
            if resource == 'people' and user['id'] == ident:
                raise APIError(400,'Vous ne pouvez pas supprimer votre propre compte administrateur.')
            db.execute(f'DELETE FROM {resource} WHERE id=?',(ident,))
            return 200,{'message':'Enregistrement supprimé.'},None
        raise APIError(405,'Méthode non autorisée.')

    # ------------------------------------------------------------------ handlers
    def password_hash(self, db, ident):
        return db.execute('SELECT password_hash FROM people WHERE id=?',(ident,)).fetchone()[0]

    def unseen_updates(self, db, person_id):
        # Applications whose status a recruiter changed since the candidate last looked.
        return db.execute('''SELECT count(*) FROM applications x JOIN people p ON p.id=x.person_id
            WHERE x.person_id=? AND x.status_updated_at<>'' AND x.status_updated_at>p.applications_seen_at''', (person_id,)).fetchone()[0]

    def public_ad(self, db, ident):
        row = db.execute(AD_SELECT+' WHERE a.id=?',(ident,)).fetchone()
        user = self.current_user(db)
        # Drafts are only visible to the people who manage them (preview).
        if not row or (row['status'] == 'draft' and not self.can_manage_ad(user, row)):
            raise APIError(404,'Cette offre n’existe pas.')
        data = dict(row)
        # Count visits from the public, not from recruiters checking their own ads.
        if row['status'] == 'published' and not (user and user['role'] in ('admin', 'company_admin')):
            db.execute('UPDATE ads SET views=views+1 WHERE id=?', (ident,))
        if user:
            application = db.execute('SELECT id,status,created_at FROM applications WHERE ad_id=? AND person_id=?', (ident, user['id'])).fetchone()
            data['viewer'] = {
                'saved': bool(db.execute('SELECT 1 FROM saved_ads WHERE ad_id=? AND person_id=?', (ident, user['id'])).fetchone()),
                'application': dict(application) if application else None,
                'can_manage': self.can_manage_ad(user, row),
            }
        return data

    def apply(self, db, ad_id):
        # Applying requires an account; contact details come from the profile.
        user = self.current_user(db)
        if not user:
            raise APIError(401,'Connectez-vous pour postuler.')
        if user['role'] != 'candidate':
            raise APIError(403,'Les candidatures sont réservées aux comptes candidats.')
        ad = db.execute('SELECT id,status FROM ads WHERE id=?', (ad_id,)).fetchone()
        if not ad or ad['status'] == 'draft':
            raise APIError(404,'Cet enregistrement n’existe pas.')
        data = self.body()
        unknown = set(data) - {'message'}
        if unknown:
            raise APIError(400,'Champ inconnu : '+', '.join(sorted(unknown)))
        message = data.get('message','')
        if not isinstance(message,str) or not 20 <= len(message.strip()) <= 12000:
            raise APIError(400,'Votre message doit contenir entre 20 et 12 000 caractères.')
        if ad['status'] != 'published':
            raise APIError(409,'Cette offre n’accepte plus de candidatures.')
        if db.execute('SELECT 1 FROM applications WHERE ad_id=? AND person_id=?', (ad_id, user['id'])).fetchone():
            raise APIError(409,'Vous avez déjà postulé à cette offre.')
        limit_message = 'Trop de candidatures envoyées. Réessayez plus tard.'
        self.rate_check('apply-account',user['id'],APPLICATION_ACCOUNT_LIMIT,limit_message)
        self.rate_check('apply-ip',self.client_ip(),APPLICATION_IP_LIMIT,limit_message)
        ident = db.execute('INSERT INTO applications(ad_id,person_id,message,applicant_name,applicant_email,applicant_phone,created_at) VALUES(?,?,?,?,?,?,?)',
            (ad_id,user['id'],message.strip(),user['name'],user['email'],user['phone'],now_iso())).lastrowid
        self.add_event(db, ident, 'Reçue', user['id'])
        application = {k: v for k, v in self.record(db,'applications',ident).items() if k != 'notes'}
        return 201, {'application':application,'message':'Votre candidature a été enregistrée et est accessible au recruteur.'}, None

    def my_applications(self, db, user):
        # Explicit columns: recruiter notes must never reach the candidate.
        rows = db.execute('''SELECT x.id,x.ad_id,x.message,x.status,x.created_at,x.status_updated_at,
            a.title,a.location,a.contract,a.work_mode,a.status AS ad_status,
            c.id AS company_id,c.name AS company_name,c.color AS company_color
            FROM applications x JOIN ads a ON a.id=x.ad_id JOIN companies c ON c.id=a.company_id
            WHERE x.person_id=? ORDER BY x.created_at DESC, x.id DESC''', (user['id'],)).fetchall()
        seen = db.execute('SELECT applications_seen_at FROM people WHERE id=?', (user['id'],)).fetchone()[0]
        items = [dict(r) for r in rows]
        history = self.events(db, [item['id'] for item in items])
        for item in items:
            item['events'] = [{k: v for k, v in e.items() if k != 'actor_name'} for e in history.get(item['id'], [])]
            item['updated'] = bool(item['status_updated_at']) and item['status_updated_at'] > seen
        return items

    def list_ads(self, db, query):
        """Fetch a page of published ads with the same filters used for its count."""
        conditions, params = ["a.status='published'"], []
        for field in ('category_id','company_id','location','contract','work_mode'):
            value = query.get(field,[''])[0]
            if value:
                conditions.append(f'a.{field}=?'); params.append(value)
        minimum = query.get('min_salary',[''])[0]
        if minimum:
            if not minimum.isdigit():
                raise APIError(400,'min_salary doit être un entier positif.')
            conditions.append('a.salary_max>=?'); params.append(int(minimum))
        term = query.get('q',[''])[0].strip()[:200]
        if term:
            conditions.append('(a.title LIKE ? OR a.summary LIKE ? OR c.name LIKE ? OR k.name LIKE ?)')
            params += ['%'+term+'%']*4
        where = ' WHERE '+' AND '.join(conditions)
        total = db.execute('SELECT count(*) FROM ads a JOIN companies c ON c.id=a.company_id JOIN categories k ON k.id=a.category_id'+where,params).fetchone()[0]
        page,limit = self.pagination(query)
        # Sorting comes from a fixed list: no client SQL is executed.
        order = {'recent':'a.created_at DESC,a.id DESC','salary':'a.salary_max DESC,a.id DESC','relevant':'a.featured DESC,a.created_at DESC,a.id DESC'}.get(query.get('sort',['relevant'])[0],'a.id DESC')
        rows = db.execute(AD_SELECT+where+f' ORDER BY {order} LIMIT ? OFFSET ?',params+[limit,(page-1)*limit]).fetchall()
        return {'items':[dict(r) for r in rows],'total':total,'page':page,'limit':limit}

    def list_resource(self, db, resource, clause, params, query):
        # Paginated admin list with search, exact filters and status counts for tabs.
        conditions, values = [f'({clause})'], list(params)
        for field in LIST_FILTERS[resource]:
            value = query.get(field, [''])[0]
            if value and field != 'status':
                conditions.append(f'{field}=?'); values.append(value)
        term = query.get('q', [''])[0].strip()[:200]
        if term:
            conditions.append('(' + ' OR '.join(f'{c} LIKE ?' for c in LIST_SEARCH[resource]) + ')')
            values += ['%' + term + '%'] * len(LIST_SEARCH[resource])
        source = f'SELECT * FROM ({LIST_SOURCES[resource]}) t'
        facets = None
        if resource in ('ads', 'applications'):
            facets = {r[0]: r[1] for r in db.execute(f'SELECT status,count(*) FROM ({source} WHERE {" AND ".join(conditions)}) GROUP BY status', values)}
        status = query.get('status', [''])[0]
        if status and 'status' in LIST_FILTERS[resource]:
            conditions.append('status=?'); values.append(status)
        where = ' WHERE ' + ' AND '.join(conditions)
        page, limit = self.pagination(query)
        total = db.execute(f'SELECT count(*) FROM ({source}{where})', values).fetchone()[0]
        order = 'name COLLATE NOCASE' if resource == 'categories' else 'id DESC'
        rows = db.execute(f'{source}{where} ORDER BY {order} LIMIT ? OFFSET ?', values + [limit, (page - 1) * limit]).fetchall()
        result = {'items':[dict(r) for r in rows],'total':total,'page':page,'limit':limit}
        if facets is not None:
            result['facets'] = facets
        return result

    def dashboard(self, db, user):
        # Key figures for the admin home page, limited to the admin's company when relevant.
        company = user['company_id'] if user['role'] == 'company_admin' else None
        ad_clause, ad_params = ('company_id=?', [company]) if company else ('1=1', [])
        app_clause, app_params = self.scope(user, 'applications')
        ads_by_status = dict.fromkeys(AD_STATUSES, 0)
        for status, count in db.execute(f'SELECT status,count(*) FROM ads WHERE {ad_clause} GROUP BY status', ad_params):
            ads_by_status[status] = count
        apps_by_status = dict.fromkeys(APPLICATION_STATUSES, 0)
        for status, count in db.execute(f'SELECT status,count(*) FROM applications WHERE {app_clause} GROUP BY status', app_params):
            apps_by_status[status] = count
        since = now_iso(-13 * 86400)[:10]
        per_day = {r[0]: r[1] for r in db.execute(
            f'SELECT substr(created_at,1,10) d,count(*) FROM applications WHERE {app_clause} AND substr(created_at,1,10)>=? GROUP BY d',
            app_params + [since])}
        timeline = [{'day': now_iso(-i * 86400)[:10], 'count': per_day.get(now_iso(-i * 86400)[:10], 0)} for i in range(13, -1, -1)]
        recent = db.execute(f'''SELECT x.id,x.applicant_name,x.status,x.created_at,a.id AS ad_id,a.title AS ad_title
            FROM applications x JOIN ads a ON a.id=x.ad_id WHERE x.id IN (SELECT id FROM applications WHERE {app_clause})
            ORDER BY x.created_at DESC, x.id DESC LIMIT 6''', app_params).fetchall()
        top = db.execute(f'''SELECT a.id,a.title,a.status,a.views,
            (SELECT count(*) FROM applications x WHERE x.ad_id=a.id) AS applications_count,
            (SELECT count(*) FROM applications x WHERE x.ad_id=a.id AND x.status='Reçue') AS new_applications
            FROM ads a WHERE {ad_clause} ORDER BY applications_count DESC, a.views DESC, a.id DESC LIMIT 5''', ad_params).fetchall()
        result = {
            'ads': ads_by_status,
            'applications': apps_by_status,
            'applications_total': sum(apps_by_status.values()),
            'applications_week': db.execute(f'SELECT count(*) FROM applications WHERE {app_clause} AND created_at>=?', app_params + [now_iso(-7 * 86400)]).fetchone()[0],
            'views': db.execute(f'SELECT coalesce(sum(views),0) FROM ads WHERE {ad_clause}', ad_params).fetchone()[0],
            'timeline': timeline,
            'recent_applications': [dict(r) for r in recent],
            'top_ads': [dict(r) for r in top],
        }
        if not company:
            result['people'] = {r[0]: r[1] for r in db.execute('SELECT role,count(*) FROM people GROUP BY role')}
            result['companies'] = db.execute('SELECT count(*) FROM companies').fetchone()[0]
        return result

    def export_applications(self, db, user, query):
        # CSV export (semicolon-separated, UTF-8 with BOM so spreadsheet software reads accents).
        clause, params = self.scope(user, 'applications')
        conditions, values = [f'x.id IN (SELECT id FROM applications WHERE {clause})'], list(params)
        for field in ('status', 'ad_id'):
            value = query.get(field, [''])[0]
            if value:
                conditions.append(f'x.{field}=?'); values.append(value)
        rows = db.execute(f'''SELECT x.id,x.created_at,a.title,c.name,x.applicant_name,x.applicant_email,x.applicant_phone,x.status,x.message
            FROM applications x JOIN ads a ON a.id=x.ad_id JOIN companies c ON c.id=a.company_id
            WHERE {" AND ".join(conditions)} ORDER BY x.created_at DESC, x.id DESC''', values).fetchall()
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=';')
        writer.writerow(['ID','Date','Offre','Entreprise','Nom','E-mail','Téléphone','Statut','Message'])
        for row in rows:
            writer.writerow([csv_safe(v) for v in row])
        return Raw('text/csv; charset=utf-8', ('﻿' + buffer.getvalue()).encode('utf-8'), 'candidatures.csv')

    def scope(self, user, resource):
        # SQL condition (without WHERE) limiting rows to what this admin may see.
        if user['role'] == 'admin':
            return '1=1', []
        company = user['company_id']
        clauses = {
            'companies': ('id=?', [company]),
            'ads': ('company_id=?', [company]),
            'applications': ('ad_id IN (SELECT id FROM ads WHERE company_id=?)', [company]),
            'people': ('id=? OR id IN (SELECT person_id FROM applications WHERE ad_id IN (SELECT id FROM ads WHERE company_id=?))', [user['id'], company]),
            'categories': ('1=1', []),
        }
        clause, params = clauses[resource]
        return clause, list(params)

    def authorize_values(self, db, user, resource, values, ident=None, existing=None):
        # Checks roles and company links before writing, in particular for company admins.
        if resource == 'people':
            previous = existing if existing is not None else (
                self.record(db, resource, ident) if ident else {'role': 'candidate', 'company_id': None}
            )
            merged = previous | values
            if merged['role'] not in ROLES:
                raise APIError(400, 'Rôle invalide.')
            if merged['role'] == 'company_admin':
                if not merged.get('company_id'):
                    raise APIError(400, 'Choisissez une entreprise pour cet administrateur.')
                self.record(db, 'companies', merged['company_id'])
            else:
                values['company_id'] = None
        if user['role'] != 'company_admin':
            return
        if resource == 'ads':
            if 'company_id' in values and values['company_id'] != user['company_id']:
                raise APIError(403, 'Vous pouvez gérer uniquement les offres de votre entreprise.')
            if 'contact_id' in values and values['contact_id'] != user['id']:
                raise APIError(403, 'Vous devez être le contact de cette offre.')
            values['company_id'] = user['company_id']
            values['contact_id'] = user['id']
            # Featuring an ad on the home page is an editorial choice of the project admin.
            values.pop('featured', None)
        # A company admin moves an application through the pipeline but cannot rewrite it.
        if resource == 'applications' and set(values) - {'status', 'notes'}:
            raise APIError(403, 'Seul le statut de la candidature peut être modifié.')

    def protect_admin(self,db,resource,ident,values,existing=None):
        # The last project administrator cannot be deleted or demoted.
        if resource == 'people' and 'role' in values and values['role'] != 'admin':
            person = existing if existing is not None else self.record(db,resource,ident)
            if person['role'] == 'admin' and db.execute("SELECT count(*) FROM people WHERE role='admin'").fetchone()[0] <= 1:
                raise APIError(400,'Le dernier administrateur doit être conservé.')

    def update(self,db,resource,ident,values):
        if not values:
            raise APIError(400,'Aucune modification fournie.')
        db.execute(f'UPDATE {resource} SET '+','.join(f'{key}=?' for key in values)+' WHERE id=?',list(values.values())+[ident])

    def pagination(self,query):
        # page >= 1 and between 1 and 100 rows per page (6 by default).
        try:
            page = max(1,int(query.get('page',['1'])[0]))
            limit = min(100,max(1,int(query.get('limit',['6'])[0])))
            return page,limit
        except ValueError:
            raise APIError(400,'Pagination invalide.')

    # ------------------------------------------------------------------ static files
    def site_url(self):
        # Absolute site address for robots.txt and sitemap.xml; an invalid Host header is ignored.
        host = self.headers.get('Host','')
        if not re.fullmatch(r'[A-Za-z0-9.\-]+(:\d+)?|\[[0-9A-Fa-f:]+\](:\d+)?',host):
            host = '127.0.0.1:%d' % self.server.server_address[1]
        scheme = 'https' if os.environ.get('COOKIE_SECURE') == '1' else 'http'
        return f'{scheme}://{host}'

    def crawler_file(self, path):
        site = self.site_url()
        if path == '/robots.txt':
            # /api/ads stays open: crawlers need it to display the jobs.
            disallowed = ('/api/admin/','/api/account','/api/applications','/api/auth/','/api/my-applications','/api/people','/api/saved')
            lines = ['User-agent: *','Allow: /'] + [f'Disallow: {route}' for route in disallowed] + ['',f'Sitemap: {site}/sitemap.xml','']
            return 'text/plain; charset=utf-8', '\n'.join(lines)
        if path == '/sitemap.xml':
            # Views such as #job/1 are URL fragments, which sitemaps do not support.
            return 'application/xml; charset=utf-8', ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                f'  <url><loc>{site}/</loc></url>\n'
                '</urlset>\n')
        return None

    STATIC_TYPES = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8',
                    '.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.webp':'image/webp','.ico':'image/x-icon',
                    '.json':'application/json; charset=utf-8','.woff2':'font/woff2'}

    def serve_static(self, path):
        generated = self.crawler_file(path)
        if generated:
            content = generated[1].encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type',generated[0])
            self.send_header('Content-Length',str(len(content)))
            self.security_headers(); self.end_headers(); self.wfile.write(content)
            return
        name = path.lstrip('/') or 'index.html'
        file = (PUBLIC / name).resolve()
        # Blocks paths that leave the public folder, such as ../server.py.
        if not file.is_relative_to(PUBLIC.resolve()) or not file.is_file():
            return self.send_json(404,{'error':'Page introuvable.'})
        content = file.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type',self.STATIC_TYPES.get(file.suffix,'application/octet-stream'))
        self.send_header('Content-Length',str(len(content)))
        # Always revalidate: assets change during development and are small.
        self.send_header('Cache-Control','no-cache')
        self.security_headers(); self.end_headers(); self.wfile.write(content)

    def handle_request(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith('/api/'):
            if self.command != 'GET':
                return self.send_json(405,{'error':'Méthode non autorisée.'})
            return self.serve_static(parsed.path)
        if self.command != 'GET':
            # When Origin is present, refuse writes coming from another site.
            origin = self.headers.get('Origin')
            host = self.headers.get('Host') or ''
            if origin and origin not in ('http://'+host, 'https://'+host):
                return self.send_json(403,{'error':'Origine non autorisée.'})
        db = connect()
        try:
            # Commit when the route succeeds; roll back when it raises.
            with db:
                status,data,cookie = self.route(db,parsed.path.rstrip('/'),parse_qs(parsed.query))
            if isinstance(data, Raw):
                self.send_raw(status, data)
            else:
                self.send_json(status,data,cookie)
        except APIError as error:
            self.send_json(error.status,{'error':error.message})
        except sqlite3.IntegrityError as error:
            # Turns SQL constraints (duplicates, relations, values) into readable messages.
            detail = str(error)
            if 'UNIQUE' in detail:
                message = 'Cet enregistrement existe déjà (e-mail, catégorie ou candidature en double).'
                status = 409
            elif 'FOREIGN KEY' in detail:
                message = 'Relation invalide ou enregistrement encore utilisé. Vérifiez les références avant de supprimer.'
                status = 409
            else:
                message,status = 'Valeurs invalides : vérifiez le contrat, le statut, le rôle et les salaires.',400
            self.send_json(status,{'error':message})
        except Exception:
            import traceback
            # Technical details stay in the logs; the browser gets a generic message.
            traceback.print_exc()
            self.send_json(500,{'error':'Erreur interne du serveur.'})
        finally:
            db.close()

    do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = handle_request


def make_server(host='127.0.0.1',port=8000):
    # Prepares the database and the threaded server without starting its loop.
    initialize()
    server = ThreadingHTTPServer((host,port),Handler)
    # In-memory counters shared by threads; they reset on restart.
    server.rate_hits = {}
    server.rate_lock = threading.Lock()
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='HireLoop — Job Board')
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--host',default='127.0.0.1')
    args = parser.parse_args()
    server = make_server(args.host,args.port)
    print(f'HireLoop disponible sur http://{args.host}:{args.port}',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
