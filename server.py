"""HireLoop : serveur HTTP et API REST, Python 3.10+, sans dépendance externe."""
import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from seed import seed

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('JOBBOARD_DB', str(ROOT / 'data' / 'hireloop.sqlite3')))
PUBLIC = ROOT / 'public'
RESOURCES = {
    'companies': ['name','industry','location','website','description','color'],
    'categories': ['name'],
    'people': ['name','email','phone','role','company_id'],
    'ads': ['company_id','category_id','contact_id','title','summary','description','requirements','location','contract','work_mode','salary_min','salary_max','working_time','featured'],
    'applications': ['ad_id','person_id','message','status'],
}
REQUIRED = {
    'companies': ['name','industry','location','description'], 'categories': ['name'],
    'people': ['name','email'],
    'ads': ['company_id','category_id','contact_id','title','summary','description','requirements','location','contract','work_mode','salary_min','salary_max'],
    'applications': ['ad_id','person_id','message'],
}
EMAIL = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
AD_SELECT = '''SELECT a.*, c.name AS company_name,c.color AS company_color,c.industry,
 c.description AS company_description,c.website AS company_website,k.name AS category_name
 FROM ads a JOIN companies c ON c.id=a.company_id JOIN categories k ON k.id=a.category_id'''
PERSON_COLUMNS = 'id,name,email,phone,role,company_id,created_at'

def hash_password(password):
    salt = secrets.token_hex(16)
    value = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000).hex()
    return f'{salt}${value}'

def verify_password(password, stored):
    if not stored or not isinstance(password,str):
        return False
    salt, value = stored.split('$')
    return hmac.compare_digest(hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000).hex(), value)

def connect():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

def initialize():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript((ROOT / 'schema.sql').read_text(encoding='utf-8'))
        migrate_people(db)
        seed(db)
        migrate_application_contacts(db)

def migrate_application_contacts(db):
    columns = {r['name'] for r in db.execute('PRAGMA table_info(applications)')}
    for field, person_field in (('applicant_name', 'name'), ('applicant_email', 'email'), ('applicant_phone', 'phone')):
        if field not in columns:
            db.execute(f"ALTER TABLE applications ADD COLUMN {field} TEXT NOT NULL DEFAULT ''")
            db.execute(f'UPDATE applications SET {field}=(SELECT {person_field} FROM people WHERE people.id=applications.person_id)')

def migrate_people(db):
    """Upgrade the legacy role constraint without changing IDs or related records."""
    if 'company_id' in {r['name'] for r in db.execute('PRAGMA table_info(people)')}:
        return
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
    def __init__(self, status, message):
        self.status, self.message = status, message

