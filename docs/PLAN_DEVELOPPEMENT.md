# PLAN_DEVELOPPEMENT — MagiaStream

Document pragmatique et phasé pour achever et produire une v1 de `MagiaStream`.

---

## Résumé de l'état actuel (audit rapide)

- `voiranime_downloader/` : package principal
  - `__init__.py` : contient `__version__ = "0.1.0"`.
  - `cli.py` : CLI Typer minimal avec commande `download` et options `--serie`, `--saison`, `--episode`, `--resolution`. Initialise logging via `setup_logging()` puis orchestre `Scraper` et `Downloader`.
  - `scraper.py` : classe `Scraper` dataclass avec `search_episode()` non implémentée (lève `ScraperError`).
  - `downloader.py` : classe `Downloader` dataclass qui appelle le scraper, construit un nom de fichier et retourne un chemin simulé (pas d'appel réel à aria2c).
  - `config.py` : dataclass `Config` avec `BASE_URL`, `output_dir`, `temp_dir`, `user_agent`, `timeout_seconds`.
  - `utils.py` : `setup_logging()` et `ensure_directory()` simples.
  - `exceptions.py` : exceptions métier (`MagiaStreamError`, `ScraperError`, `DownloadError`).

- `tests/` : test unitaire initial basé sur `unittest` (`tests/test_scraper.py`) qui vérifie que `Scraper.search_episode` lève `ScraperError`.
- `requirements.txt` : liste basique (`playwright`, `typer[all]`, `rich`, `python-dotenv`, `tqdm`).
- `.gitignore`, `README.md`, `pyproject.toml` : présents ; `pyproject.toml` déclare le script `voiranime = "voiranime_downloader.cli:main"`.

### Résumé : ce qui fonctionne

- Structure initiale cohérente ; tests unitaires basiques passent.
- Typage moderne (annotations), utilisation de Typer et Rich.

### Manquants / limites immédiates

- `Scraper` non implémenté (aucune interaction Playwright / HTTP).
- Aucun gestionnaire d'authentification, de parsing .m3u8, ni de gestion d'iframes/anti-bot.
- `Downloader` ne lance pas `aria2c` ni la gestion de reprise / multi-connexion.
- Pas de parsing `.env` ni configuration centralisée via `python-dotenv`.
- Logging basique ; pas de rotation, pas de niveau configuré via fichier/env.
- Aucun test d'intégration, pas de CI, pas de packaging final (wheel, tests automatisés).
- `pyproject.toml` a `dependencies = []` (les dépendances ne sont pas inscrites dans `pyproject`), à corriger si on veut publier.
- README mentionne `voiranime` mais le nom du package est `MagiaStream` — cohérence mineure à ajuster.

---

## Observations techniques et recommandations rapides

- Garder la séparation `Scraper` (récupération) vs `Downloader` (transfert) vs CLI.
- Prévoir un composant `http`/`browser` qui encapsule Playwright, gestion des headers, proxies et retry.
- Stocker la configuration en priorité dans `.env` + `Config` qui hydrate depuis l'environnement.
- Utiliser `subprocess.run` ou `asyncio.create_subprocess_exec` pour appeler `aria2c` et capter la sortie (progression). Préférer `aria2c` en mode `--enable-rpc`/`--input-file` pour listes longues.
- Ajouter des métriques/logs structurés (JSON) pour faciliter debug en production.

---

## Actions réalisées

- Lecture et vérification des fichiers listés ci-dessus.
- Tests unitaires basiques exécutés : OK.

---

# Plan de développement par phases

Chaque phase liste tâches, priorités et edge-cases à anticiper. Dépendances = phases précédentes.

### Phase 0 — Finalisation setup (priorité: critique) — TERMINÉ

Objectif : rendre le projet exécutable localement, reproductible et versionnable.
Tâches :

- Initialiser `venv` et documenter la commande d'activation dans `README.md`.
- Mettre à jour `requirements.txt` et `pyproject.toml` (répliquer deps dans `pyproject` si publication prévue).
- `git init` si non fait, ajouter `LICENSE` (MIT par défaut) et premiers commits.
- Ajouter `.env.example` avec variables : `BASE_URL`, `ARIA2C_PATH`, `OUTPUT_DIR`, `TIMEOUT`, `PLAYWRIGHT_BROWSERS`.
- Ajouter script simple `scripts/setup.sh` (optionnel) pour apt/dnf deps: `aria2`, `libnss3`, `libatk1.0`, etc. (Playwright deps).
- Vérifier `playwright install --with-deps chromium` dans README.

Edge-cases : utilisateur sans `aria2c`, sans droits root, version Python <3.13.
Dépendances: none.

### Phase 1 — Configuration & Utils (priorité: haute) — TERMINÉ (2026-07-18)

Note: Phase 1 est marquée comme terminée. Le projet a subi des corrections de packaging, nettoyage legacy et ajout de tests unitaires de base. Ready for Phase 2 after fixes.

Objectif : robustifier config et utilitaires transverses.
Tâches :

- Charger `.env` via `python-dotenv` dans `Config` (méthode de classe `from_env()` et validation zod-like simple).
- Améliorer `utils.setup_logging()` : support niveau via env, fichier `LOG_LEVEL`, `RotatingFileHandler` optionnel, JSON formatter optionnel.
- Ajouter utilitaires `retry` (backoff exponentiel) configurable (utiliser `tenacity` si acceptable, sinon implémenter petit wrapper).
- Installer gestion d'horodatage/format uniforme et gestion `--verbose` dans CLI.
- Ajouter utilitaires pour gestion de chemins (safe filename sanitization) et housekeeping du `temp_dir`.

Edge-cases : chemins non écriturables, quotas disque, collisions de noms de fichiers.
Dépendances: Phase 0.

### Phase 2 — Scraper core (priorité: critique)

Objectif : implémenter le cœur du scraping robuste avec Playwright.
Tâches :

- Créer module `browser.py` encapsulant Playwright (sync ou async — choisir async si besoin de scalabilité).
- Créer module `browser.py` encapsulant Playwright (sync ou async — choisir async si besoin de scalabilité).
- Sub-tâches découvertes lors de l'audit :
  - Ajouter une couche `network_monitor` pour intercepter requêtes et extraire `.m3u8`/tokens.
  - Implémenter une stratégie de backoff et gestion des challenges JS (rejouer scripts dans le contexte Playwright).
  - Écrire tests unitaires pour `Scraper` en mockant Playwright (utiliser pytest + pytest-asyncio + respx/vcrpy).
- Patterns : session persistante, reuse browser contexts, options headless, user-agent, proxy support.
- Techniques anti-bot : randomisation d'user-agent, injection de waits/stall, utilisation de `stealth` script si nécessaire.
- Navigation sur `https://voir-anime.to` : découvrir structure HTML, pages séries, pages épisodes.
- Implémenter `Scraper.search_episode()` :
  - recherche série par nom (fuzzy matching), sélection de saison, liste d'épisodes ;
  - normaliser les titres et retourner métadonnées : titre, saison, épisode, page_url, iframe_url(s), timestamp, available_resolutions.
- Persistance légère des métadonnées en cache (sqlite ou fichier JSON) pour réduire requests.

Edge-cases : Cloudflare/anti-bot (JS challenge), pages dynamiques chargées via XHR, pagination infinie, redirections.
Dépendances: Phase 1.

### Phase 3 — Extraction des flux vidéo (priorité: élevée)

Objectif : extraire les URLs de flux (m3u8 / mp4) depuis pages/iframes et gérer anti-bot.
Tâches :

- Gérer les iframes : naviguer dans l'iframe (Playwright) et inspecter DOM/requests réseau.
- Intercepter requêtes réseau (route/response) pour localiser `.m3u8` ou `.mp4` et tokens temporaires.
- Parser les playlists `.m3u8` (variant playlists) pour choisir la piste correspondant à la résolution désirée.
- Résoudre signatures/jetons si fournis via JS (exécuter le script JS dans le contexte du navigateur si nécessaire).
- Enumérer cas: flux HLS chiffré (AES-128) — si chiffré, détecter et exposer message d'erreur ou tenter récupération des clés si accessible.

Edge-cases : liens temporaires (signed URLs), fragments chiffrés, tokens expirants, CORS, redirections 302.
Dépendances: Phase 2.

### Phase 4 — Downloader (priorité: élevée)

Objectif : fiabiliser le téléchargement via `aria2c` avec reprise et multi-connexions.
Tâches :

- Implémenter wrapper `downloader/aria2_wrapper.py` : construction de la commande, options par défaut `-x 16 -s 16`, contrôle timeout, retry.
- Support pour `.m3u8` : si flux HLS, possibilité 1) utiliser `ffmpeg` pour downloader et remuxer; 2) utiliser `aria2c` sur segments quand possible; documenter les deux approches.
- Progression : parser la sortie `aria2c` et exposer progression en % vers `rich.progress`.
- Reprise : utiliser option `--continue`/`--allow-overwrite=false` et garder métadonnées `.aria2`/`.tmp` en `temp_dir`.
- Organisation répertoires : `{output}/{serie}/Saison {saison}/{serie}.s{s:02d}e{e:02d}.{resolution}.mp4`.

