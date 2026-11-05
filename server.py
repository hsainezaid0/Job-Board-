"""HireLoop : serveur HTTP et API REST, Python 3.10+, sans dépendance externe."""
# Biblioth?ques standard : arguments du terminal, s?curit?, JSON, SQLite et serveur HTTP.
import argparse
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import closing
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from seed import seed

# Chemins absolus : les fichiers restent accessibles m?me si le terminal est ouvert dans un autre dossier.
ROOT = Path(__file__).resolve().parent
# JOBBOARD_DB permet de placer la base sur un disque persistant chez l?h?bergeur.
DB_PATH = Path(os.environ.get('JOBBOARD_DB', str(ROOT / 'data' / 'hireloop.sqlite3')))
PUBLIC = ROOT / 'public'
# Liste blanche des tables et colonnes modifiables via l?API ; les noms SQL ne viennent pas librement du client.
RESOURCES = {
    'companies': ['name','industry','location','website','description','color'],
    'categories': ['name'],
    'people': ['name','email','phone','role','company_id'],
    'ads': ['company_id','category_id','contact_id','title','summary','description','requirements','location','contract','work_mode','salary_min','salary_max','working_time','featured'],
    'applications': ['ad_id','person_id','message','status'],
}
# Champs indispensables ? la cr?ation ; une modification partielle ne v?rifie que les champs transmis.
REQUIRED = {
    'companies': ['name','industry','location','description'], 'categories': ['name'],
    'people': ['name','email'],
    'ads': ['company_id','category_id','contact_id','title','summary','description','requirements','location','contract','work_mode','salary_min','salary_max'],
    'applications': ['ad_id','person_id','message'],
}
# Expression r?guli?re pour un contr?le simple du format des adresses e-mail.
EMAIL = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
# Limites anti-abus : (nombre maximal, durée de la fenêtre en secondes).
LOGIN_FAILURE_LIMIT = (15, 300)
SIGNUP_LIMIT = (10, 3600)
APPLICATION_ACCOUNT_LIMIT = (20, 3600)
APPLICATION_IP_LIMIT = (60, 3600)
# Jointures : enrichit chaque offre avec les informations de son entreprise et de sa cat?gorie.
AD_SELECT = '''SELECT a.*, c.name AS company_name,c.color AS company_color,c.industry,
 c.description AS company_description,c.website AS company_website,k.name AS category_name
 FROM ads a JOIN companies c ON c.id=a.company_id JOIN categories k ON k.id=a.category_id'''
# Colonnes publiques d?un utilisateur : exclut volontairement password_hash.
PERSON_COLUMNS = 'id,name,email,phone,role,company_id,created_at'

def hash_password(password):
    # Transforme un mot de passe en empreinte PBKDF2 avec un sel al?atoire ; renvoie ? sel$empreinte ?.
    # Le sel ?vite que deux mots de passe identiques produisent la m?me empreinte stock?e.
    salt = secrets.token_hex(16)
    # 260 000 it?rations rendent les essais de mots de passe plus co?teux ; encode() produit des octets.
    value = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000).hex()
    return f'{salt}${value}'

def verify_password(password, stored):
    # Recalcule l?empreinte du mot de passe fourni et la compare ? celle enregistr?e.
    if not stored or not isinstance(password,str):
        return False
    salt, value = stored.split('$')
    # Comparaison con?ue pour limiter les fuites li?es au temps de comparaison des empreintes.
    return hmac.compare_digest(hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000).hex(), value)

def connect():
    # Ouvre une connexion SQLite ; le code appelant doit la fermer apr?s utilisation.
    db = sqlite3.connect(DB_PATH, timeout=10)
    # Permet de lire une colonne par son nom, par exemple row["email"], et de convertir la ligne en dictionnaire.
    db.row_factory = sqlite3.Row
    # Active le contr?le des relations entre tables pour cette connexion.
    db.execute('PRAGMA foreign_keys=ON')
    return db

