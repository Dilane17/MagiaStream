"""Accès réseau et extraction des informations de streaming (stub)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from magia_stream.config import Config
from magia_stream.exceptions import ScraperError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Scraper:
    """Encapsule la logique de récupération des métadonnées."""

    config: Config

    def search_episode(self, serie: str, saison: int, episode: int) -> dict[str, str]:
        """Retourne un squelette de données pour un épisode donné (stub).

        Remplacer par une implémentation Playwright dans Phase 2.
        """

        logger.debug(
            "Recherche d'épisode: serie=%s saison=%s episode=%s",
            serie,
            saison,
            episode,
        )
        raise ScraperError("Le scraper n'est pas encore implémenté.")
