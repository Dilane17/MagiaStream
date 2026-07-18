"""Utilitaires transverses pour MagiaStream."""

from __future__ import annotations

import logging
from pathlib import Path

DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure le logging standard de l'application."""

    logging.basicConfig(level=level, format=DEFAULT_LOG_FORMAT)


def ensure_directory(path: Path) -> Path:
    """Crée le dossier cible si nécessaire et le retourne."""

    path.mkdir(parents=True, exist_ok=True)
    return path
