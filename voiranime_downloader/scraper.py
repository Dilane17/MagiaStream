"""Accès réseau et extraction des informations de streaming."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from voiranime_downloader.config import Config
from voiranime_downloader.exceptions import ScraperError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Scraper:
    """Encapsule la logique de récupération des métadonnées."""

    config: Config

    def search_episode(self, serie: str, saison: int, episode: int) -> dict[str, str]:
        """Retourne un squelette de données pour un épisode donné."""

        logger.debug(
            "Recherche d'épisode: serie=%s saison=%s episode=%s",
            serie,
            saison,
            episode,
        )
        raise ScraperError("Le scraper n'est pas encore implémenté.")
