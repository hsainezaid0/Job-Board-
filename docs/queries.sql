-- Exemples demandés par le bootstrap. À exécuter sur data/hireloop.sqlite3.

-- 1. Nombre d'offres par entreprise, y compris celles n'ayant aucune offre.
SELECT c.id, c.name, COUNT(a.id) AS advertisement_count
FROM companies c
LEFT JOIN ads a ON a.company_id = c.id
GROUP BY c.id, c.name
ORDER BY advertisement_count DESC, c.name;

-- 2. Offre(s) ayant reçu le plus de candidatures (gestion des ex aequo).
WITH counts AS (
  SELECT a.id, a.title, COUNT(x.id) AS application_count
  FROM ads a LEFT JOIN applications x ON x.ad_id = a.id
  GROUP BY a.id, a.title
)
SELECT * FROM counts
WHERE application_count = (SELECT MAX(application_count) FROM counts);

-- 3. Candidats à l'offre #1, avec message, date et statut.
SELECT p.name, p.email, p.phone, a.title, x.message, x.created_at, x.status
FROM applications x
JOIN people p ON p.id = x.person_id
JOIN ads a ON a.id = x.ad_id
WHERE a.id = 1
ORDER BY x.created_at DESC;
