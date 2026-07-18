# MagiaStream

# MagiaStream

MagiaStream est un outil CLI modulaire en Python 3.13+ destiné à automatiser la recherche et le téléchargement d'épisodes d'anime.

## Installation (rapide)

```bash
# Exécuter le script d'installation (Fedora compatible)
./scripts/setup.sh
```

Manuellement :

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Optional: install Playwright browsers (no sudo required inside venv)
playwright install chromium
```

## Première exécution

```bash
# Affiche l'aide (après activation du venv)
magia --help

# Exemple de téléchargement d'un épisode (simulé pour l'instant)
magia download --serie "NomDeSerie" --saison 1 --episode 1 --resolution 1080p
```

## Remarques

- Vérifiez que `aria2c` est installé sur votre système (`aria2c --version`).
- Ne committez jamais vos secrets : utilisez `.env` (non suivi) et votre `.env.example` pour la configuration.

## Phase 1 — Configuration & Utils
Phase 1 — Terminé (2026-07-18)

La configuration centrale, les utilitaires et le CLI de base sont en place.
Avant d'attaquer la Phase 2 (scraping), vérifiez que vous avez bien exécuté :

```bash
# activer l'environnement virtuel
source venv/bin/activate

# installer dépendances Python
pip install -r requirements.txt

# installer les navigateurs Playwright si nécessaire
playwright install chromium

# afficher l'aide du CLI
python -m magia_stream.cli --help
```

Ensuite, vous pouvez afficher la configuration active :

```bash
magia config show
```