class Handler(BaseHTTPRequestHandler):
    server_version = 'HireLoop/1.0'

    def send_json(self, status, data, cookie=None):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        if cookie:
            self.send_header('Set-Cookie',cookie)
        self.security_headers()
        self.end_headers()
        self.wfile.write(body)

    def security_headers(self):
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','same-origin')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")

    def body(self):
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

    def current_user(self, db):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie',''))
            token = cookie['hireloop_session'].value
        except (KeyError, CookieError):
            return None
        return db.execute(f'SELECT {", ".join("p."+x for x in PERSON_COLUMNS.split(","))} FROM people p JOIN sessions s ON s.person_id=p.id WHERE s.token_hash=? AND s.expires_at>?',
            (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()

    def require_user(self, db, admin=False):
        user = self.current_user(db)
        if not user:
            raise APIError(401,'Connectez-vous pour accéder à cette page.')
        if admin and user['role'] not in ('admin', 'company_admin'):
            raise APIError(403,'Cet espace est réservé aux administrateurs.')
        return user

    def new_session(self, db, person):
        token = secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE expires_at<?',(int(time.time()),))
        db.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),person,int(time.time())+86400))
        secure = '; Secure' if os.environ.get('COOKIE_SECURE') == '1' else ''
        return f'hireloop_session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=86400{secure}'

    def validate(self, resource, data, partial=False):
        allowed = RESOURCES[resource] + (['password'] if resource == 'people' else [])
        unknown = set(data) - set(allowed)
        if unknown:
            raise APIError(400,'Champ inconnu : '+', '.join(sorted(unknown)))
        cleaned = {}
        for key,value in data.items():
            if resource == 'people' and key == 'company_id' and value in (None, ''):
                cleaned[key] = None
                continue
            if key in ('company_id','category_id','contact_id','ad_id','person_id','salary_min','salary_max','featured'):
                if isinstance(value,bool) or not str(value).isdigit():
                    raise APIError(400,f'{key} doit être un entier positif.')
                value = int(value)
            else:
                if not isinstance(value,str) or len(value) > 12000:
                    raise APIError(400,f'Valeur invalide pour {key}.')
                value = value if key == 'password' else value.strip()
            cleaned[key] = value
        for key in REQUIRED[resource]:
            if (not partial or key in cleaned) and (key not in cleaned or cleaned[key] == ''):
                raise APIError(400,f'Champ obligatoire : {key}.')
        if 'email' in cleaned:
            cleaned['email'] = cleaned['email'].lower()
            if not EMAIL.fullmatch(cleaned['email']):
                raise APIError(400,'Adresse e-mail invalide.')
        if 'password' in cleaned:
            if len(cleaned['password']) < 10:
                raise APIError(400,'Le mot de passe doit contenir au moins 10 caractères.')
            cleaned['password_hash'] = hash_password(cleaned.pop('password'))
        if 'website' in cleaned and cleaned['website'] and not re.match(r'^https?://[^\s]+$',cleaned['website']):
            raise APIError(400,'Le site doit commencer par https:// ou http://.')
        if 'color' in cleaned and not re.fullmatch(r'#[0-9a-fA-F]{6}',cleaned['color']):
            raise APIError(400,'Couleur invalide (exemple : #355d50).')
        return cleaned

    def record(self,db,resource,ident):
        columns = PERSON_COLUMNS if resource == 'people' else '*'
        row = db.execute(f'SELECT {columns} FROM {resource} WHERE id=?',(ident,)).fetchone()
        if not row:
            raise APIError(404,'Cet enregistrement n’existe pas.')
        return dict(row)

    def route(self,db,path,query):
        method = self.command
        admin_view = path.startswith('/api/admin/')
        if admin_view:
            self.require_user(db, True)
            path = path.replace('/api/admin/', '/api/', 1)
        if path == '/api/health' and method == 'GET':
            db.execute('SELECT 1')
            return 200, {'status':'ok'}, None
        if path == '/api/auth/me' and method == 'GET':
            user = self.current_user(db)
            return 200, {'user':dict(user) if user else None}, None
        if path in ('/api/auth/register','/api/auth/login') and method == 'POST':
            data = self.body()
            if path.endswith('register'):
                if set(data) - {'name','email','phone','password'}:
                    raise APIError(400,'Champs d’inscription invalides.')
                if not data.get('password'):
                    raise APIError(400,'Le mot de passe est obligatoire.')
                values = self.validate('people',data)
                existing = db.execute('SELECT id,password_hash FROM people WHERE email=?',(values['email'],)).fetchone()
                if existing:
                    raise APIError(409,'Cette adresse est déjà connue. Connectez-vous ou utilisez une autre adresse.')
                keys = list(values)
                ident = db.execute(f'INSERT INTO people({",".join(keys)}) VALUES({",".join("?" for _ in keys)})',list(values.values())).lastrowid
                cookie = self.new_session(db,ident)
                return 201, {'user':self.record(db,'people',ident)}, cookie
            email, password = data.get('email',''), data.get('password','')
            if not isinstance(email,str) or not isinstance(password,str):
                raise APIError(400,'Identifiants invalides.')
            # Limitation locale par IP ; aucune donnée de mot de passe conservée.
            now = time.time()
            ip = self.client_address[0]
            with self.server.login_lock:
                attempts = [t for t in self.server.login_attempts.get(ip,[]) if t > now-300]
                if len(attempts) >= 15:
                    raise APIError(429,'Trop de tentatives. Réessayez dans cinq minutes.')
                attempts.append(now)
                self.server.login_attempts[ip] = attempts
            user = db.execute('SELECT * FROM people WHERE email=?',(email.strip().lower(),)).fetchone()
            if not user or not verify_password(password,user['password_hash']):
                raise APIError(401,'Adresse e-mail ou mot de passe incorrect.')
            return 200, {'user':self.record(db,'people',user['id'])}, self.new_session(db,user['id'])
        if path == '/api/auth/logout' and method == 'POST':
            cookie = SimpleCookie(self.headers.get('Cookie',''))
            if 'hireloop_session' in cookie:
                db.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(cookie['hireloop_session'].value.encode()).hexdigest(),))
            return 200, {'message':'Vous êtes déconnecté.'}, 'hireloop_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'
        if path == '/api/account' and method == 'PATCH':
            user = self.require_user(db)
            data = self.body()
            if set(data) - {'name','email','phone','password','current_password'}:
                raise APIError(400,'Champs de profil invalides.')
            current_password = data.pop('current_password',None)
            values = self.validate('people',data,True)
            if 'password_hash' in values or ('email' in values and values['email'] != user['email'].lower()):
                stored = db.execute('SELECT password_hash FROM people WHERE id=?',(user['id'],)).fetchone()[0]
                if not verify_password(current_password,stored):
                    raise APIError(400,'Votre mot de passe actuel est requis pour ce changement.')
            self.update(db,'people',user['id'],values)
            return 200, {'user':self.record(db,'people',user['id'])}, None
        if path == '/api/my-applications' and method == 'GET':
            user = self.require_user(db)
            rows = db.execute('SELECT x.*,a.title,c.name AS company_name FROM applications x JOIN ads a ON a.id=x.ad_id JOIN companies c ON c.id=a.company_id WHERE person_id=? ORDER BY x.id DESC',(user['id'],)).fetchall()
            return 200, {'items':[dict(r) for r in rows]}, None
        if path == '/api/stats' and method == 'GET':
            if admin_view:
                user = self.require_user(db, True)
                counts = {}
                for table in ('ads','companies','applications','people'):
                    where, params = self.scope(user, table)
                    counts[table] = db.execute(f'SELECT count(*) FROM {table}' + where, params).fetchone()[0]
                return 200, counts, None
            return 200, {table:db.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in ('ads','companies','applications','people')}, None
        if path == '/api/meta' and method == 'GET':
            return 200, {'companies':[dict(r) for r in db.execute('SELECT id,name FROM companies ORDER BY name')], 'categories':[dict(r) for r in db.execute('SELECT * FROM categories ORDER BY name')], 'locations':[r[0] for r in db.execute('SELECT DISTINCT location FROM ads ORDER BY location')]}, None
        match = re.fullmatch(r'/api/companies/(\d+)/ads',path)
        if match and method == 'GET':
            self.record(db,'companies',int(match[1]))
            return 200, {'items':[dict(r) for r in db.execute(AD_SELECT+' WHERE a.company_id=? ORDER BY a.id DESC',(int(match[1]),))]}, None
        match = re.fullmatch(r'/api/ads/(\d+)/applications',path)
        if match and method == 'POST':
            ad_id = int(match[1])
            self.record(db,'ads',ad_id)
            data = self.body()
            user = self.current_user(db)
            message = data.get('message','')
            if not isinstance(message,str) or not 20 <= len(message.strip()) <= 12000:
                raise APIError(400,'Votre message doit contenir entre 20 et 12 000 caractères.')
            if user:
                person_id = user['id']
                values = self.validate('people', {k:data.get(k, user[k]) for k in ('name','email','phone')})
            else:
                values = self.validate('people',{k:data[k] for k in ('name','email','phone') if k in data})
                existing = db.execute('SELECT id,password_hash FROM people WHERE email=?',(values['email'],)).fetchone()
                if existing and existing['password_hash']:
                    raise APIError(409,'Un compte existe avec cet e-mail. Connectez-vous pour postuler.')
                if existing:
                    person_id = existing['id']
                else:
                    person_id = db.execute('INSERT INTO people(name,email,phone) VALUES(?,?,?)',(values['name'],values['email'],values.get('phone',''))).lastrowid
            ident = db.execute('INSERT INTO applications(ad_id,person_id,message,applicant_name,applicant_email,applicant_phone) VALUES(?,?,?,?,?,?)',
                (ad_id,person_id,message.strip(),values['name'],values['email'],values.get('phone',''))).lastrowid
            return 201, {'application':self.record(db,'applications',ident),'message':'Votre candidature a été enregistrée et est accessible au recruteur.'}, None
        match = re.fullmatch(r'/api/(ads|companies|categories|people|applications)(?:/(\d+))?',path)
        if not match:
            raise APIError(404,'Route introuvable.')
        resource, ident = match[1], int(match[2]) if match[2] else None
        if method == 'GET' and resource == 'ads' and ident and not admin_view:
            row = db.execute(AD_SELECT+' WHERE a.id=?',(ident,)).fetchone()
            if not row:
                raise APIError(404,'Cette offre n’existe pas.')
            return 200, dict(row), None
        if method == 'GET' and resource == 'ads' and not admin_view:
            conditions, params = [], []
            for field in ('category_id','company_id','location','contract','work_mode'):
                value = query.get(field,[''])[0]
                if value:
                    conditions.append(f'a.{field}=?'); params.append(value)
            term = query.get('q',[''])[0].strip()[:200]
            if term:
                conditions.append('(a.title LIKE ? OR a.summary LIKE ? OR c.name LIKE ?)')
                params += ['%'+term+'%']*3
            where = ' WHERE '+' AND '.join(conditions) if conditions else ''
            total = db.execute('SELECT count(*) FROM ads a JOIN companies c ON c.id=a.company_id'+where,params).fetchone()[0]
            page,limit = self.pagination(query)
            order = {'recent':'a.created_at DESC,a.id DESC','salary':'a.salary_max DESC,a.id DESC','relevant':'a.featured DESC,a.created_at DESC,a.id DESC'}.get(query.get('sort',['relevant'])[0],'a.id DESC')
            rows = db.execute(AD_SELECT+where+f' ORDER BY {order} LIMIT ? OFFSET ?',params+[limit,(page-1)*limit]).fetchall()
            return 200, {'items':[dict(r) for r in rows],'total':total,'page':page,'limit':limit}, None
        user = self.require_user(db,True)
        where, params = self.scope(user, resource)
        if ident:
            self.record(db, resource, ident)
            conjunction = ' AND ' if where else ' WHERE '
            if not db.execute(f'SELECT id FROM {resource}' + where + conjunction + 'id=?', params + [ident]).fetchone():
                raise APIError(403, 'Cet enregistrement appartient à une autre entreprise.')
        if user['role'] == 'company_admin' and method != 'GET':
            if resource in ('people', 'categories') or (resource == 'companies' and method not in ('PATCH', 'PUT')) or (resource == 'applications' and method not in ('PATCH', 'PUT')):
                raise APIError(403, 'Cette action est réservée à l’administrateur du projet.')
        if method == 'GET':
            if ident:
                return 200,self.record(db,resource,ident),None
            page,limit = self.pagination(query)
            columns = PERSON_COLUMNS if resource == 'people' else '*'
            total = db.execute(f'SELECT COUNT(*) FROM {resource}' + where, params).fetchone()[0]
            rows = db.execute(f'SELECT {columns} FROM {resource}' + where + ' ORDER BY id DESC LIMIT ? OFFSET ?',params + [limit,(page-1)*limit]).fetchall()
            return 200, {'items':[dict(r) for r in rows],'total':total,'page':page,'limit':limit},None
        if method == 'POST' and not ident:
            values = self.validate(resource,self.body())
            self.authorize_values(db, user, resource, values)
            keys = list(values)
            ident = db.execute(f'INSERT INTO {resource}({",".join(keys)}) VALUES({",".join("?" for _ in keys)})',list(values.values())).lastrowid
            return 201,self.record(db,resource,ident),None
        if method in ('PATCH','PUT') and ident:
            self.record(db,resource,ident)
            values = self.validate(resource,self.body(),method=='PATCH')
            self.authorize_values(db, user, resource, values, ident)
            self.protect_admin(db,resource,ident,values)
            if resource == 'ads':
                merged = self.record(db,resource,ident) | values
                if merged['salary_max'] < merged['salary_min']:
                    raise APIError(400,'Le salaire maximum doit être supérieur au minimum.')
            self.update(db,resource,ident,values)
            return 200,self.record(db,resource,ident),None
        if method == 'DELETE' and ident:
            self.record(db,resource,ident)
            self.protect_admin(db,resource,ident,{'role':'candidate'})
            current = self.current_user(db)
            if resource == 'people' and current['id'] == ident:
                raise APIError(400,'Vous ne pouvez pas supprimer votre propre compte administrateur.')
            db.execute(f'DELETE FROM {resource} WHERE id=?',(ident,))
            return 200,{'message':'Enregistrement supprimé.'},None
        raise APIError(405,'Méthode non autorisée.')

    def scope(self, user, resource):
        if user['role'] == 'admin':
            return '', []
        company = user['company_id']
        clauses = {
            'companies': ('id=?', [company]),
            'ads': ('company_id=?', [company]),
            'applications': ('ad_id IN (SELECT id FROM ads WHERE company_id=?)', [company]),
            'people': ('id=? OR id IN (SELECT person_id FROM applications WHERE ad_id IN (SELECT id FROM ads WHERE company_id=?))', [user['id'], company]),
            'categories': ('1=1', []),
        }
        clause, params = clauses[resource]
        return ' WHERE (' + clause + ')', params

    def authorize_values(self, db, user, resource, values, ident=None):
        if resource == 'people':
            previous = self.record(db, resource, ident) if ident else {'role': 'candidate', 'company_id': None}
            merged = previous | values
            if merged['role'] not in ('candidate', 'admin', 'company_admin'):
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
        if resource == 'applications' and set(values) - {'status'}:
            raise APIError(403, 'Seul le statut de la candidature peut être modifié.')

    def protect_admin(self,db,resource,ident,values):
        if resource == 'people' and 'role' in values and values['role'] != 'admin':
            person = self.record(db,resource,ident)
            if person['role'] == 'admin' and db.execute("SELECT count(*) FROM people WHERE role='admin'").fetchone()[0] <= 1:
                raise APIError(400,'Le dernier administrateur doit être conservé.')

    def update(self,db,resource,ident,values):
        if not values:
            raise APIError(400,'Aucune modification fournie.')
        db.execute(f'UPDATE {resource} SET '+','.join(f'{key}=?' for key in values)+' WHERE id=?',list(values.values())+[ident])

    def pagination(self,query):
        try:
            page = max(1,int(query.get('page',['1'])[0]))
            limit = min(100,max(1,int(query.get('limit',['6'])[0])))
            return page,limit
        except ValueError:
            raise APIError(400,'Pagination invalide.')

    def handle_request(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith('/api/'):
            if self.command != 'GET':
                return self.send_json(405,{'error':'Méthode non autorisée.'})
            name = parsed.path.lstrip('/') or 'index.html'
            file = (PUBLIC / name).resolve()
            if not file.is_relative_to(PUBLIC.resolve()) or not file.is_file():
                return self.send_json(404,{'error':'Page introuvable.'})
            content = file.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type',{'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.svg':'image/svg+xml'}.get(file.suffix,'application/octet-stream'))
            self.send_header('Content-Length',str(len(content)))
            self.security_headers(); self.end_headers(); self.wfile.write(content)
            return
        if self.command != 'GET':
            origin = self.headers.get('Origin')
            if origin and origin != 'http://'+self.headers.get('Host') and origin != 'https://'+self.headers.get('Host'):
                return self.send_json(403,{'error':'Origine non autorisée.'})
        db = connect()
        try:
            with db:
                status,data,cookie = self.route(db,parsed.path.rstrip('/'),parse_qs(parsed.query))
            self.send_json(status,data,cookie)
        except APIError as error:
            self.send_json(error.status,{'error':error.message})
        except sqlite3.IntegrityError as error:
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
            traceback.print_exc()
            self.send_json(500,{'error':'Erreur interne du serveur.'})
        finally:
            db.close()

    do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = handle_request

def make_server(host='127.0.0.1',port=8000):
    import threading
    initialize()
    server = ThreadingHTTPServer((host,port),Handler)
    server.login_attempts = {}
    server.login_lock = threading.Lock()
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
