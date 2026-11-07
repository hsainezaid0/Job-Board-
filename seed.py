"""Fictional demo data inserted by the backend, only into an empty database."""
import time


def ago(days=0, hours=0):
    # UTC timestamp `days` days and `hours` hours in the past, in SQLite's format.
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - days * 86400 - hours * 3600))


# Pre-computed PBKDF2 hashes, so the first start stays fast.
ADMIN_HASH = '8b9438be42dab3fd841eec764eb9e58d$ca8fe3f0e9581b8d37d1dc374d4580768e40edfe4a33cb7e6bb088128321dc29'   # Admin2026!
CAMILLE_HASH = '70e992c3810ab9a037764a4c1ab0444b$714428043750175796f40735aca0219c63556f71d3161556f89916c748922af6'  # Camille2026!
ALEX_HASH = 'bfa33982df212a602371d210ad7f5364$908d4a50e72685fcf21a394d9f7fa1a41736a96dc142afa249d63d092c8adf57'     # Alex2026!
COMPANY_HASH = 'b07fbc9c5b42df625ff2983147b6228b$d84023625318cbbfe550e734ec7d4b59d91a3a9a92fba65f042a320834e9c113'  # Company123!

COMPANIES = [
    ('Studio North', 'Design & technologie', 'Paris', 'https://example.com',
     'Studio indépendant de 18 personnes. Nous concevons et développons des applications web pour des clients de la culture, de la santé et de l’éducation. Pas de sous-traitance : chaque projet est mené de bout en bout par la même équipe.',
     '#7253a0'),
    ('Bloom', 'Climate tech', 'Lyon', 'https://example.com',
     'Bloom édite un logiciel de bilan carbone utilisé par 400 PME. Notre objectif : qu’une entreprise de 50 salariés puisse mesurer ses émissions sans cabinet de conseil.',
     '#43775a'),
    ('Orbit', 'Logiciel SaaS', 'Bordeaux', 'https://example.com',
     'Orbit est un outil de gestion de projet pour les agences. 35 personnes, entièrement financées par nos clients, avec une équipe produit qui livre chaque semaine.',
     '#4077a2'),
    ('Maison Atlas', 'Commerce & lifestyle', 'Nantes', 'https://example.com',
     'Maison Atlas regroupe trois marques de mobilier et de décoration fabriquées en France. Boutique en ligne, deux showrooms et un atelier à Rezé.',
     '#b36d4c'),
    ('Linear Labs', 'Intelligence artificielle', 'Paris', 'https://example.com',
     'Linear Labs aide les services clients à classer et résumer leurs tickets. Équipe de 25 personnes, dont un tiers en recherche appliquée.',
     '#525aa4'),
    ('Collectif', 'Services numériques', 'Lille', 'https://example.com',
     'Coopérative de 40 consultants spécialisés dans les services publics numériques. Accessibilité et écoconception font partie de chaque mission, pas d’une option.',
     '#92742e'),
]

