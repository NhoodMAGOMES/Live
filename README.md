# LIVE Pulse AO Intelligence

MVP monorepo pour surveiller, normaliser, scorer et qualifier des appels d'offres publics pertinents pour LIVE.

## Stack

- Backend: FastAPI, SQLAlchemy 2, Alembic, Celery, Redis.
- Base: PostgreSQL avec extension pgvector.
- Frontend: Next.js, TypeScript, Tailwind, composants shadcn-like.
- IA: provider OpenAI isolé, Responses API `gpt-5.5`, sortie Pydantic structurée, fallback heuristique sans clé.
- Agents: registre activable, runs historisés, métriques de réussite et tokens consommés.
- Parsing: PDF, DOCX, HTML, XML, JSON, TXT.

## Lancement

```bash
cp .env.example .env
make dev
```

Dans `.env`, utilisez une valeur aléatoire pour `JWT_SECRET`. Renseignez `SEED_ADMIN_PASSWORD` avec un mot de passe unique avant `make seed` pour créer le premier compte administrateur.

Dans un second terminal:

```bash
make migrate
make seed
```

URLs:

- Web: http://127.0.0.1:3000
- API: http://127.0.0.1:8000
- OpenAPI: http://127.0.0.1:8000/docs
- PostgreSQL hôte: `127.0.0.1:55432`
- Redis hôte: `127.0.0.1:56379`

Le compte initial `admin@live.local` est créé uniquement si `SEED_ADMIN_PASSWORD` est renseigné. Relancer `make seed` ne change pas le mot de passe d'un compte existant.

## Commandes

```bash
make dev      # docker compose up --build
make migrate  # alembic upgrade head
make seed     # seed admin, sources, mots-clés
make test     # pytest dans Docker
```

## Connecteurs

- `BOAMP_API`: API officielle DILA/Opendatasoft, endpoint configurable par source.
- `TED_API`: API officielle TED v3, sans clé pour la recherche des avis publiés; recherche française active et mots-clés LIVE par défaut.
- `WEB_WATCH`: mode prudent pour VTscan/Pitchville ou autres pages surveillées; le scraping reste désactivé tant que `scraping_allowed=true` n'est pas configuré après vérification CGU/robots.txt.
- `RSS`, `EMAIL_IMPORT`, `MANUAL_UPLOAD`: architecture prête, MVP orienté import manuel et ingestion configurable.

En développement Docker local, les sources BOAMP et TED seedées contiennent `verify_ssl=false` pour tolérer les environnements avec interception SSL locale. En production, configurez une chaîne CA valide et repassez `verify_ssl=true`.

## Mode sans OpenAI

Si `OPENAI_API_KEY` est absent, l'analyse reste disponible:

- scoring mots-clés + sémantique heuristique;
- rapport français structuré;
- mention explicite: `Analyse IA avancée indisponible : clé LLM manquante`.

Avec une clé OpenAI, le rapport utilise `OPENAI_MODEL=gpt-5.5` par défaut. Vous pouvez ajuster `OPENAI_REASONING_EFFORT` et `OPENAI_TEXT_VERBOSITY` dans `.env`.

Gardez `OPENAI_VERIFY_SSL=true` en production. En développement local avec interception SSL, passez temporairement à `OPENAI_VERIFY_SSL=false`.

## Frontoffice / Backoffice

- `/`: page de connexion.
- `/frontoffice`: cockpit métier avec opportunités, priorités et prochaines actions.
- `/opportunities`: liste et détail des AO récupérés.
- `/backoffice`: accueil administration.
- `/backoffice/platforms`: connexions plateformes, sources AO, runs et erreurs.
- `/backoffice/agents`: activation, planification, activité, taux de réussite et tokens des agents.
- `/backoffice/users`: création, suppression, activation, mot de passe et choix d'accès des profils de connexion.
- `/backoffice/keywords`: familles, mots-clés, poids et synonymes du scoring.

Le frontoffice et le backoffice ont chacun leur propre shell de navigation. Le frontoffice n'affiche que les vues métier; le backoffice s'ouvre sur une URL séparée `/backoffice` et contient uniquement les fonctions d'administration.

Les routes backoffice utilisent le compte connecté côté interface. Un profil `admin` accède au frontoffice et au backoffice. Un profil non-admin accède seulement au frontoffice. La gestion des profils (`/auth/users`) nécessite un utilisateur admin.

## Endpoints principaux

- `POST /auth/login`, `POST /auth/register`, `GET /auth/me`
- `GET/POST/PATCH/DELETE /auth/users` pour l'administration des profils
- `GET/POST/PATCH/DELETE /keyword-categories`
- `GET/POST/PATCH/DELETE /keywords`
- `POST /keywords/import`, `GET /keywords/export`
- `GET/POST/PATCH/DELETE /sources`
- `POST /sources/{id}/run`, `GET /sources/{id}/runs`
- `GET /opportunities`
- `POST /opportunities/import-url`, `POST /opportunities/import-file`
- `POST /opportunities/{id}/analyze`
- `PATCH /opportunities/{id}/status`
- `GET /opportunities/{id}/report`, `GET /opportunities/{id}/export/pdf`
- `GET /agents`, `PATCH /agents/{slug}`, `POST /agents/{slug}/run`
- `GET /reports`, `GET /notifications`, `PATCH /notifications/{id}/read`

## Agents AO

La page web `/backoffice/agents` pilote le cycle AO et les agents spécialisés:

- `verification_cycle`: lance les agents actifs dans l'ordre;
- `source_discovery`: vérifie les sources actives et importe les AO;
- `ao_analyzer`: score les AO entrants et génère le rapport IA;
- `ao_classifier`: classe les AO analysés en GO, WATCH ou NO-GO;
- `alert_dispatcher`: crée les notifications utiles.

Chaque run conserve statut, volumes traités, taux de réussite, modèle, tokens d'entrée/sortie et total tokens. L'agent `ao_analyzer` est inactif par défaut pour éviter une consommation OpenAI automatique.

Chaque agent peut aussi être planifié depuis `/backoffice/agents`: manuel, toutes les X heures, tous les X jours ou toutes les X semaines avec jour/heure. Le worker Celery vérifie les échéances toutes les 5 minutes. Le cycle `verification_cycle` est planifié par défaut tous les jours à 08:00 Europe/Paris.

## Organisation de l'interface

- Frontoffice: `/frontoffice`, `/opportunities`, `/notifications`.
- Backoffice: `/backoffice`, `/backoffice/platforms`, `/backoffice/agents`, `/backoffice/users`, `/backoffice/keywords`.

## Notes d'architecture

Les mots-clés ne sont pas codés dans le moteur de scoring. Le seed charge les familles et termes initiaux en base, puis le moteur lit les `KeywordConfig` actifs au moment de l'analyse.

Chaque score conserve:

- score global;
- score par famille;
- mots-clés et synonymes matchés;
- extraits sources;
- poids appliqués;
- malus;
- confidence score et `human_review_required`.

Le rapport suit les sections demandées: synthèse exécutive, détection, pertinence Pulse LIVE, analyse business, approche recommandée et conclusion.
