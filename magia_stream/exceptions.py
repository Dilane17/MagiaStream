"""Exceptions métiers de MagiaStream."""

from __future__ import annotations


class MagiaStreamError(Exception):
    """Classe de base pour les erreurs du projet."""


class ScraperError(MagiaStreamError):
    """Erreur liée à la récupération ou l'analyse des données."""


class DownloadError(MagiaStreamError):
    """Erreur liée à la préparation ou à l'exécution du téléchargement."""


class ConfigError(MagiaStreamError):
    """Erreur levée lors de la validation de la configuration."""