def initialize():
    # Cr?e ou met ? jour la base, puis initialise le compte de production ou les donn?es de d?monstration.
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Le contexte db valide ou annule la transaction ; closing ferme ensuite r?ellement la connexion.
    with closing(connect()) as db, db:
        # Le journal WAL facilite la coexistence des lectures et des ?critures SQLite.
        db.execute('PRAGMA journal_mode=WAL')
        # Charge les d?finitions des tables depuis schema.sql.
        db.executescript((ROOT / 'schema.sql').read_text(encoding='utf-8'))
        migrate_people(db)
        # En production, aucun compte de d?monstration : le premier administrateur vient des variables secr?tes.
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
        migrate_application_contacts(db)

def migrate_application_contacts(db):
    # Ajoute aux anciennes candidatures une copie du nom, de l?e-mail et du t?l?phone du candidat.
    # PRAGMA table_info d?crit les colonnes existantes : on ajoute seulement celles qui manquent.
    columns = {r['name'] for r in db.execute('PRAGMA table_info(applications)')}
    for field, person_field in (('applicant_name', 'name'), ('applicant_email', 'email'), ('applicant_phone', 'phone')):
        if field not in columns:
            db.execute(f"ALTER TABLE applications ADD COLUMN {field} TEXT NOT NULL DEFAULT ''")
            db.execute(f'UPDATE applications SET {field}=(SELECT {person_field} FROM people WHERE people.id=applications.person_id)')

def migrate_people(db):
    # Reconstruit une ancienne table people pour ajouter les r?les et le rattachement ? une entreprise.
    """Upgrade the legacy role constraint without changing IDs or related records."""
    if 'company_id' in {r['name'] for r in db.execute('PRAGMA table_info(people)')}:
        return
    # Termine la transaction avant de d?sactiver temporairement les contraintes de cl?s ?trang?res.
    db.commit()
    # N?cessaire pendant le remplacement de la table ; les relations seront v?rifi?es puis r?activ?es.
    db.execute('PRAGMA foreign_keys=OFF')
    try:
        # Regroupe la reconstruction de la table dans une transaction pour pouvoir annuler en cas d??chec.
        db.execute('BEGIN')
        # R?cup?re la d?finition de people dans le sch?ma actuel pour cr?er une table de remplacement.
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
        # Annule la migration si une ?tape ?choue, puis propage l?erreur.
        db.rollback()
        raise
    finally:
        db.execute('PRAGMA foreign_keys=ON')

# Erreur m?tier contr?l?e : distingue les erreurs attendues des pannes internes du serveur.
class APIError(Exception):
    def __init__(self, status, message):
        # M?morise le code HTTP et le message qui seront renvoy?s au navigateur.
        self.status, self.message = status, message