# company, category, contact, title, summary, location, contract, mode, low, high, featured, status, days ago, views,
# description, requirements (one item per line)
JOBS = [
    (1, 1, 4, 'Développeur·se Front-end React',
     'Créez des expériences web soignées, rapides et accessibles au sein d’un studio qui aime les beaux produits.',
     'Paris', 'CDI', 'Hybride', 42000, 55000, 1, 'published', 0, 214,
     'Vous rejoignez une équipe de quatre développeurs front-end. Nos projets actuels : une billetterie pour un réseau de théâtres et un outil de prise de rendez-vous pour des centres de santé.\n\n'
     'Notre stack : React, TypeScript, Vite, Playwright pour les tests de bout en bout. Les maquettes arrivent de Figma, mais vous participez aux ateliers avec les designers dès le début.\n\n'
     'Deux jours sur place par semaine (mardi et jeudi), le reste où vous voulez. Mutuelle prise en charge à 100 %, 1 500 € par an de budget formation.',
     'Au moins deux ans d’expérience avec React en production\n'
     'Bonne connaissance de l’accessibilité (RGAA ou WCAG)\n'
     'Vous écrivez des tests sans qu’on vous le demande\n'
     'Un plus : une expérience avec un design system'),
    (2, 2, 1, 'Product Designer',
     'Imaginez des interfaces qui rendent la transition écologique plus simple, un écran à la fois.',
     'Lyon', 'CDI', 'Hybride', 40000, 52000, 1, 'published', 1, 168,
     'Nos utilisateurs sont des responsables RSE ou des dirigeants de PME, rarement experts du carbone. Votre travail : rendre des calculs complexes compréhensibles en quelques écrans.\n\n'
     'Vous travaillez en binôme avec une product manager et intervenez de la recherche utilisateur jusqu’au suivi après la mise en production. Nous faisons au moins quatre entretiens utilisateurs par mois.\n\n'
     'Bureaux à la Croix-Rousse, trois jours sur place.',
     'Trois ans d’expérience en design produit sur un logiciel B2B\n'
     'Un portfolio qui montre votre démarche, pas seulement le résultat\n'
     'À l’aise avec Figma et les prototypes interactifs\n'
     'Intérêt pour les sujets climat'),
    (3, 1, 1, 'Développeur·se Full Stack',
     'Construisez les prochaines fonctionnalités de notre plateforme collaborative avec une équipe passionnée.',
     'Bordeaux', 'CDI', 'Télétravail', 45000, 60000, 0, 'published', 2, 131,
     'L’équipe produit compte huit développeurs répartis en deux squads. Vous rejoignez celle qui s’occupe de la planification et du suivi du temps.\n\n'
     'Stack : Node.js, PostgreSQL, Vue 3. Déploiement continu, revues de code systématiques, une semaine par trimestre consacrée à la dette technique.\n\n'
     'Poste 100 % à distance depuis la France, avec un séminaire de trois jours tous les deux mois à Bordeaux.',
     'Trois ans d’expérience en développement web\n'
     'À l’aise avec SQL et la modélisation de données\n'
     'Expérience d’un framework front-end moderne\n'
     'Bonne communication écrite : l’équipe est distribuée'),
    (5, 3, 1, 'Data Analyst Junior',
     'Donnez du sens aux données et aidez nos équipes à prendre des décisions éclairées.',
     'Paris', 'CDI', 'Hybride', 38000, 46000, 1, 'published', 3, 152,
     'Vous rejoignez l’équipe data (trois personnes) et répondez aux questions des équipes commerciale et produit : quels clients utilisent quelle fonctionnalité, où les utilisateurs abandonnent, ce qu’une évolution a changé.\n\n'
     'Outils : SQL sur BigQuery, dbt, Metabase et un peu de Python. Un data analyst senior vous accompagne pendant les six premiers mois.',
     'Une première expérience (stage ou alternance comprise) en analyse de données\n'
     'Bon niveau en SQL\n'
     'Capacité à expliquer un résultat à quelqu’un qui n’est pas du métier\n'
     'Python est un plus, pas un prérequis'),
    (4, 4, 1, 'Assistant·e Communication',
     'Faites rayonner des marques engagées à travers des contenus créatifs et des campagnes qui ont du sens.',
     'Nantes', 'Alternance', 'Sur site', 14000, 19000, 0, 'published', 4, 77,
     'Alternance de 12 ou 24 mois au sein d’une équipe marketing de cinq personnes. Vous préparez les publications sur les réseaux sociaux, la newsletter mensuelle et les supports pour les deux showrooms.\n\n'
     'Rythme : trois semaines en entreprise, une semaine à l’école. Les bureaux sont à côté de l’atelier, à Rezé.',
     'Inscription en école de communication ou de marketing (bac+3 à bac+5)\n'
     'Aisance rédactionnelle et orthographe soignée\n'
     'Notions de Canva, Photoshop ou Figma\n'
     'Intérêt pour le design et l’artisanat'),
    (2, 1, 1, 'Développeur·se Back-end Python',
     'Concevez des API fiables pour accélérer la mesure et la réduction de l’empreinte carbone.',
     'Lyon', 'CDI', 'Télétravail', 44000, 58000, 0, 'published', 5, 119,
     'Notre moteur de calcul transforme des factures et des relevés en émissions de CO2. Vous travaillez sur ce moteur et sur l’API publique utilisée par nos partenaires comptables.\n\n'
     'Stack : Python 3.12, FastAPI, PostgreSQL, Celery. Code revu par deux personnes, tests obligatoires, mises en production plusieurs fois par jour.',
     'Trois ans d’expérience en Python côté serveur\n'
     'Expérience de la conception d’API REST\n'
     'Bonnes bases en bases de données relationnelles\n'
     'Un plus : Docker et une première expérience d’astreinte'),
    (6, 2, 1, 'UX Designer',
     'Allez à la rencontre des utilisateurs et transformez leurs besoins en parcours intuitifs.',
     'Lille', 'Stage', 'Hybride', 12000, 18000, 0, 'published', 6, 64,
     'Stage de six mois à partir de février. Vous participez à une mission pour une collectivité : refonte du parcours d’inscription à la cantine et au périscolaire.\n\n'
     'Au programme : entretiens avec des familles, tests d’utilisabilité, maquettes et vérification de l’accessibilité avec notre experte RGAA.',
     'Formation en design d’interaction, UX ou ergonomie\n'
     'Un premier projet de recherche utilisateur, même scolaire\n'
     'Envie de travailler sur des services publics'),
    (3, 5, 1, 'Product Manager',
     'Accompagnez une équipe pluridisciplinaire de la découverte au lancement de nouveaux services.',
     'Bordeaux', 'CDD', 'Hybride', 46000, 62000, 0, 'published', 7, 98,
     'CDD de 12 mois pour remplacer notre PM pendant un congé parental, avec une possibilité de CDI à la suite.\n\n'
     'Vous prenez en charge la squad facturation : quatre développeurs, une designer. Priorités du moment : la facturation récurrente et la connexion avec deux logiciels comptables.',
     'Trois ans d’expérience en gestion de produit SaaS\n'
     'Vous savez dire non et expliquer pourquoi\n'
     'À l’aise avec les données d’usage\n'
     'Une expérience de la facturation ou de la comptabilité est appréciée'),
    (5, 3, 1, 'Machine Learning Engineer',
     'Mettez des modèles en production et contribuez à une IA robuste, mesurable et responsable.',
     'Paris', 'CDI', 'Hybride', 50000, 70000, 0, 'published', 8, 187,
     'Vous faites le lien entre l’équipe de recherche et la production. Nos modèles classent plus de deux millions de tickets par mois : la latence, le coût et la qualité comptent autant que la précision.\n\n'
     'Stack : Python, PyTorch, Ray, Kubernetes. Chaque modèle mis en production est accompagné d’un tableau de bord de qualité.',
     'Trois ans d’expérience en ML appliqué\n'
     'Vous avez déjà mis un modèle en production et vous l’avez suivi\n'
     'Solides bases en ingénierie logicielle\n'
     'Un plus : expérience des LLM et de leur évaluation'),
    (6, 6, 1, 'Ingénieur·e DevOps',
     'Améliorez nos pipelines et faites grandir une infrastructure fiable et sobre.',
     'Lille', 'CDI', 'Télétravail', 43000, 57000, 0, 'published', 9, 85,
     'Vous rejoignez l’équipe plateforme (trois personnes) qui héberge une vingtaine de services pour nos clients publics, sur un cloud souverain.\n\n'
     'Chantiers en cours : migration vers Kubernetes, mesure de la consommation électrique de chaque service et réduction des temps de build.',
     'Expérience de Linux, Terraform et d’un outil de CI\n'
     'Vous documentez ce que vous faites\n'
     'Sensibilité à l’écoconception\n'
     'Astreinte une semaine sur quatre, rémunérée'),
    (1, 2, 4, 'Brand Designer freelance',
     'Donnez une identité singulière aux prochains projets du studio, du concept à la livraison.',
     'Paris', 'Freelance', 'Télétravail', 48000, 65000, 0, 'published', 10, 73,
     'Mission de quatre mois, environ trois jours par semaine, pour créer l’identité visuelle de deux clients : un festival de musique et une mutuelle étudiante.\n\n'
     'Livrables : logo, typographies, palette, iconographie et un guide de marque utilisable par les équipes des clients.',
     'Portfolio en identité visuelle\n'
     'Vous savez présenter et défendre une proposition\n'
     'Disponibilité à partir du mois prochain'),
    (4, 4, 1, 'Chargé·e de marketing digital',
     'Développez notre présence en ligne et expérimentez de nouvelles idées avec notre équipe marketing.',
     'Nantes', 'Stage', 'Sur site', 12000, 17000, 0, 'published', 11, 58,
     'Stage de six mois. Vous gérez les campagnes d’e-mailing, suivez les performances de la boutique en ligne et proposez des tests (pages produit, offres, contenus).\n\n'
     'Vous êtes accompagné·e par notre responsable acquisition, avec un point chaque semaine.',
     'École de commerce ou formation en marketing digital\n'
     'À l’aise avec les chiffres et Google Analytics\n'
     'Curiosité pour le e-commerce'),
    (1, 1, 4, 'Développeur·se iOS',
     'Rejoignez le studio pour lancer notre première application mobile native pour un réseau de médiathèques.',
     'Paris', 'CDI', 'Hybride', 45000, 58000, 0, 'draft', 1, 0,
     'Annonce en préparation : nous finalisons le périmètre avec le client.\n\n'
     'Application de réservation et de prêt pour un réseau de 30 médiathèques, en Swift et SwiftUI.',
     'Deux ans d’expérience en Swift\n'
     'Une application publiée sur l’App Store'),
    (1, 2, 4, 'Stagiaire UX Research',
     'Six mois pour mener les entretiens et tests utilisateurs de nos projets culture et santé.',
     'Paris', 'Stage', 'Sur site', 12000, 15000, 0, 'closed', 30, 141,
     'Stage de six mois au sein de l’équipe design. Vous préparez et menez les entretiens utilisateurs, organisez les tests et synthétisez les résultats pour l’équipe.',
     'Formation en UX, ergonomie ou sciences sociales\n'
     'Aisance à l’oral'),
]

