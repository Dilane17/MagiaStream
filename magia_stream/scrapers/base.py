"""Interface de base pour les scrapers de sites d'animes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional
from magia_stream.models import Episode


class BaseScraper(ABC):
    """Classe abstraite de référence pour tout scraper de source d'anime."""

    @abstractmethod
    def search_episode(
        self,
        serie: str,
        saison: int,
        episode: int,
        resolution: Optional[str] = None,
        trace: bool = False,
    ) -> Optional[Episode]:
        """Recherche et retourne un épisode unique."""
        pass

    @abstractmethod
    def get_episodes_list(
        self,
        serie: str,
        saison: int,
    ) -> List[int]:
        """Retourne la liste des numéros d'épisodes disponibles pour une saison."""
        pass