Edge-cases : quotas de connexion, serveurs limitant shards, fichiers incomplets, DRM/HLS chiffré.
Dépendances: Phase 3, Phase 1.

### Phase 5 — CLI avancée (priorité: moyenne)

Objectif : rendre le CLI complet et ergonomique pour workflows courants.
Tâches :

- Étendre `cli.py` : options `--range` (ex: `1-12`), `--all` pour télécharger toute une saison, `--parallel` pour télécharger plusieurs séries/épisodes.
- Ajouter commandes : `list-episodes`, `search`, `resume`, `cleanup`, `config show`.
- Intégrer `rich` pour sorties colorées et `prompt` pour confirmation.
- Support d'un fichier d'entrée (YAML/JSON) pour batch jobs.

Edge-cases : gestion des interruptions (SIGINT), verrouillage de dossier pour éviter écritures concurrentes.
Dépendances: Phase 4.

### Phase 6 — Gestion erreurs, tests, packaging (priorité: haute)

Objectif : durcir la solution et rendre le build repoducible.
Tâches :

- Tests : ajouter tests unitaires pour `utils`, mocks pour `browser`/Playwright, tests d'intégration limités (optionnels) via fixtures (vcrpy/ad-hoc mocking).
- CI : config GitHub Actions — lint (ruff/flake8), type-check (mypy), tests, build wheel, publish on tag.
- Gestion erreurs : erreurs sûres remontées vers le CLI, logs structurés et codes de sortie cohérents.
- Packaging : finaliser `pyproject.toml` (mettre `dependencies`), build `wheel`, ajouter `entry_points` si nécessaire.

