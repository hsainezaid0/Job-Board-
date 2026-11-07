"""Tests d’intégration HTTP sur une base temporaire isolée."""
import http.cookiejar
import json
import sys
import tempfile
import threading
import unittest
import unittest.mock
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server

class APITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        server.DB_PATH = Path(cls.temp.name) / 'test.sqlite3'
        cls.server = server.make_server(port=0)
        cls.base = f'http://127.0.0.1:{cls.server.server_port}/api'
        cls.thread = threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()
        cls.temp.cleanup()

    def setUp(self):
        self.server.rate_hits.clear()
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self,path,method='GET',data=None,expected=200,headers=None):
        req = urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers=headers or ({'Content-Type':'application/json'} if data is not None else {}))
        try:
            response=self.client.open(req)
        except urllib.error.HTTPError as error:
            response=error
        self.assertEqual(response.status,expected,response.read().decode() if response.status!=expected else '')
        return json.loads(response.read())

    def admin(self):
        return self.request('/auth/login','POST',{'email':'admin@hireloop.test','password':'Admin2026!'})

    def test_01_public_search_filters_and_pagination(self):
        data=self.request('/ads')
        self.assertEqual(data['total'],12); self.assertEqual(len(data['items']),6)
        self.assertTrue(all(a['contract']=='Stage' for a in self.request('/ads?contract=Stage')['items']))
        self.assertTrue(all(a['location']=='Paris' for a in self.request('/ads?location=Paris')['items']))
        self.assertEqual(self.request('/ads?q=React')['total'],1)
        self.assertEqual(self.request('/ads?q=unmotinexistant')['total'],0)
        self.assertNotEqual(data['items'][0]['id'],self.request('/ads?page=2')['items'][0]['id'])
        self.request('/ads?page=abc',expected=400)
        salary=self.request('/ads?sort=salary')['items']
        self.assertEqual([a['salary_max'] for a in salary],sorted([a['salary_max'] for a in salary],reverse=True))
        self.request('/ads/999999',expected=404)
        self.assertEqual(self.request('/ads/1')['company_name'],'Studio North')
        self.assertGreater(len(self.request('/companies/1/ads')['items']),0)
        self.request('/companies/999999/ads',expected=404)

    def test_02_anonymous_permissions(self):
        for resource in server.RESOURCES:
            self.request('/'+resource,'POST',{},expected=401)
            self.request('/'+resource+'/1','PATCH',{},expected=401)
            self.request('/'+resource+'/1','DELETE',expected=401)
        self.request('/people',expected=401)
        self.request('/applications',expected=401)
        self.request('/my-applications',expected=401)
        self.assertIsNone(self.request('/auth/me')['user'])

    def test_03_register_profile_apply_and_logout(self):
        data=self.request('/auth/register','POST',{'name':'Test Candidate','email':'new@example.test','phone':'0601020304','password':'Password2026!'},201)
        self.assertEqual(data['user']['role'],'candidate')
        self.assertNotIn('password_hash',data['user'])
        self.assertEqual(self.request('/auth/me')['user']['name'],'Test Candidate')
        self.request('/people',expected=403)
        self.request('/ads','POST',{},expected=403)
        self.request('/account','PATCH',{'role':'admin'},400)
        self.request('/account','PATCH',{'email':123},400)
        self.request('/account','PATCH',{'email':'changed@example.test','current_password':{}},400)
        self.request('/account','PATCH',{'email':'changed@example.test'},400)
        self.request('/account','PATCH',{'name':'Updated Candidate','phone':'0611223344'})
        application = self.request('/ads/2/applications','POST',{'message':'Je suis intéressé par cette offre et souhaite rencontrer votre équipe.'},201)['application']
        self.assertEqual(application['applicant_name'], 'Updated Candidate')
        self.assertEqual(application['applicant_email'], 'new@example.test')
        self.assertEqual(application['applicant_phone'], '0611223344')
        self.request('/ads/3/applications','POST',{'name':'Someone Else','email':'other@example.test','message':'Un message suffisamment long pour cette candidature.'},400)
        self.request('/ads/2/applications','POST',{'message':'Deuxième tentative de candidature pour la même offre.'},409)
        self.assertEqual(len(self.request('/my-applications')['items']),1)
        self.request('/auth/logout','POST',{})
        self.assertIsNone(self.request('/auth/me')['user'])
        self.request('/auth/login','POST',{'email':'new@example.test','password':'incorrect'},401)
        self.request('/auth/login','POST',{'email':'new@example.test','password':'Password2026!'})
        self.request('/account','PATCH',{'current_password':'Password2026!','password':'NewPassword2026!'})
        self.request('/auth/logout','POST',{})
        self.request('/auth/login','POST',{'email':'new@example.test','password':'NewPassword2026!'})

    def test_04_application_requires_account_and_validation(self):
        message = 'Bonjour, je souhaite vous rejoindre pour participer à vos projets.'
        self.request('/ads/1/applications','POST',{'name':'Guest','email':'guest@example.test','phone':'060000','message':message},401)
        self.request('/ads/1/applications','POST',{'name':'Camille','email':'camille@hireloop.test','message':message},401)
        self.request('/auth/login','POST',{'email':'camille@hireloop.test','password':'Camille2026!'})
        self.request('/ads/2/applications','POST',{'message':'court'},400)
        self.request('/ads/999999/applications','POST',{'message':message},404)
        self.request('/auth/logout','POST',{})
        self.request('/auth/register','POST',{'name':'A','email':'invalid','password':'Password2026!'},400)
        self.request('/auth/register','POST',{'name':'A','email':'a@test.fr','password':'short'},400)
        self.request('/auth/register','POST',{'name':'A','email':'a@test.fr','password':'Password2026!','role':'admin'},400)
        self.request('/auth/register','POST',{'name':'A','email':'admin@hireloop.test','password':'Password2026!'},409)

    def test_05_admin_crud_all_tables(self):
        self.admin()
        company=self.request('/companies','POST',{'name':'Test Co','industry':'Tech','location':'Paris','description':'Test company'},201)
        category=self.request('/categories','POST',{'name':'Test category'},201)
        person=self.request('/people','POST',{'name':'Contact','email':'contact@test.fr','password':'Contact2026!'},201)
        ad=self.request('/ads','POST',{'company_id':company['id'],'category_id':category['id'],'contact_id':person['id'],'title':'Test job','summary':'Résumé','description':'Description','requirements':'Profil','location':'Paris','contract':'CDI','work_mode':'Hybride','salary_min':30000,'salary_max':40000},201)
        application=self.request('/applications','POST',{'ad_id':ad['id'],'person_id':person['id'],'message':'Test message'},201)
        for resource,row,change in [('companies',company,{'name':'Updated Co'}),('categories',category,{'name':'Updated Category'}),('people',person,{'phone':'0612345678'}),('ads',ad,{'title':'Updated job'}),('applications',application,{'status':'Entretien'})]:
            self.assertGreater(self.request('/'+resource+'?limit=100')['total'],0)
            self.assertEqual(self.request(f'/{resource}/{row["id"]}')['id'],row['id'])
            updated=self.request(f'/{resource}/{row["id"]}','PATCH',change)
            for k,v in change.items(): self.assertEqual(updated[k],v)
        self.request(f'/companies/{company["id"]}','DELETE',expected=409)
        self.request(f'/categories/{category["id"]}','DELETE',expected=409)
        self.request(f'/ads/{ad["id"]}','PATCH',{'salary_max':1},400)
        self.request('/categories','POST',{},400)
        self.request('/categories','POST',{'name':'Updated Category'},409)
        self.request('/people/1','PATCH',{'role':'candidate'},400)
        self.request('/people/1','DELETE',expected=400)
        self.request('/ads/999999','PATCH',{'title':'x'},404)
        self.request('/companies','POST',{'name':'X','industry':'X','location':'X','description':'X','website':'javascript:alert(1)'},400)
        self.request('/people','POST',{'name':'X','email':'x@test.fr','role':'superadmin'},400)
        self.request('/categories','POST',{'name':'X','evil':'value'},400)
        self.request(f'/categories/{category["id"]}','PUT',{'name':'Replaced Category'})
        for resource,row in [('applications',application),('ads',ad),('companies',company),('categories',category),('people',person)]:
            self.request(f'/{resource}/{row["id"]}','DELETE')
            self.request(f'/{resource}/{row["id"]}',expected=404)

    def test_06_security_and_invalid_requests(self):
        self.assertEqual(self.request('/ads?q=%27%20OR%201%3D1--')['total'],0)
        self.request('/auth/login','POST',{'email':'admin@hireloop.test','password':'Admin2026!'},403,{'Origin':'https://evil.test','Content-Type':'application/json'})
        self.request('/not-found',expected=404)
        self.request('/auth/register','POST',{},400)
        self.request('/auth/login','POST',{'email':None,'password':{}},400)

    def test_07_company_admin_isolation(self):
        self.admin()
        self.request('/people', 'POST', {'name':'Missing company', 'email':'missing@test.fr', 'role':'company_admin'}, 400)
        self.request('/people/1', 'PATCH', {'role':'company_admin', 'company_id':1}, 400)
        person = self.request('/people', 'POST', {'name':'Company Admin', 'email':'company@test.fr', 'password':'Company2026!', 'role':'company_admin', 'company_id':1}, 201)
        self.request('/auth/logout', 'POST', {})
        self.request('/auth/login', 'POST', {'email':'company@test.fr', 'password':'Company2026!'})
        self.assertEqual(self.request('/auth/me')['user']['company_id'], 1)
        self.assertEqual([r['id'] for r in self.request('/companies')['items']], [1])
        self.assertTrue(all(r['company_id'] == 1 for r in self.request('/admin/ads')['items']))
        self.assertEqual(self.request('/admin/stats')['companies'], 1)
        self.request('/companies/2', expected=403)
        self.request('/companies/2', 'PATCH', {'name':'Forbidden'}, 403)
        self.request('/ads/2', 'DELETE', expected=403)
        self.request('/admin/ads/2', expected=403)
        self.request('/applications/2', expected=403)
        self.request('/applications/2', 'PATCH', {'status':'Entretien'}, 403)
        self.request('/people/3', expected=403)
        self.request('/people/1', 'PATCH', {'role':'candidate'}, 403)
        self.request('/people', 'POST', {'name':'X','email':'x@x.test','role':'admin'}, 403)
        self.request('/account', 'PATCH', {'role':'admin'}, 400)
        self.request('/account', 'PATCH', {'company_id':2}, 400)
        self.request('/categories', 'POST', {'name':'Forbidden'}, 403)
        self.request('/companies/1', 'DELETE', expected=403)
        self.request('/companies/1', 'PATCH', {'name':'Studio North'})
        self.request('/applications/1', 'PATCH', {'status':'Entretien'})
        self.request('/applications/1', 'PATCH', {'ad_id':2}, 403)
        self.request('/ads/1', 'PATCH', {'company_id':2}, 403)
        self.request('/ads/1', 'PATCH', {'contact_id':1}, 403)
        ad = {k:v for k,v in self.request('/ads/1').items() if k in server.RESOURCES['ads']}
        ad['contact_id'] = person['id']
        created = self.request('/ads', 'POST', ad, 201)
        self.request('/ads/' + str(created['id']), 'PATCH', {'title':'Company offer'})
        self.request('/ads/' + str(created['id']), 'DELETE')
        # The company and contact are optional for recruiters: they come from the session.
        minimal = {k: v for k, v in ad.items() if k not in ('company_id', 'contact_id')}
        own = self.request('/ads', 'POST', minimal, 201)
        self.assertEqual((own['company_id'], own['contact_id']), (1, person['id']))
        self.request('/ads/' + str(own['id']), 'DELETE')
        self.request('/auth/logout', 'POST', {})
        self.admin()
        self.request('/people/' + str(person['id']), 'PATCH', {'role':'candidate'})
        self.assertIsNone(self.request('/people/' + str(person['id']))['company_id'])

    def test_09_sorting_and_pagination_preserve_results(self):
        from contextlib import closing

        with closing(server.connect()) as db:
            offers = [dict(row) for row in db.execute("SELECT * FROM ads WHERE status='published'")]
            orders = {
                'relevant': lambda row: (row['featured'], row['created_at'], row['id']),
                'recent': lambda row: (row['created_at'], row['id']),
                'salary': lambda row: (row['salary_max'], row['id']),
                'unknown': lambda row: row['id'],
            }
            for sort, key in orders.items():
                with self.subTest(sort=sort):
                    expected = [row['id'] for row in sorted(offers, key=key, reverse=True)]
                    actual = []
                    for page in range(1, (len(offers) + 2) // 3 + 1):
                        result = self.request(f'/ads?sort={sort}&page={page}&limit=3')
                        self.assertEqual(result['total'], len(offers))
                        actual.extend(row['id'] for row in result['items'])
                    self.assertEqual(actual, expected)

            filtered = self.request('/ads?company_id=1&location=Paris&limit=100')
            expected = {row['id'] for row in offers if row['company_id'] == 1 and row['location'] == 'Paris'}
            self.assertEqual({row['id'] for row in filtered['items']}, expected)
            self.assertEqual(filtered['total'], len(expected))
            self.assertEqual(self.request('/ads?page=999999')['items'], [])
            self.assertEqual(self.request('/ads?limit=1000')['limit'], 100)

    def test_08_legacy_migration_preserves_relations(self):
        import re
        import sqlite3
        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        try:
            legacy_people = """CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                phone TEXT NOT NULL DEFAULT '', password_hash TEXT,
                role TEXT NOT NULL DEFAULT 'candidate' CHECK (role IN ('candidate', 'admin')),
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')));"""
            schema = (server.ROOT / 'schema.sql').read_text(encoding='utf-8')
            schema, replaced = re.subn(r'CREATE TABLE\s+IF NOT EXISTS people \(.*?\n\s*\);', lambda _: legacy_people, schema, count=1, flags=re.S)
            self.assertEqual(replaced, 1)
            db.executescript(schema)
            db.executemany('INSERT INTO people(name,email,role) VALUES(?,?,?)', [('Admin','a@test.fr','admin'),('Camille','c@test.fr','candidate'),('Alex','b@test.fr','candidate')])
            db.execute("INSERT INTO companies(name,industry,location,description) VALUES('Co','Tech','Paris','Test')")
            db.execute("INSERT INTO categories(name) VALUES('Test')")
            db.execute("INSERT INTO ads(company_id,category_id,contact_id,title,summary,description,requirements,location,contract,work_mode,salary_min,salary_max) VALUES(1,1,1,'Job','S','D','R','Paris','CDI','Hybride',1,2)")
            db.execute("INSERT INTO applications(ad_id,person_id,message) VALUES(1,2,'Message')")
            db.commit()
            self.assertNotIn('company_id', [r['name'] for r in db.execute('PRAGMA table_info(people)')])
            before = {t: [tuple(r) for r in db.execute('SELECT * FROM ' + t)] for t in ('ads','applications','companies')}
            server.migrate_people(db)
            server.migrate_people(db)
            for table, rows in before.items():
                self.assertEqual(rows, [tuple(r) for r in db.execute('SELECT * FROM ' + table)])
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(db.execute('SELECT role FROM people WHERE id=1').fetchone()[0], 'admin')
            db.execute("UPDATE people SET role='company_admin',company_id=1 WHERE id=3")
            self.assertEqual(db.execute('SELECT company_id FROM people WHERE id=3').fetchone()[0], 1)
        finally:
            db.close()

    def test_10_demo_company_account(self):
        user = self.request('/auth/login', 'POST', {'email':'company@test.com', 'password':'Company123!'})['user']
        self.assertEqual((user['role'], user['company_id']), ('company_admin', 1))
        self.assertEqual([r['id'] for r in self.request('/companies')['items']], [1])

    def test_11_login_limit_only_counts_failures_per_visitor(self):
        good = {'email':'admin@hireloop.test','password':'Admin2026!'}
        bad = {'email':'admin@hireloop.test','password':'incorrect'}
        def from_ip(forwarded):
            return {'Content-Type':'application/json','X-Forwarded-For':forwarded}
        with unittest.mock.patch.object(server,'LOGIN_FAILURE_LIMIT',(3,300)):
            for _ in range(5):
                self.request('/auth/login','POST',good)
            for _ in range(3):
                self.request('/auth/login','POST',bad,401)
            self.request('/auth/login','POST',bad,429)
            self.request('/auth/login','POST',good,429)
            # Sans TRUST_PROXY, l'en-tête est ignoré et ne permet pas de contourner la limite.
            self.request('/auth/login','POST',good,429,from_ip('1.1.1.1'))
            self.server.rate_hits.clear()
            with unittest.mock.patch.dict('os.environ',{'TRUST_PROXY':'1'}):
                for _ in range(3):
                    self.request('/auth/login','POST',bad,401,from_ip('8.8.8.8, 10.0.0.1'))
                self.request('/auth/login','POST',good,429,from_ip('8.8.8.8, 10.0.0.1'))
                # Un autre visiteur reste libre, mais une valeur ajoutée à gauche ne change rien.
                self.request('/auth/login','POST',good,200,from_ip('1.1.1.1, 10.0.0.1'))
                self.request('/auth/login','POST',good,429,from_ip('1.1.1.1, 8.8.8.8, 10.0.0.1'))

    def test_12_signup_limit(self):
        with unittest.mock.patch.object(server,'SIGNUP_LIMIT',(2,3600)):
            for i in range(2):
                self.request('/auth/register','POST',{'name':'Bot','email':f'limit{i}@example.test','password':'Password2026!'},201)
            self.request('/auth/register','POST',{'name':'Bot','email':'limit2@example.test','password':'Password2026!'},429)

    def test_13_application_limits(self):
        message = {'message':'Bonjour, je souhaite vous rejoindre pour participer à vos projets.'}
        self.request('/auth/register','POST',{'name':'One','email':'apply1@example.test','password':'Password2026!'},201)
        with unittest.mock.patch.object(server,'APPLICATION_ACCOUNT_LIMIT',(1,3600)):
            self.request('/ads/5/applications','POST',message,201)
            self.request('/ads/6/applications','POST',message,429)
        self.server.rate_hits.clear()
        with unittest.mock.patch.object(server,'APPLICATION_IP_LIMIT',(1,3600)):
            self.request('/ads/6/applications','POST',message,201)
            self.request('/auth/register','POST',{'name':'Two','email':'apply2@example.test','password':'Password2026!'},201)
            self.request('/ads/6/applications','POST',message,429)

    def test_14_password_change_ends_other_sessions(self):
        account = {'email':'sessions@example.test','password':'Password2026!'}
        self.request('/auth/register','POST',{'name':'Sessions',**account},201)
        first = self.client
        second = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.client = second
        ident = self.request('/auth/login','POST',account)['user']['id']
        # Modifier le profil sans changer le mot de passe conserve les sessions.
        self.request('/account','PATCH',{'phone':'0600000001'})
        self.client = first
        self.assertIsNotNone(self.request('/auth/me')['user'])
        self.request('/account','PATCH',{'current_password':account['password'],'password':'NewPassword2026!'})
        self.assertIsNotNone(self.request('/auth/me')['user'])
        self.client = second
        self.assertIsNone(self.request('/auth/me')['user'])
        # Une réinitialisation par l'administrateur ferme toutes les sessions du compte.
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.admin()
        self.request(f'/people/{ident}','PATCH',{'password':'ResetPassword2026!'})
        self.assertEqual(self.request('/auth/me')['user']['role'],'admin')
        self.client = first
        self.assertIsNone(self.request('/auth/me')['user'])

    def test_15_robots_and_sitemap(self):
        site = self.base.removesuffix('/api')
        with urllib.request.urlopen(site + '/robots.txt') as response:
            robots = response.read().decode()
            self.assertTrue(response.headers['Content-Type'].startswith('text/plain'))
        self.assertIn(f'Sitemap: {site}/sitemap.xml', robots)
        self.assertIn('Disallow: /api/admin/', robots)
        self.assertNotIn('Disallow: /api/ads', robots)
        with urllib.request.urlopen(site + '/sitemap.xml') as response:
            sitemap = response.read().decode()
            self.assertTrue(response.headers['Content-Type'].startswith('application/xml'))
        self.assertIn(f'<loc>{site}/</loc>', sitemap)
        # Un en-tête Host invalide ne doit pas se retrouver dans le fichier généré.
        evil = urllib.request.Request(site + '/sitemap.xml', headers={'Host':'evil.test"><script>'})
        with urllib.request.urlopen(evil) as response:
            self.assertNotIn('evil.test', response.read().decode())

    # ------------------------------------------------------------------ v2 features
    def other_client(self):
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def as_client(self, client, call, *args, **kwargs):
        previous, self.client = self.client, client
        try:
            return call(*args, **kwargs)
        finally:
            self.client = previous

    def raw(self, path):
        with self.client.open(self.base + path) as response:
            return response.headers, response.read()

    def test_16_ad_lifecycle_and_views(self):
        public_ids = [a['id'] for a in self.request('/ads?limit=100')['items']]
        self.assertNotIn(13, public_ids)              # draft
        self.assertNotIn(14, public_ids)              # closed
        self.request('/ads/13', expected=404)
        self.assertEqual(self.request('/ads/14')['status'], 'closed')
        # The company that owns the draft can preview it.
        self.request('/auth/login','POST',{'email':'company@test.com','password':'Company123!'})
        preview = self.request('/ads/13')
        self.assertTrue(preview['viewer']['can_manage'])
        # A company admin cannot feature its own ads.
        self.request('/ads/2', 'PATCH', {'featured':0}, 403)
        self.request('/ads/11', 'PATCH', {'featured':1, 'title':'Brand Designer freelance'})
        self.assertEqual(self.request('/admin/ads/11')['featured'], 0)
        self.request('/auth/logout','POST',{})
        # Closed ads do not accept applications.
        self.request('/auth/login','POST',{'email':'alex@hireloop.test','password':'Alex2026!'})
        self.request('/ads/14/applications','POST',{'message':'Bonjour, je souhaite vous rejoindre pour ce stage.'},409)
        self.request('/ads/13/applications','POST',{'message':'Bonjour, je souhaite vous rejoindre pour ce poste.'},404)
        self.request('/auth/logout','POST',{})
        self.admin()
        self.request('/ads/1/applications','POST',{'message':'Un administrateur ne postule pas aux offres.'},403)
        # Publishing a draft makes it public and dates it from today.
        self.admin()
        before = self.request('/admin/ads/13')
        published = self.request('/ads/13', 'PATCH', {'status':'published'})
        self.assertGreater(published['created_at'], before['created_at'])
        self.request('/auth/logout','POST',{})
        self.assertIn(13, [a['id'] for a in self.request('/ads?limit=100')['items']])
        self.request('/ads/13'); self.request('/ads/13')
        self.admin()
        self.assertEqual(self.request('/admin/ads/13')['views'], 2)
        self.request('/ads/13'); self.assertEqual(self.request('/admin/ads/13')['views'], 2)   # admins are not counted
        self.request('/ads/13', 'PATCH', {'status':'draft'})
        self.request('/ads/13', 'PATCH', {'status':'archived'}, 400)

    def test_17_saved_jobs_and_withdrawal(self):
        self.request('/auth/register','POST',{'name':'Saver','email':'saver@example.test','password':'Password2026!'},201)
        self.request('/saved/2', 'PUT')
        self.request('/saved/2', 'PUT')                # idempotent
        self.request('/saved/13', 'PUT', expected=404) # drafts cannot be saved
        self.assertEqual(self.request('/auth/me')['saved'], [2])
        self.assertEqual([a['id'] for a in self.request('/saved')['items']], [2])
        self.assertTrue(self.request('/ads/2')['viewer']['saved'])
        self.request('/saved/2', 'DELETE')
        self.assertEqual(self.request('/saved')['items'], [])
        message = {'message':'Bonjour, je souhaite vous rejoindre pour participer à vos projets.'}
        first = self.request('/ads/2/applications','POST',message,201)['application']
        self.assertEqual(self.request('/ads/2')['viewer']['application']['status'], 'Reçue')
        self.request(f'/my-applications/{first["id"]}', 'DELETE')
        self.request(f'/my-applications/{first["id"]}', 'DELETE', expected=404)
        second = self.request('/ads/3/applications','POST',message,201)['application']
        admin = self.other_client()
        self.as_client(admin, self.admin)
        self.as_client(admin, self.request, f'/applications/{second["id"]}', 'PATCH', {'status':'Acceptée'})
        self.request(f'/my-applications/{second["id"]}', 'DELETE', expected=400)
        # Someone else's application cannot be withdrawn.
        self.request('/my-applications/1', 'DELETE', expected=404)
        self.request('/saved', expected=200)
        self.request('/auth/logout','POST',{})
        self.request('/saved', expected=401)

    def test_18_history_notes_and_updates(self):
        self.request('/auth/register','POST',{'name':'History','email':'history@example.test','password':'Password2026!'},201)
        ident = self.request('/ads/6/applications','POST',{'message':'Bonjour, votre moteur de calcul m’intéresse beaucoup.'},201)['application']['id']
        item = self.request('/my-applications')['items'][0]
        self.assertEqual([e['status'] for e in item['events']], ['Reçue'])
        self.assertFalse(item['updated'])
        self.assertEqual(self.request('/auth/me')['updates'], 0)
        admin = self.other_client()
        self.as_client(admin, self.admin)
        self.as_client(admin, self.request, f'/applications/{ident}', 'PATCH', {'status':'Entretien','notes':'Secret recruiter note'})
        self.as_client(admin, self.request, f'/applications/{ident}', 'PATCH', {'notes':'Secret recruiter note, edited'})
        detail = self.as_client(admin, self.request, f'/admin/applications/{ident}')
        self.assertEqual([e['status'] for e in detail['events']], ['Reçue','Entretien'])
        self.assertEqual(detail['ad_title'], 'Développeur·se Back-end Python')
        self.assertIn('candidate', detail)
        self.assertEqual(self.request('/auth/me')['updates'], 1)
        response = self.request('/my-applications')
        self.assertNotIn('Secret', json.dumps(response))
        self.assertTrue(response['items'][0]['updated'])
        self.assertEqual(len(response['items'][0]['events']), 2)
        self.request('/my-applications/seen', 'POST', {})
        self.assertEqual(self.request('/auth/me')['updates'], 0)
        # Company admins may write notes on their own company's applications only.
        company = self.other_client()
        self.as_client(company, self.request, '/auth/login','POST',{'email':'company@test.com','password':'Company123!'})
        self.as_client(company, self.request, '/applications/4', 'PATCH', {'notes':'Rappeler lundi.'})
        self.as_client(company, self.request, f'/applications/{ident}', 'PATCH', {'notes':'x'}, 403)

    def test_19_admin_lists_dashboard_and_export(self):
        self.admin()
        received = self.request('/admin/applications?status=Re%C3%A7ue&limit=100')
        self.assertTrue(received['items'] and all(a['status'] == 'Reçue' for a in received['items']))
        self.assertEqual(received['facets']['Reçue'], received['total'])
        self.assertGreater(sum(received['facets'].values()), received['total'])
        self.assertIn('ad_title', received['items'][0])
        found = self.request('/admin/ads?q=React')
        self.assertEqual(found['total'], 1)
        self.assertEqual(found['items'][0]['company_name'], 'Studio North')
        self.assertGreaterEqual(found['items'][0]['applications_count'], 3)
        self.assertTrue(all(p['role'] == 'admin' for p in self.request('/admin/people?role=admin')['items']))
        self.assertNotIn('password_hash', json.dumps(self.request('/admin/people?limit=100')))
        self.assertEqual(self.request('/admin/ads?status=draft')['facets'].get('draft'), 1)
        dashboard = self.request('/admin/dashboard')
        self.assertEqual(len(dashboard['timeline']), 14)
        self.assertIn('people', dashboard)
        self.assertEqual(dashboard['ads']['closed'], 1)
        headers, body = self.raw('/admin/applications/export')
        self.assertTrue(headers['Content-Type'].startswith('text/csv'))
        self.assertIn('attachment', headers['Content-Disposition'])
        text = body.decode('utf-8')
        self.assertTrue(text.startswith('﻿ID;Date;Offre'))
        self.assertIn('Orbit', text)
        self.request('/auth/logout','POST',{})
        self.request('/admin/dashboard', expected=401)
        self.request('/admin/applications/export', expected=401)
        self.request('/auth/login','POST',{'email':'company@test.com','password':'Company123!'})
        dashboard = self.request('/admin/dashboard')
        self.assertNotIn('people', dashboard)
        self.assertTrue(dashboard['top_ads'])
        studio = {a['id'] for a in self.request('/admin/ads?limit=100')['items']}
        self.assertTrue(all(a['id'] in studio for a in dashboard['top_ads']))
        self.assertTrue(all(a['ad_id'] in studio for a in dashboard['recent_applications']))
        text = self.raw('/admin/applications/export')[1].decode('utf-8')
        self.assertIn('Studio North', text)
        self.assertNotIn('Orbit', text)

    def test_20_account_deletion(self):
        account = {'email':'leaving@example.test','password':'Password2026!'}
        self.request('/auth/register','POST',{'name':'Leaving',**account},201)
        self.request('/ads/7/applications','POST',{'message':'Bonjour, ce stage correspond à ce que je cherche.'},201)
        self.request('/account','DELETE',{'current_password':'wrong'},400)
        self.request('/account','DELETE',{'current_password':account['password']})
        self.assertIsNone(self.request('/auth/me')['user'])
        self.request('/auth/login','POST',account,401)
        # Recruiters still named as an ad contact must hand it over first.
        self.request('/auth/login','POST',{'email':'company@test.com','password':'Company123!'})
        self.request('/account','DELETE',{'current_password':'Company123!'},409)
        self.request('/auth/logout','POST',{})
        self.admin()
        self.request('/account','DELETE',{'current_password':'Admin2026!'},400)

    def test_21_directory_similar_and_filters(self):
        companies = self.request('/directory/companies')['items']
        self.assertEqual(len(companies), 6)
        studio = next(c for c in companies if c['id'] == 1)
        self.assertEqual(studio['open_ads'], 2)
        profile = self.request('/directory/companies/1')
        self.assertTrue(all(a['status'] == 'published' for a in profile['ads']))
        self.request('/directory/companies/999', expected=404)
        similar = self.request('/ads/1/similar')['items']
        self.assertTrue(0 < len(similar) <= 3)
        self.assertNotIn(1, [a['id'] for a in similar])
        self.request('/ads/13/similar', expected=404)
        meta = self.request('/meta')
        self.assertEqual(sum(c['count'] for c in meta['categories']), 12)
        self.assertIn('CDI', meta['contracts'])
        rich = self.request('/ads?min_salary=60000&limit=100')['items']
        self.assertTrue(rich and all(a['salary_max'] >= 60000 for a in rich))
        self.request('/ads?min_salary=abc', expected=400)
        self.assertEqual(self.request('/ads?q=Infrastructure')['total'], 1)   # category names are searchable

    def test_22_field_validation(self):
        self.request('/auth/register','POST',{'name':'Valid','email':'valid@example.test','password':'Password2026!'},201)
        self.request('/account','PATCH',{'phone':'call me'},400)
        self.request('/account','PATCH',{'website':'ftp://example.test'},400)
        self.request('/account','PATCH',{'name':'x' * 200},400)
        user = self.request('/account','PATCH',{'headline':'Designer','location':'Lille','website':'https://example.test','bio':'Hello'})['user']
        self.assertEqual((user['headline'], user['location']), ('Designer', 'Lille'))
        self.request('/auth/logout','POST',{})
        self.admin()
        self.request('/ads/1','PATCH',{'contract':'Intérim'},400)
        self.request('/ads/1','PATCH',{'featured':2},400)
        self.request('/applications/1','PATCH',{'status':'Archivée'},400)
        # A request without a Host header used to crash the origin check.
        import http.client
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        connection.putrequest('POST', '/api/auth/logout', skip_host=True)
        connection.putheader('Origin', 'https://evil.test')
        connection.putheader('Content-Length', '0')
        connection.endheaders()
        self.assertEqual(connection.getresponse().status, 403)
        connection.close()

if __name__=='__main__':
    unittest.main(verbosity=2)