# Extra applicants who never created a password: they appear in the recruiter view only.
APPLICANTS = [
    ('Sarah Lemoine', 'sarah.lemoine@example.test', '0645127890', 'Développeuse front-end junior', 'Paris'),
    ('Yanis Haddad', 'yanis.haddad@example.test', '0678901234', 'Intégrateur web en reconversion', 'Montreuil'),
    ('Léa Dubois', 'lea.dubois@example.test', '0611457812', 'Designer graphique indépendante', 'Paris'),
    ('Thomas Petit', 'thomas.petit@example.test', '0756231478', 'Directeur artistique', 'Lyon'),
]

# ad, person, message, history [(status, days ago)], private recruiter note
APPLICATIONS = [
    (1, 2, 'Bonjour, je développe depuis trois ans des interfaces React pour une agence, dont un site de billetterie très proche de votre projet. L’accessibilité fait partie de mon quotidien et j’aimerais rejoindre une équipe qui y attache autant d’importance.',
     [('Reçue', 6), ('En cours', 5), ('Entretien', 2)], 'Portfolio solide. Entretien technique jeudi avec Hugo et Nadia.'),
    (3, 2, 'Votre outil de planification m’intéresse beaucoup : j’en utilise un au quotidien et je vois plusieurs choses à améliorer. Je serais ravie d’en discuter avec vous.',
     [('Reçue', 2)], ''),
    (4, 3, 'Passionné par l’analyse de données, je souhaite mettre mes compétences SQL et Python au service de vos équipes. J’ai réalisé mon alternance dans une équipe data d’un e-commerçant.',
     [('Reçue', 5), ('En cours', 3)], ''),
    (1, 5, 'Bonjour, je sors d’un bootcamp et d’un premier CDD de huit mois sur une application React. Je cherche une équipe où progresser sur les tests et l’accessibilité.',
     [('Reçue', 1)], ''),
    (1, 6, 'Intégrateur depuis quatre ans, je me suis formé à React l’an dernier et je l’utilise sur tous mes projets personnels. Vous trouverez mes réalisations sur mon site.',
     [('Reçue', 4), ('En cours', 3)], 'Profil intéressant, un peu juste sur TypeScript. À rappeler.'),
    (11, 7, 'Designer indépendante depuis six ans, j’ai créé l’identité de plusieurs festivals et associations culturelles. Je suis disponible trois jours par semaine dès le mois prochain.',
     [('Reçue', 0)], ''),
    (11, 8, 'Directeur artistique en agence, je souhaite passer en freelance et cette mission correspond exactement à ce que je cherche.',
     [('Reçue', 9), ('En cours', 8), ('Refusée', 6)], 'Pas disponible avant trois mois.'),
    (14, 5, 'Étudiante en master d’ergonomie, je cherche un stage de six mois pour mener des entretiens et des tests utilisateurs.',
     [('Reçue', 33), ('Entretien', 28), ('Acceptée', 24)], 'Arrivée prévue le 2 février.'),
    (2, 3, 'Bonjour, je ne suis pas designer mais j’ai beaucoup travaillé avec des équipes produit. Je postule par curiosité pour le sujet climat et je serais heureux d’échanger.',
     [('Reçue', 3)], ''),
    (9, 2, 'Je m’intéresse au machine learning depuis un an et j’ai suivi plusieurs formations. Je sais que je ne coche pas toutes les cases mais je suis motivée.',
     [('Reçue', 10), ('Refusée', 7)], ''),
]

