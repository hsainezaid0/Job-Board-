# Validation et guide de soutenance

## Tests automatisés

Commande : `python -m unittest discover -s tests -v`

Résultat : **6 scénarios réussis**, sur un serveur HTTP réel et une base SQLite temporaire.

| Scénario | Vérifications |
|---|---|
| Catalogue public | 12 offres initiales, filtres, recherche, résultats vides, tri, pagination, détail et offres par entreprise, erreurs 400/404 |
| Permissions anonymes | Création/modification/suppression interdites sur les cinq ressources, données personnelles protégées |
| Compte candidat | Inscription, session, profil, prévention d'élévation de privilège, mot de passe, candidature, doublon, suivi et déconnexion |
| Candidature anonyme | Enregistrement, validation des champs, message trop court, compte existant, doublons et offre inexistante |
| Administration | CRUD des cinq tables, PUT et PATCH, relations, salaires, contraintes, suppression bloquée, protection du dernier administrateur |
| Requêtes invalides | Injection SQL traitée comme texte, refus d'origine externe, routes inconnues, inscription incomplète |

Les tests ne dépendent pas du serveur de démonstration ouvert sur 8000/8001. Ils ne touchent pas la base de développement.

## Vérifications dans le navigateur

- Accueil et identité visuelle contrôlés sur ordinateur.
- Recherche « React » : une seule offre retournée, mise à jour sans rechargement.
- Bouton « En savoir plus » : affichage intégré du détail complet, aucun popup.
- Connexion admin : redirection vers le tableau de bord et accès aux cinq onglets.
- Formulaire d'ajout d'offre : champs et listes de relations correctement affichés.
- Déconnexion : disparition des liens privés et retour au catalogue.
- Connexion candidat : redirection vers les offres ; le formulaire utilise le nom et l'e-mail du profil sans ressaisie.
- Envoi d'une candidature fictive depuis le navigateur : confirmation de l'enregistrement et lien vers le suivi.
- Responsive : contrôle de la mise en page à une largeur mobile ; retour à la taille initiale après le test.

## Parcours de démonstration (5 minutes)

1. Démarrer `python server.py` et ouvrir `http://127.0.0.1:8000`.
2. Rechercher « React », puis effacer les filtres. Choisir un contrat et une ville ; changer le tri.
3. Cliquer sur **En savoir plus** : montrer le détail sans rechargement et les informations de salaire, contrat, rythme et lieu.
4. Cliquer sur **Postuler**, saisir des informations fictives et un message d'au moins 20 caractères. Montrer la confirmation d'enregistrement.
5. Créer un compte avec une autre adresse fictive, ou se connecter avec `camille@hireloop.test` / `Camille2026!`. Postuler à une offre sans ressaisir nom/e-mail/téléphone ; retrouver le statut dans **Mes candidatures**.
6. Modifier le nom ou téléphone dans **Mon compte**, puis se déconnecter.
7. Se connecter avec `admin@hireloop.test` / `Admin2026!` ; montrer la redirection vers **Administration**.
8. Dans **Candidatures**, ouvrir un enregistrement et passer son statut à **Entretien**.
9. Créer une catégorie et une entreprise fictives, puis une offre reliée à ces données. Montrer les modifications dans le catalogue.
10. Supprimer l'offre de test avec la confirmation intégrée, puis l'entreprise et la catégorie. Montrer la pagination.
11. Lancer les tests et expliquer les relations SQL à l'aide de `schema.sql` et des trois requêtes de `docs/queries.sql`.

## Correspondance avec le sujet

| Exigence | Implémentation |
|---|---|
| Base SQL et remplissage backend | `schema.sql`, `seed.py`, initialisation de `server.py` |
| Table offres, entreprises, personnes, candidatures | `ads`, `companies`, `people`, `applications` + catégories |
| API REST et bons verbes/statuts | Routes `/api`, GET/POST/PUT/PATCH/DELETE, statuts documentés |
| Toutes les données dynamiques via API | `fetch()` dans `public/app.js` |
| Titre, résumé, learn more, apply | Cartes de la page `#jobs` |
| Détail dynamique sans popup | Vue `#job/:id`, rendu DOM |
| Formulaire et conservation candidature | Section intégrée, POST puis transaction SQL |
| Connexion, création et modification compte | `#login`, `#register`, `#account` |
| Candidat identifié sans ressaisie | Session serveur, identité récupérée par le backend |
| Redirection selon rôle | Connexion → `#admin` ou `#jobs` |
| Administration CRUD et accès restreint | `#admin` + vérification serveur pour toutes les écritures |
| Pagination | 6 offres/page, 8 lignes/page en administration |
| README et tests locaux | `README.md`, `tests/test_api.py` |
| Requêtes du bootstrap | `docs/queries.sql` |

## Limites explicites

Le serveur est conçu pour l'évaluation locale. Pas d'envoi d'e-mail, de collecte d'offres externes, de téléversement de CV ni de récupération de compte. Les messages sont conservés et lus dans l'administration. Les sites d'entreprises utilisent `example.com` car les données de démonstration sont fictives.
