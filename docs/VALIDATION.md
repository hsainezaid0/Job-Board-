# Validation et guide de soutenance

## Tests automatisés

Commandes :

```sh
python -m unittest discover -s tests -v
node --test tests/test_i18n.cjs
```

Résultat : **22 tests API réussis** sur un serveur HTTP réel et une base SQLite temporaire, et **6 tests de traduction réussis**.

| Scénario | Vérifications |
|---|---|
| Catalogue public | Offres publiées uniquement, filtres (dont salaire minimum), recherche sur titre, résumé, entreprise et domaine, tri, pagination, détail, offres similaires, annuaire des entreprises |
| Cycle de vie d’une offre | Brouillon invisible du public mais prévisualisable par son équipe, offre fermée visible sans candidature possible, publication datée du jour, compteur de vues hors recruteurs |
| Permissions | Anonyme, candidat, recruteur et administrateur sur les cinq ressources ; isolement entre entreprises, y compris par accès direct à un identifiant |
| Compte candidat | Inscription, profil enrichi, mot de passe, suppression du compte, offres sauvegardées, retrait d’une candidature sans réponse |
| Suivi des candidatures | Historique des statuts, notes privées jamais renvoyées au candidat, indicateur « Nouveau » et marquage comme lu |
| Administration | CRUD des cinq tables, recherche, filtres et compteurs par statut, tableau de bord, export CSV limité au périmètre du recruteur |
| Protection contre les abus | Limites de connexion, d’inscription et de candidature, fermeture des autres sessions après un changement de mot de passe |
| Requêtes invalides | Injection SQL traitée comme texte, origine externe refusée (même sans en-tête Host), routes inconnues, champs trop longs, énumérations et téléphone invalides |
| Migration | Une base de l’ancienne version est mise à niveau sans perte de données ni de relations |

Les tests ne dépendent pas du serveur de démonstration et ne touchent pas la base de développement.

## Vérifications dans le navigateur

Contrôlées dans Edge (sans interface) sur ordinateur (1366 px) et sur mobile (390 px), en français et en anglais, sans erreur dans la console ni défilement horizontal :

- Accueil : recherche, puces de domaines, filtres (panneau coulissant sur mobile), filtres actifs supprimables, pagination, sauvegarde d’une offre.
- Fiche d’offre : description, profil recherché en liste, encadré « En bref », entreprise, offres similaires, candidature avec compteur de caractères puis confirmation.
- Espace candidat : candidatures avec étapes et historique, offres sauvegardées, profil, sécurité, menu du compte.
- Espace recruteur : tableau de bord, publication d’un brouillon, création d’une offre depuis le panneau latéral, changement de statut depuis la liste, fiche candidature avec notes privées, export CSV, profil de l’entreprise avec aperçu.
- Administration : entreprises, catégories, utilisateurs.

## Parcours de démonstration (5 minutes)

1. Lancer `python server.py` et ouvrir `http://127.0.0.1:8000`.
2. Rechercher « React », puis cliquer sur une puce de domaine et choisir un contrat. Montrer l’adresse qui conserve les filtres, puis « Tout effacer ».
3. Ouvrir une offre : salaire, contrat, mode de travail, entreprise et offres similaires. Cliquer sur le signet sans être connecté : invitation à se connecter.
4. Page de connexion : « Utiliser » sur le compte Candidat (Camille). Le badge rouge signale deux candidatures mises à jour ; montrer les étapes, l’historique et le retrait possible.
5. Postuler à une offre : le nom, l’e-mail et le téléphone viennent du profil, le message est enregistré en brouillon pendant la saisie.
6. Se déconnecter, puis « Utiliser » sur le compte Recruteur (Inès, Studio North). Tableau de bord : candidatures à traiter, graphique, offres les plus suivies.
7. Offres : publier le brouillon « Développeur·se iOS », puis créer une offre et la garder en brouillon. Montrer l’aperçu depuis la page publique.
8. Candidatures : passer une candidature « Reçue » en « Entretien », ajouter une note privée, exporter en CSV.
9. Se reconnecter en Candidat (Camille) : le statut a changé, la note privée n’apparaît pas.
10. Se connecter en Administrateur : utilisateurs filtrés par rôle, création d’un recruteur rattaché à une entreprise, catégories.
11. Basculer en anglais (FR / EN) sur n’importe quel écran : la saisie en cours est conservée.
12. Lancer les tests et expliquer les relations SQL à l’aide de `schema.sql` et des trois requêtes de `docs/queries.sql`.

## Correspondance avec le sujet

| Exigence | Implémentation |
|---|---|
| Base SQL et remplissage backend | `schema.sql`, `seed.py`, initialisation et migrations dans `server.py` |
| Tables offres, entreprises, personnes, candidatures | `ads`, `companies`, `people`, `applications`, plus `categories`, `application_events`, `saved_ads` |
| API REST, bons verbes et statuts | Routes `/api`, GET/POST/PUT/PATCH/DELETE, statuts documentés dans le README |
| Données dynamiques via l’API | `fetch()` dans `public/js/core.js` |
| Titre, résumé, « en savoir plus », « postuler » | Liste des offres et fiche `#job/:id` |
| Détail dynamique sans popup | Vue `#job/:id`, rendu DOM |
| Formulaire et conservation des candidatures | Formulaire intégré, transaction SQL, historique des statuts |
| Connexion, création et modification de compte | `#login`, `#register`, `#account`, `#security` |
| Candidat identifié sans ressaisie | Session serveur, coordonnées reprises par le backend |
| Redirection selon le rôle | Connexion → `#admin` (recruteurs, administrateurs) ou retour à l’offre / `#jobs` |
| Administration CRUD et accès restreint | `#admin/...` et vérification serveur de chaque écriture |
| Pagination | 8 offres par page, 10 à 12 lignes par page en administration |
| README et tests locaux | `README.md`, `tests/` |
| Requêtes du bootstrap | `docs/queries.sql` |

## Limites explicites

Le serveur est conçu pour l’évaluation locale. Pas d’envoi d’e-mail, de vérification d’adresse, de récupération de mot de passe, de téléversement de CV ni de collecte d’offres externes. Les sites des entreprises pointent vers `example.com` car les données de démonstration sont fictives.
