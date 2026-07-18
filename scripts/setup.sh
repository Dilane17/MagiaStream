#!/usr/bin/env bash
# Script d'installation minimal pour Fedora
set -euo pipefail

echo "==> Installation des dépendances système (Fedora)"
if command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y aria2 libX11 libXcomposite libXdamage libXrandr libXcursor alsa-lib atk at-spi2-atk cups-libs gtk3 libXScrnSaver nss libxkbcommon libxcb
else
  echo "Gestionnaire de paquets non reconnu. Installez aria2 et les dépendances Playwright manuellement."
fi

echo "==> Création d'un environnement virtuel et activation"
python -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate

echo "==> Mise à jour pip et installation des dépendances Python"
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "==> Installation des navigateurs Playwright"
playwright install --with-deps chromium

echo "Setup terminé. Activez le venv via 'source venv/bin/activate' si nécessaire."
