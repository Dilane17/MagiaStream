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
playwright install --with-deps chromium
```

## Première exécution

```bash
# Affiche l'aide
magia --help

# Exemple de téléchargement d'un épisode (simulé pour l'instant)
magia download --serie "NomDeSerie" --saison 1 --episode 1 --resolution 1080p
```

## Remarques

- Vérifiez que `aria2c` est installé sur votre système (`aria2c --version`).
- Ne committez jamais vos secrets : utilisez `.env` (non suivi) et votre `.env.example` pour la configuration.

## Phase 1 — Configuration & Utils

Créez un fichier `.env` local (ou copiez `.env.example`) et ajustez les valeurs si nécessaire. Exemple :

```bash
cp .env.example .env
```

Ensuite, vous pouvez afficher la configuration active :

```bash
magia config show
```
