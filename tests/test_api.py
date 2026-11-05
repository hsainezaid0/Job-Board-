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
        self.request('/auth/logout', 'POST', {})
        self.admin()
        self.request('/people/' + str(person['id']), 'PATCH', {'role':'candidate'})
        self.assertIsNone(self.request('/people/' + str(person['id']))['company_id'])

    def test_09_sorting_and_pagination_preserve_results(self):
        from contextlib import closing

        with closing(server.connect()) as db:
            offers = [dict(row) for row in db.execute('SELECT * FROM ads')]
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

if __name__=='__main__':
    unittest.main(verbosity=2)