# Une instance de ce gestionnaire traite les requ?tes HTTP re?ues par le serveur.
class Handler(BaseHTTPRequestHandler):
    server_version = 'HireLoop/1.0'

    def send_json(self, status, data, cookie=None):
        # Envoie une r?ponse HTTP contenant du JSON et, si n?cessaire, un cookie de session.
        # S?rialise les donn?es Python et encode le texte en UTF-8 en conservant les accents.
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        # ?vite la mise en cache des r?ponses API, qui peuvent contenir des donn?es personnelles.
        self.send_header('Cache-Control','no-store')
        if cookie:
            self.send_header('Set-Cookie',cookie)
        self.security_headers()
        self.end_headers()
        self.wfile.write(body)

    def security_headers(self):
        # Ajoute les r?gles de s?curit? que le navigateur doit appliquer ? la r?ponse.
        # Interdit au navigateur de deviner un type de fichier diff?rent de celui annonc?.
        self.send_header('X-Content-Type-Options','nosniff')
        # Interdit l?int?gration de la page dans un cadre provenant d?un autre site ou du m?me site.
        self.send_header('X-Frame-Options','DENY')
        # Ne transmet l?adresse de la page d?origine que vers la m?me origine.
        self.send_header('Referrer-Policy','same-origin')
        # Restreint scripts, connexions et ressources ? ce site, avec les exceptions explicites indiqu?es.
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")

    def body(self):
        # Lit le corps JSON de la requ?te et exige un objet, avec une taille maximale de 64 Kio.
        try:
            # Lit la taille annonc?e avant de lire le flux entrant pour limiter la quantit? de donn?es accept?es.
            length = int(self.headers.get('Content-Length','0'))
            if length < 0:
                raise APIError(400,'Longueur de requête invalide.')
            if length > 65536:
                raise APIError(413,'Le formulaire est trop volumineux.')
            if 'application/json' not in self.headers.get('Content-Type',''):
                raise APIError(415,'Utilisez Content-Type: application/json.')
            # Transforme le JSON re?u en objet Python ; les tableaux et les valeurs isol?es sont refus?s ensuite.
            data = json.loads(self.rfile.read(length))
            if not isinstance(data,dict):
                raise ValueError()
            return data
        except (ValueError, json.JSONDecodeError):
            raise APIError(400,'Corps JSON invalide.')

    def client_ip(self):
        # Adresse du visiteur, utilisée pour les limites anti-abus et les journaux.
        # TRUST_PROXY=1 uniquement derrière un proxy : sinon cet en-tête serait falsifiable.
        headers = getattr(self, 'headers', None)
        if os.environ.get('TRUST_PROXY') == '1' and headers:
            # Le proxy ajoute la vraie adresse à droite : les valeurs falsifiées restent à gauche,
            # et les sauts internes du proxy sont des adresses privées à ignorer.
            for part in reversed(','.join(headers.get_all('X-Forwarded-For') or []).split(',')):
                try:
                    address = ipaddress.ip_address(part.strip())
                except ValueError:
                    continue
                if not address.is_private:
                    return str(address)
        return self.client_address[0]

    def address_string(self):
        # Les journaux affichent le visiteur plutôt que le proxy.
        return self.client_ip()

    def rate_check(self, bucket, key, limit, message, record=True):
        # Refuse la requête si la limite est atteinte ; record=True compte aussi cette tentative.
        maximum, window = limit
        now = time.time()
        with self.server.rate_lock:
            hits = self.server.rate_hits
            # Empêche le compteur en mémoire de grandir sans fin.
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
        # Compte une tentative après coup, par exemple un mot de passe incorrect.
        with self.server.rate_lock:
            self.server.rate_hits.setdefault((bucket, key), []).append(time.time())

    def session_token_hash(self):
        # Empreinte du jeton de session présent dans le cookie, ou None s'il est absent.
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie',''))
            return hashlib.sha256(cookie['hireloop_session'].value.encode()).hexdigest()
        except (KeyError, CookieError):
            return None

    def revoke_sessions(self, db, person):
        # Ferme les sessions d'un compte, sauf celle qui effectue la requête si elle lui appartient.
        db.execute('DELETE FROM sessions WHERE person_id=? AND token_hash IS NOT ?',(person,self.session_token_hash()))

    def current_user(self, db):
        # Retrouve l'utilisateur lié au cookie de session ; renvoie None si la session est absente ou expirée.
        token_hash = self.session_token_hash()
        if not token_hash:
            return None
        # La base conserve seulement l'empreinte du jeton ; la date doit être supérieure à l'heure actuelle.
        return db.execute(f'SELECT {", ".join("p."+x for x in PERSON_COLUMNS.split(","))} FROM people p JOIN sessions s ON s.person_id=p.id WHERE s.token_hash=? AND s.expires_at>?',
            (token_hash, int(time.time()))).fetchone()

    def require_user(self, db, admin=False):
        # Exige une connexion et, si admin=True, un r?le d?administrateur ; renvoie l?utilisateur autoris?.
        user = self.current_user(db)
        if not user:
            raise APIError(401,'Connectez-vous pour accéder à cette page.')
        if admin and user['role'] not in ('admin', 'company_admin'):
            raise APIError(403,'Cet espace est réservé aux administrateurs.')
        return user

    def new_session(self, db, person):
        # Cr?e une session valable 24 heures et renvoie le cookie ? transmettre au navigateur.
        # Jeton al?atoire impr?visible : sa valeur brute reste dans le cookie, son empreinte dans la base.
        token = secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE expires_at<?',(int(time.time()),))
        db.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),person,int(time.time())+86400))
        # Secure impose HTTPS ; HttpOnly interdit la lecture du cookie par JavaScript et SameSite limite son envoi entre sites.
        secure = '; Secure' if os.environ.get('COOKIE_SECURE') == '1' else ''
        return f'hireloop_session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=86400{secure}'

    def validate(self, resource, data, partial=False):
        # V?rifie les champs autoris?s, les types et les formats ; renvoie les valeurs nettoy?es pour SQLite.
        allowed = RESOURCES[resource] + (['password'] if resource == 'people' else [])
        # Refuse tout champ non pr?vu, plut?t que de l?ins?rer directement dans une requ?te SQL.
        unknown = set(data) - set(allowed)
        if unknown:
            raise APIError(400,'Champ inconnu : '+', '.join(sorted(unknown)))
        cleaned = {}
        for key,value in data.items():
            if resource == 'people' and key == 'company_id' and value in (None, ''):
                cleaned[key] = None
                continue
            # Convertit les identifiants et montants en entiers ; refuse les bool?ens m?me si Python les assimile ? des entiers.
            if key in ('company_id','category_id','contact_id','ad_id','person_id','salary_min','salary_max','featured'):
                if isinstance(value,bool) or not str(value).isdigit():
                    raise APIError(400,f'{key} doit être un entier positif.')
                value = int(value)
            else:
                if not isinstance(value,str) or len(value) > 12000:
                    raise APIError(400,f'Valeur invalide pour {key}.')
                # Supprime les espaces superflus du texte, mais pr?serve exactement les caract?res du mot de passe.
                value = value if key == 'password' else value.strip()
            cleaned[key] = value
        # partial=True correspond ? PATCH : seuls les champs pr?sents sont obligatoires et contr?l?s ici.
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
            # Retire le mot de passe en clair du dictionnaire et le remplace par son empreinte.
            cleaned['password_hash'] = hash_password(cleaned.pop('password'))
        if 'website' in cleaned and cleaned['website'] and not re.match(r'^https?://[^\s]+$',cleaned['website']):
            raise APIError(400,'Le site doit commencer par https:// ou http://.')
        if 'color' in cleaned and not re.fullmatch(r'#[0-9a-fA-F]{6}',cleaned['color']):
            raise APIError(400,'Couleur invalide (exemple : #355d50).')
        return cleaned

    def record(self,db,resource,ident):
        # Lit une ligne par son identifiant, sans exposer le mot de passe ; signale une erreur 404 si elle manque.
        columns = PERSON_COLUMNS if resource == 'people' else '*'
        row = db.execute(f'SELECT {columns} FROM {resource} WHERE id=?',(ident,)).fetchone()
        if not row:
            raise APIError(404,'Cet enregistrement n’existe pas.')
        return dict(row)

    def route(self,db,path,query):
        # Choisit le traitement selon l?URL et la m?thode HTTP ; renvoie (code HTTP, donn?es, cookie ?ventuel).
        method = self.command
        # Les routes /api/admin/ imposent un r?le administrateur avant de r?utiliser les traitements communs.
        admin_view = path.startswith('/api/admin/')
        admin_user = self.require_user(db, True) if admin_view else None
        if admin_view:
            path = path.replace('/api/admin/', '/api/', 1)
        # Sonde de sant? : v?rifie que SQLite r?pond.
        if path == '/api/health' and method == 'GET':
            db.execute('SELECT 1')
            return 200, {'status':'ok'}, None
        # Permet au frontend de conna?tre l?utilisateur connect? au chargement de la page.
        if path == '/api/auth/me' and method == 'GET':
            user = self.current_user(db)
            return 200, {'user':dict(user) if user else None}, None
        if path in ('/api/auth/register','/api/auth/login') and method == 'POST':
            data = self.body()
            # Inscription : les champs autoris?s excluent role pour emp?cher une ?l?vation de privil?ges.
            if path.endswith('register'):
                if set(data) - {'name','email','phone','password'}:
                    raise APIError(400,'Champs d’inscription invalides.')
                self.rate_check('signup',self.client_ip(),SIGNUP_LIMIT,'Trop d’inscriptions depuis cette adresse. Réessayez plus tard.')
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
            # Seuls les échecs comptent : un visiteur ne peut pas bloquer la connexion des autres.
            ip = self.client_ip()
            self.rate_check('login',ip,LOGIN_FAILURE_LIMIT,'Trop de tentatives. Réessayez dans cinq minutes.',record=False)
            user = db.execute('SELECT * FROM people WHERE email=?',(email.strip().lower(),)).fetchone()
            if not user or not verify_password(password,user['password_hash']):
                self.rate_record('login',ip)
                raise APIError(401,'Adresse e-mail ou mot de passe incorrect.')
            return 200, {'user':self.record(db,'people',user['id'])}, self.new_session(db,user['id'])
        # D?connexion : supprime la session c?t? base et fait expirer le cookie c?t? navigateur.
        if path == '/api/auth/logout' and method == 'POST':
            db.execute('DELETE FROM sessions WHERE token_hash=?',(self.session_token_hash(),))
            return 200, {'message':'Vous êtes déconnecté.'}, 'hireloop_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'
        # Modification du profil personnel ; changer l?e-mail ou le mot de passe exige le mot de passe actuel.
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
            if 'password_hash' in values:
                self.revoke_sessions(db,user['id'])
            return 200, {'user':self.record(db,'people',user['id'])}, None
        # Liste uniquement les candidatures de l?utilisateur connect?, avec le titre et l?entreprise.
        if path == '/api/my-applications' and method == 'GET':
            user = self.require_user(db)
            rows = db.execute('SELECT x.*,a.title,c.name AS company_name FROM applications x JOIN ads a ON a.id=x.ad_id JOIN companies c ON c.id=a.company_id WHERE person_id=? ORDER BY x.id DESC',(user['id'],)).fetchall()
            return 200, {'items':[dict(r) for r in rows]}, None
        # Compte les enregistrements ; la vue administrateur d?entreprise est limit?e par scope().
        if path == '/api/stats' and method == 'GET':
            if admin_view:
                user = admin_user
                counts = {}
                for table in ('ads','companies','applications','people'):
                    where, params = self.scope(user, table)
                    counts[table] = db.execute(f'SELECT count(*) FROM {table}' + where, params).fetchone()[0]
                return 200, counts, None
            return 200, {table:db.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in ('ads','companies','applications','people')}, None
        # Fournit les entreprises, cat?gories et villes pour remplir les filtres de l?interface.
        if path == '/api/meta' and method == 'GET':
            return 200, {'companies':[dict(r) for r in db.execute('SELECT id,name FROM companies ORDER BY name')], 'categories':[dict(r) for r in db.execute('SELECT * FROM categories ORDER BY name')], 'locations':[r[0] for r in db.execute('SELECT DISTINCT location FROM ads ORDER BY location')]}, None
        # Reconna?t une URL contenant l?identifiant d?une entreprise pour afficher ses offres.
        match = re.fullmatch(r'/api/companies/(\d+)/ads',path)
        if match and method == 'GET':
            self.record(db,'companies',int(match[1]))
            return 200, {'items':[dict(r) for r in db.execute(AD_SELECT+' WHERE a.company_id=? ORDER BY a.id DESC',(int(match[1]),))]}, None
        # Soumission d'une candidature : réservée aux comptes, avec les coordonnées du profil.
        match = re.fullmatch(r'/api/ads/(\d+)/applications',path)
        if match and method == 'POST':
            user = self.current_user(db)
            if not user:
                raise APIError(401,'Connectez-vous pour postuler.')
            ad_id = int(match[1])
            self.record(db,'ads',ad_id)
            data = self.body()
            unknown = set(data) - {'message'}
            if unknown:
                raise APIError(400,'Champ inconnu : '+', '.join(sorted(unknown)))
            message = data.get('message','')
            if not isinstance(message,str) or not 20 <= len(message.strip()) <= 12000:
                raise APIError(400,'Votre message doit contenir entre 20 et 12 000 caractères.')
            limit_message = 'Trop de candidatures envoyées. Réessayez plus tard.'
            self.rate_check('apply-account',user['id'],APPLICATION_ACCOUNT_LIMIT,limit_message)
            self.rate_check('apply-ip',self.client_ip(),APPLICATION_IP_LIMIT,limit_message)
            # Fige les coordonnées du compte dans la candidature, indépendamment des futures modifications du profil.
            ident = db.execute('INSERT INTO applications(ad_id,person_id,message,applicant_name,applicant_email,applicant_phone) VALUES(?,?,?,?,?,?)',
                (ad_id,user['id'],message.strip(),user['name'],user['email'],user['phone'])).lastrowid
            return 201, {'application':self.record(db,'applications',ident),'message':'Votre candidature a été enregistrée et est accessible au recruteur.'}, None
        # Routes g?n?riques : la ressource est limit?e ? cinq tables et l?identifiant facultatif est num?rique.
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
            return 200, self.list_ads(db, query), None
        # Au-del? des routes publiques, toutes les op?rations g?n?riques exigent un administrateur.
        user = admin_user if admin_user is not None else self.require_user(db, True)
        where, params = self.scope(user, resource)
        # V?rifie aussi que l?enregistrement demand? appartient au p?rim?tre autoris?.
        if ident:
            existing = self.record(db, resource, ident)
            conjunction = ' AND ' if where else ' WHERE '
            if not db.execute(f'SELECT id FROM {resource}' + where + conjunction + 'id=?', params + [ident]).fetchone():
                raise APIError(403, 'Cet enregistrement appartient à une autre entreprise.')
        if user['role'] == 'company_admin' and method != 'GET':
            if resource in ('people', 'categories') or (resource == 'companies' and method not in ('PATCH', 'PUT')) or (resource == 'applications' and method not in ('PATCH', 'PUT')):
                raise APIError(403, 'Cette action est réservée à l’administrateur du projet.')
        if method == 'GET':
            if ident:
                return 200,existing,None
            page,limit = self.pagination(query)
            columns = PERSON_COLUMNS if resource == 'people' else '*'
            total = db.execute(f'SELECT COUNT(*) FROM {resource}' + where, params).fetchone()[0]
            rows = db.execute(f'SELECT {columns} FROM {resource}' + where + ' ORDER BY id DESC LIMIT ? OFFSET ?',params + [limit,(page-1)*limit]).fetchall()
            return 200, {'items':[dict(r) for r in rows],'total':total,'page':page,'limit':limit},None
        # Cr?ation : valide les donn?es et les droits, ins?re la ligne puis renvoie un statut 201.
        if method == 'POST' and not ident:
            values = self.validate(resource,self.body())
            self.authorize_values(db, user, resource, values)
            keys = list(values)
            ident = db.execute(f'INSERT INTO {resource}({",".join(keys)}) VALUES({",".join("?" for _ in keys)})',list(values.values())).lastrowid
            return 201,self.record(db,resource,ident),None
        # Modification : PATCH est partiel, PUT exige les champs obligatoires ; prot?ge ?galement le dernier admin.
        if method in ('PATCH','PUT') and ident:
            values = self.validate(resource,self.body(),method=='PATCH')
            self.authorize_values(db, user, resource, values, ident, existing)
            self.protect_admin(db,resource,ident,values,existing)
            if resource == 'ads':
                merged = existing | values
                if merged['salary_max'] < merged['salary_min']:
                    raise APIError(400,'Le salaire maximum doit être supérieur au minimum.')
            self.update(db,resource,ident,values)
            if resource == 'people' and 'password_hash' in values:
                self.revoke_sessions(db,ident)
            return 200,self.record(db,resource,ident),None
        # Suppression : interdit de supprimer son propre compte administrateur et le dernier administrateur g?n?ral.
        if method == 'DELETE' and ident:
            self.protect_admin(db,resource,ident,{'role':'candidate'},existing)
            if resource == 'people' and user['id'] == ident:
                raise APIError(400,'Vous ne pouvez pas supprimer votre propre compte administrateur.')
            db.execute(f'DELETE FROM {resource} WHERE id=?',(ident,))
            return 200,{'message':'Enregistrement supprimé.'},None
        raise APIError(405,'Méthode non autorisée.')

    def list_ads(self, db, query):
        """Fetch a page of public offers with the same filters used for its count."""
        # Construit s?par?ment les conditions SQL et leurs valeurs pour une recherche param?tr?e.
        conditions, params = [], []
        for field in ('category_id','company_id','location','contract','work_mode'):
            value = query.get(field,[''])[0]
            if value:
                conditions.append(f'a.{field}=?'); params.append(value)
        # Recherche textuelle limit?e ? 200 caract?res dans le titre, le r?sum? et le nom de l?entreprise.
        term = query.get('q',[''])[0].strip()[:200]
        if term:
            conditions.append('(a.title LIKE ? OR a.summary LIKE ? OR c.name LIKE ?)')
            params += ['%'+term+'%']*3
        where = ' WHERE '+' AND '.join(conditions) if conditions else ''
        total = db.execute('SELECT count(*) FROM ads a JOIN companies c ON c.id=a.company_id'+where,params).fetchone()[0]
        page,limit = self.pagination(query)
        # Choisit le tri dans une liste fixe : aucun fragment SQL de tri fourni par le client n?est ex?cut?.
        order = {'recent':'a.created_at DESC,a.id DESC','salary':'a.salary_max DESC,a.id DESC','relevant':'a.featured DESC,a.created_at DESC,a.id DESC'}.get(query.get('sort',['relevant'])[0],'a.id DESC')
        rows = db.execute(AD_SELECT+where+f' ORDER BY {order} LIMIT ? OFFSET ?',params+[limit,(page-1)*limit]).fetchall()
        return {'items':[dict(r) for r in rows],'total':total,'page':page,'limit':limit}

    def scope(self, user, resource):
        # Construit la condition SQL limitant les donn?es visibles au p?rim?tre de l?administrateur.
        if user['role'] == 'admin':
            return '', []
        company = user['company_id']
        # Chaque table poss?de sa r?gle : une entreprise voit ses offres et les candidats qui y ont postul?.
        clauses = {
            'companies': ('id=?', [company]),
            'ads': ('company_id=?', [company]),
            'applications': ('ad_id IN (SELECT id FROM ads WHERE company_id=?)', [company]),
            'people': ('id=? OR id IN (SELECT person_id FROM applications WHERE ad_id IN (SELECT id FROM ads WHERE company_id=?))', [user['id'], company]),
            'categories': ('1=1', []),
        }
        clause, params = clauses[resource]
        return ' WHERE (' + clause + ')', params

    def authorize_values(self, db, user, resource, values, ident=None, existing=None):
        # V?rifie les r?les et les rattachements avant ?criture, notamment pour un administrateur d?entreprise.
        if resource == 'people':
            previous = existing if existing is not None else (
                self.record(db, resource, ident) if ident else {'role': 'candidate', 'company_id': None}
            )
            # Fusionne les valeurs existantes et propos?es afin de v?rifier l??tat final du compte.
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
        # Un administrateur d?entreprise peut changer le statut, mais pas r??crire la candidature.
        if resource == 'applications' and set(values) - {'status'}:
            raise APIError(403, 'Seul le statut de la candidature peut être modifié.')

    def protect_admin(self,db,resource,ident,values,existing=None):
        # Emp?che de supprimer ou de r?trograder le dernier administrateur g?n?ral du projet.
        if resource == 'people' and 'role' in values and values['role'] != 'admin':
            person = existing if existing is not None else self.record(db,resource,ident)
            if person['role'] == 'admin' and db.execute("SELECT count(*) FROM people WHERE role='admin'").fetchone()[0] <= 1:
                raise APIError(400,'Le dernier administrateur doit être conservé.')

    def update(self,db,resource,ident,values):
        # Met ? jour uniquement les colonnes fournies ; les valeurs passent par des param?tres SQL.
        if not values:
            raise APIError(400,'Aucune modification fournie.')
        db.execute(f'UPDATE {resource} SET '+','.join(f'{key}=?' for key in values)+' WHERE id=?',list(values.values())+[ident])

    def pagination(self,query):
        # Lit page et limit dans l?URL : page >= 1 et entre 1 et 100 r?sultats par page (6 par d?faut).
        try:
            page = max(1,int(query.get('page',['1'])[0]))
            limit = min(100,max(1,int(query.get('limit',['6'])[0])))
            return page,limit
        except ValueError:
            raise APIError(400,'Pagination invalide.')

    def handle_request(self):
        # Point d?entr?e HTTP : sert un fichier public ou ex?cute une route API avec gestion des erreurs.
        # S?pare le chemin de l?URL et les param?tres de recherche plac?s apr?s le point d?interrogation.
        parsed = urlparse(self.path)
        # Les URL hors API servent les fichiers HTML, CSS, JavaScript et les images du dossier public.
        if not parsed.path.startswith('/api/'):
            if self.command != 'GET':
                return self.send_json(405,{'error':'Méthode non autorisée.'})
            name = parsed.path.lstrip('/') or 'index.html'
            # R?sout les segments du chemin avant de v?rifier que le fichier reste dans public.
            file = (PUBLIC / name).resolve()
            # Bloque les chemins sortant de public, par exemple une tentative de lecture de ../server.py.
            if not file.is_relative_to(PUBLIC.resolve()) or not file.is_file():
                return self.send_json(404,{'error':'Page introuvable.'})
            content = file.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type',{'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.svg':'image/svg+xml'}.get(file.suffix,'application/octet-stream'))
            self.send_header('Content-Length',str(len(content)))
            self.security_headers(); self.end_headers(); self.wfile.write(content)
            return
        if self.command != 'GET':
            # Si Origin est pr?sent, refuse les ?critures provenant d?une origine diff?rente de celle du serveur.
            origin = self.headers.get('Origin')
            if origin and origin != 'http://'+self.headers.get('Host') and origin != 'https://'+self.headers.get('Host'):
                return self.send_json(403,{'error':'Origine non autorisée.'})
        db = connect()
        try:
            # Valide les ?critures si la route r?ussit ; annule la transaction si elle l?ve une exception.
            with db:
                status,data,cookie = self.route(db,parsed.path.rstrip('/'),parse_qs(parsed.query))
            self.send_json(status,data,cookie)
        # Convertit une erreur attendue en r?ponse JSON avec son code HTTP et son message explicite.
        except APIError as error:
            self.send_json(error.status,{'error':error.message})
        # Traduit les contraintes SQL (doublons, relations, valeurs) en messages compr?hensibles.
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
            # Garde les d?tails techniques dans les logs ; le navigateur re?oit seulement un message g?n?rique.
            traceback.print_exc()
            self.send_json(500,{'error':'Erreur interne du serveur.'})
        finally:
            # Ferme la connexion propre ? cette requ?te, m?me si une erreur est survenue.
            db.close()

    # Associe les cinq m?thodes HTTP prises en charge au m?me point d?entr?e.
    do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = handle_request

def make_server(host='127.0.0.1',port=8000):
    # Initialise la base et pr?pare le serveur multithread, sans encore d?marrer sa boucle d??coute.
    import threading
    initialize()
    # Chaque connexion peut ?tre trait?e dans un thread pour ne pas bloquer tous les visiteurs.
    server = ThreadingHTTPServer((host,port),Handler)
    # Compteurs en m?moire : ils sont partag?s entre threads, mais disparaissent au red?marrage.
    server.rate_hits = {}
    server.rate_lock = threading.Lock()
    return server

# Ce bloc d?marre seulement si le fichier est ex?cut? directement, pas lorsqu?il est import? par les tests.
if __name__ == '__main__':
    # Lit les options --host et --port du terminal ; par d?faut, ?coute uniquement sur la machine locale.
    parser = argparse.ArgumentParser(description='HireLoop — Job Board')
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--host',default='127.0.0.1')
    args = parser.parse_args()
    server = make_server(args.host,args.port)
    print(f'HireLoop disponible sur http://{args.host}:{args.port}',flush=True)
    try:
        # Attend les requ?tes jusqu?? l?arr?t du programme, par exemple avec Ctrl+C.
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # Lib?re le socket d??coute ? la fermeture du serveur.
        server.server_close()