VIEWS_SAVED = [(2, 2), (2, 6)]  # (person, ad) bookmarks for Camille


def seed(db):
    # Stop if the database already has people, to avoid duplicates.
    if db.execute('SELECT COUNT(*) FROM people').fetchone()[0]:
        return

    db.executemany('INSERT INTO people(name, email, phone, password_hash, role, headline, location, bio, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', [
        ('Admin HireLoop', 'admin@hireloop.test', '0600000000', ADMIN_HASH, 'admin', 'Équipe HireLoop', 'Paris', '', ago(60)),
        ('Camille Martin', 'camille@hireloop.test', '0612345678', CAMILLE_HASH, 'candidate',
         'Développeuse front-end · 3 ans d’expérience', 'Paris',
         'Je construis des interfaces React accessibles depuis trois ans, en agence. Je cherche une équipe produit à taille humaine.', ago(40)),
        ('Alex Bernard', 'alex@hireloop.test', '0698765432', ALEX_HASH, 'candidate',
         'Data analyst junior', 'Lyon', 'Ancien alternant data dans le e-commerce. SQL, Python, Metabase.', ago(35)),
    ])

    db.executemany('INSERT INTO categories(name) VALUES (?)', [
        (n,) for n in ['Développement', 'Design', 'Data & IA', 'Marketing', 'Produit', 'Infrastructure']
    ])
    db.executemany('INSERT INTO companies(name, industry, location, website, description, color) VALUES (?, ?, ?, ?, ?, ?)', COMPANIES)

    # Demo company account, inserted after companies because company_id must exist.
    db.execute('INSERT INTO people(name, email, phone, password_hash, role, company_id, headline, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
               ('Inès Moreau', 'company@test.com', '0145678900', COMPANY_HASH, 'company_admin', 1, 'Responsable recrutement · Studio North', ago(50)))
    db.executemany('INSERT INTO people(name, email, phone, headline, location, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                   [(*a, ago(20)) for a in APPLICANTS])

    for (company, category, contact, title, summary, location, contract, mode, low, high, featured,
         status, days, views, description, requirements) in JOBS:
        created = ago(days, 5)
        db.execute('''INSERT INTO ads(company_id, category_id, contact_id, title, summary, description, requirements,
                location, contract, work_mode, salary_min, salary_max, featured, status, views, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (company, category, contact, title, summary, description, requirements, location, contract, mode,
                    low, high, featured, status, views, created, created))

    people = {r[0]: r for r in db.execute('SELECT id, name, email, phone FROM people')}
    recruiters = {r[0]: r[1] for r in db.execute('SELECT a.id, a.contact_id FROM ads a')}
    for ad, person, message, history, notes in APPLICATIONS:
        _, name, email, phone = people[person]
        status, last_days = history[-1]
        created = ago(history[0][1], 3)
        ident = db.execute('''INSERT INTO applications(ad_id, person_id, message, status, applicant_name, applicant_email,
                applicant_phone, notes, status_updated_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (ad, person, message, status, name, email, phone, notes,
                            ago(last_days, 1) if len(history) > 1 else '', created)).lastrowid
        for index, (step, days) in enumerate(history):
            db.execute('INSERT INTO application_events(application_id, status, actor_id, created_at) VALUES (?, ?, ?, ?)',
                       (ident, step, person if index == 0 else recruiters[ad], created if index == 0 else ago(days, 1)))

    db.executemany('INSERT INTO saved_ads(person_id, ad_id) VALUES (?, ?)', VIEWS_SAVED)
    db.commit()