Edge-cases : secrets exposés dans logs, tests flakys à cause de JS/temps réseau.
Dépendances: Phases 0–5.

### Phase 7 — Features futures (priorité: basse)

Objectif : roadmap pour évolutions non bloquantes.
Tâches :

- Multi-séries / file d'attente (queue) et persistence (sqlite/redis).
- Notifications (desktop, email, webhook) à la fin du job.
- Web UI léger pour orchestrer les téléchargements (FastAPI + UI minimal).
- Support multi-sources (autres sites) via adaptateurs `site_adapter`.
- Téléchargement distribué (worker pattern).

Edge-cases : sécurité des webhooks, scalabilité, licences légales.

---

## Dépendances entre phases (rappel synthétique)

- Phase 0 → Phase 1 (config & utils nécessaires pour tout le reste)
- Phase 1 → Phase 2 (scraper s'appuie sur config & utils)
- Phase 2 → Phase 3 (extraction flux dépend du navigateur)
- Phase 3 → Phase 4 (downloader a besoin des URLs de flux)
- Phase 4 → Phase 5 (CLI avancée orchestre le downloader)
- Phase 5 → Phase 6 (tests/packaging après fonctionnalités)

---

## Checklist opérationnelle et KPI de succès

- Script d'installation fonctionnel (`venv`, `pip install`, `playwright install`): success
- `Scraper.search_episode` retourne métadonnées pour 80% des séries ciblées (mesure initiale)
- Téléchargement `aria2c` stable pour fichiers >100MB avec reprise
- Tests unitaires couvrant >60% du core non-IO, CI green

---

## Annexes / notes pratiques

- Respect légal : vérifier les CGU des sources et éviter redistribution non autorisée.
- Sécurité : ne pas committer `.env` ni clés API; utiliser `.env.example`.
- Playwright stealth : ne pas utiliser de librairies propriétaires risquant des licences non compatibles.

---

Fin du plan.
