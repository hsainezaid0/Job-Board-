"""Données fictives insérées par le backend, uniquement dans une base vide."""

def seed(db):
    if db.execute('SELECT COUNT(*) FROM people').fetchone()[0]:
        return
    db.executemany('INSERT INTO people(name,email,phone,password_hash,role) VALUES(?,?,?,?,?)', [
        ('Admin HireLoop','admin@hireloop.test','0600000000','8b9438be42dab3fd841eec764eb9e58d$ca8fe3f0e9581b8d37d1dc374d4580768e40edfe4a33cb7e6bb088128321dc29','admin'),
        ('Camille Martin','camille@hireloop.test','0612345678','70e992c3810ab9a037764a4c1ab0444b$714428043750175796f40735aca0219c63556f71d3161556f89916c748922af6','candidate'),
        ('Alex Bernard','alex@hireloop.test','0698765432','bfa33982df212a602371d210ad7f5364$908d4a50e72685fcf21a394d9f7fa1a41736a96dc142afa249d63d092c8adf57','candidate'),
    ])
    db.executemany('INSERT INTO categories(name) VALUES(?)', [(n,) for n in ['Développement','Design','Data & IA','Marketing','Produit','Infrastructure']])
    db.executemany('INSERT INTO companies(name,industry,location,website,description,color) VALUES(?,?,?,?,?,?)', [
        ('Studio North','Design & technologie','Paris','https://example.com','Un studio indépendant qui transforme les idées ambitieuses en expériences numériques utiles. Petite équipe, grande attention aux détails.','#7253a0'),
        ('Bloom','Climate tech','Lyon','https://example.com','Nous aidons les entreprises à mesurer et réduire leur empreinte environnementale. Une technologie concrète au service de la transition.','#43775a'),
        ('Orbit','Logiciel SaaS','Bordeaux','https://example.com','Des outils collaboratifs pour les équipes qui construisent demain. Autonomie, transparence et apprentissage continu.','#4077a2'),
        ('Maison Atlas','Commerce & lifestyle','Nantes','https://example.com','Une maison de marques engagées, à la rencontre de la création, du commerce et des nouveaux usages.','#b36d4c'),
        ('Linear Labs','Intelligence artificielle','Paris','https://example.com','Un laboratoire produit qui rend les données accessibles et les modèles utiles, avec une culture de recherche ouverte.','#525aa4'),
        ('Collectif','Services numériques','Lille','https://example.com','Un collectif de spécialistes qui conçoit des services numériques accessibles, responsables et durables.','#92742e'),
    ])
    jobs = [
        (1,1,'Développeur·se Front-end React','Créez des expériences web soignées, rapides et accessibles au sein d’un studio qui aime les beaux produits.','Paris','CDI','Hybride',42000,55000,1),
        (2,2,'Product Designer','Imaginez des interfaces qui rendent la transition écologique plus simple, un écran à la fois.','Lyon','CDI','Hybride',40000,52000,1),
        (3,1,'Développeur·se Full Stack','Construisez les prochaines fonctionnalités de notre plateforme collaborative avec une équipe passionnée.','Bordeaux','CDI','Télétravail',45000,60000,0),
        (5,3,'Data Analyst Junior','Donnez du sens aux données et aidez nos équipes à prendre des décisions éclairées.','Paris','CDI','Hybride',38000,46000,1),
        (4,4,'Assistant·e Communication','Faites rayonner des marques engagées à travers des contenus créatifs et des campagnes qui ont du sens.','Nantes','Alternance','Sur site',14000,19000,0),
        (2,1,'Développeur·se Back-end Python','Concevez des API fiables pour accélérer la mesure et la réduction de l’empreinte carbone.','Lyon','CDI','Télétravail',44000,58000,0),
        (6,2,'UX Designer','Allez à la rencontre des utilisateurs et transformez leurs besoins en parcours intuitifs.','Lille','Stage','Hybride',12000,18000,0),
        (3,5,'Product Manager','Accompagnez une équipe pluridisciplinaire de la découverte au lancement de nouveaux services.','Bordeaux','CDD','Hybride',46000,62000,0),
        (5,3,'Machine Learning Engineer','Mettez des modèles en production et contribuez à une IA robuste, mesurable et responsable.','Paris','CDI','Hybride',50000,70000,0),
        (6,6,'Ingénieur·e DevOps','Améliorez nos pipelines et faites grandir une infrastructure fiable et sobre.','Lille','CDI','Télétravail',43000,57000,0),
        (1,2,'Brand Designer freelance','Donnez une identité singulière aux prochains projets du studio, du concept à la livraison.','Paris','Freelance','Télétravail',48000,65000,0),
        (4,4,'Chargé·e de marketing digital','Développez notre présence en ligne et expérimentez de nouvelles idées avec notre équipe marketing.','Nantes','Stage','Sur site',12000,17000,0),
    ]
    for i, (company,category,title,summary,location,contract,mode,low,high,featured) in enumerate(jobs):
        description = summary + '\n\nAu quotidien, vous participerez à la conception et à l’amélioration de nos produits. Vous travaillerez avec les équipes design, produit et technique, partagerez vos idées et mesurerez l’impact de vos réalisations.\n\nNous proposons un accompagnement à votre arrivée, du temps pour apprendre, une organisation flexible et une équipe à taille humaine. Le processus : un premier échange, une rencontre avec l’équipe et un retour personnalisé.'
        requirements = 'Vous aimez apprendre et travailler en équipe.\nVous savez expliquer vos choix et écouter les autres.\nUne première expérience ou un projet personnel dans le domaine est apprécié.\nNous accueillons les parcours variés et les candidatures de personnes en reconversion.'
        db.execute('INSERT INTO ads(company_id,category_id,contact_id,title,summary,description,requirements,location,contract,work_mode,salary_min,salary_max,featured,created_at) VALUES(?,?,1,?,?,?,?,?,?,?,?,?,?,strftime(\'%Y-%m-%dT%H:%M:%SZ\',\'now\',?))',
                   (company,category,title,summary,description,requirements,location,contract,mode,low,high,featured,f'-{i} days'))
    db.executemany('INSERT INTO applications(ad_id,person_id,message,status) VALUES(?,?,?,?)', [
        (1,2,'Bonjour, mon expérience React et mon intérêt pour le design correspondent à votre projet. Je serais ravie d’échanger avec votre équipe.','Entretien'),
        (3,2,'Votre produit collaboratif m’intéresse. Je souhaite contribuer à son développement et découvrir votre équipe.','Reçue'),
        (4,3,'Passionné par l’analyse de données, je souhaite mettre mes compétences SQL et Python au service de vos projets.','En cours'),
    ])
    db.commit()
