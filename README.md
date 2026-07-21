# MagiaStream

MagiaStream est un orchestrateur de téléchargement CLI avancé en Python 3.14+, spécialement conçu pour rechercher, scrapper et télécharger des séries d'animes de manière robuste et interactive.

## ✨ Fonctionnalités Principales

- **Mode Interactif (Wizard)** : Plus besoin de taper des commandes longues ! L'interface interactive vous guide pas-à-pas (Recherche, Choix de la saison, Résolution, etc.).
- **Recherche AJAX Dynamique** : Le scraper Playwright reproduit un comportement humain pour exploiter la barre de recherche (support de l'autocomplétion) et esquiver les limitations anti-bot.
- **Téléchargement HLS Ultra-Résilient** : Construit au-dessus de `aria2c` et `ffmpeg`, le moteur de téléchargement gère parfaitement les connexions instables :
  - **Reprise automatique** en cas de coupure (Code 5).
  - **Barre de progression en direct** (grâce à `rich`).
  - **Boucle auto-réparatrice** infinie qui s'acharne jusqu'à ce que tous les segments soient récupérés sans jamais recommencer à zéro.
- **Support Stealth & Proxies** : Intégration de serveurs Proxy, Playwright Stealth et manipulation d'User-Agents pour passer sous les radars des CDNs capricieux.

## 🚀 Installation

### 🌍 Compatibilité (Multiplateforme)

MagiaStream est 100% compatible avec **Windows, macOS et toutes les distributions Linux**.
Les seules exigences système à installer via votre gestionnaire de paquets (`apt`, `brew`, `winget`, etc.) sont :

- Python 3.10 ou supérieur
- `aria2c` (moteur de téléchargement ultra-rapide)
- `ffmpeg` (pour la fusion finale des vidéos)

### Installation (Méthode Officielle PyPI)

`pipx` est l'outil standard pour installer des applications CLI Python de manière globale.

```bash
# 1. Installer pipx si vous ne l'avez pas déjà
python -m pip install --user pipx
python -m pipx ensurepath

# 2. Installer MagiaStream officiellement depuis PyPI
pipx install magiastream

# 3. Finaliser l'installation (télécharge le navigateur et vérifie les dépendances)
magia setup
```

_(Note : Remplacez `ton-profil/MagiaStream.git` par l'URL réelle de votre dépôt Github)._

### 🔄 Mise à jour Automatique

Mettre à jour MagiaStream vers la toute dernière version se fait en une seule commande, peu importe la méthode d'installation choisie :

```bash
magia update
```

### Méthode 2 : Installation pour le Développement (Local)

Si vous souhaitez modifier le code ou contribuer au projet :

```bash
# 1. Cloner et préparer l'environnement virtuel
git clone https://github.com/ton-profil/MagiaStream.git
cd MagiaStream
python -m venv venv
source venv/bin/activate

# 2. Installer le package et ses dépendances
pip install -e .

# 3. Installer le navigateur Playwright
playwright install chromium
```

## 🎮 Utilisation

La manière la plus simple et la plus recommandée d'utiliser MagiaStream est le **mode interactif**. Tapez simplement :

```bash
magia
```

_L'assistant s'ouvrira, vous demandera quelle série chercher, affichera les vrais résultats du menu déroulant (VF/VOSTFR) via les touches fléchées, et lancera le téléchargement._

### Mode CLI Classique

Si vous préférez écrire une commande complète d'un trait (pour des scripts ou des batchs) :

```bash
# Télécharger toute la saison 1 en 720p
magia download --serie "wistoria-wand-and-sword-vf" --saison 1 --resolution 720p --all

# Télécharger uniquement l'épisode 3
magia download --serie "wistoria-wand-and-sword-vf" --saison 1 --episode 3 --resolution 1080p

# Télécharger de l'épisode 5 à 12
magia download --serie "wistoria-wand-and-sword-vf" --saison 1 --range "5-12"
```

## ⚙️ Configuration

MagiaStream utilise un fichier `.env` pour stocker sa configuration.
Copiez le fichier d'exemple :

```bash
cp .env.example .env
```

Paramètres importants :

- `PROXY_URL` : Un proxy pour contourner d'éventuels ban d'IP.
- `TIMEOUT_SECONDS` : Temps d'attente maximum pour les requêtes web.
- `HEADLESS` : Mettez `False` pour voir le navigateur fantôme travailler en arrière-plan.

## 🛠️ À propos du moteur de téléchargement

Le gestionnaire de téléchargement a été optimisé pour les **réseaux très instables**.
Plutôt que d'abandonner lorsqu'un CDN étrangle la connexion ou qu'une micro-coupure survient, MagiaStream isole les segments échoués et relance automatiquement `aria2c` en boucle toutes les 5 secondes jusqu'au succès total.

## ⚠️ Avertissement Légal (Disclaimer)

**MagiaStream** a été développé uniquement à des fins **éducatives** et de démonstration technique (automatisation web, web-scraping, et gestion de flux réseaux avec Python).

L'auteur de cet outil n'héberge aucun contenu protégé et n'encourage en aucun cas le téléchargement illégal ou le piratage de contenus protégés par le droit d'auteur.
Les utilisateurs sont seuls responsables de l'usage qu'ils font de cet outil. Assurez-vous d'avoir les droits nécessaires ou l'autorisation des plateformes avant de télécharger une vidéo. Cet outil est fourni "tel quel", sans aucune garantie.
