"""Service principal d'orchestration pour MagiaStream (StreamEngine)."""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from magia_stream.config import Config
from magia_stream.downloader import Downloader
from magia_stream.models import Episode
from magia_stream.scrapers.voiranime import VoirAnimeScraper

logger = logging.getLogger(__name__)


class StreamEngine:
    """Orchestrateur centralisant le scraping, la résolution de flux et le téléchargement."""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config.from_env()
        self.scraper = VoirAnimeScraper(config=self.config)
        self.downloader = Downloader(config=self.config)

    def search_series(self, query: str) -> Optional[str]:
        """Recherche l'URL d'une série par son nom."""
        return self.scraper._search_series_page_url(query)

    def get_available_episodes(self, serie: str, saison: int) -> List[int]:
        """Récupère la liste des épisodes disponibles pour une saison donnée."""
        return self.scraper.get_episodes_list(serie, saison)

    def fetch_episode(
        self,
        serie: str,
        saison: int,
        episode: int,
        resolution: Optional[str] = None,
        trace: bool = False,
    ) -> Optional[Episode]:
        """Extrait les métadonnées et l'URL d'un épisode."""
        return self.scraper.search_episode(
            serie=serie,
            saison=saison,
            episode=episode,
            resolution=resolution,
            trace=trace,
        )

    def download_episode(
        self,
        episode: Episode,
        output_dir: Optional[Any] = None,
    ) -> int:
        """Lance le téléchargement d'un épisode via aria2c/ffmpeg."""
        from pathlib import Path
        out_dir = Path(output_dir) if output_dir else Path.cwd()
        out_name = f"{episode.series}_S{episode.season:02d}E{episode.episode:02d}.mp4"
        output_path = out_dir / out_name
        
        stream_url = getattr(episode, "stream_url", "")
        if not stream_url:
            return 1
            
        headers = getattr(episode, "headers", {})
        return self.downloader.download_stream(stream_url, str(output_path), headers=headers)
