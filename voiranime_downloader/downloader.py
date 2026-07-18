"""Orchestration du téléchargement des épisodes."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from voiranime_downloader.config import Config
from voiranime_downloader.exceptions import DownloadError
from voiranime_downloader.scraper import Scraper
from voiranime_downloader.utils import ensure_directory

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Downloader:
    """Coordonne la résolution de l'URL et le téléchargement final."""

    config: Config
    scraper: Scraper

    def download_episode(
        self,
        serie: str,
        saison: int,
        episode: int,
        resolution: Optional[str] = None,
    ) -> Path:
        """Prépare le téléchargement et retourne le chemin cible."""

        try:
            metadata = self.scraper.search_episode(serie=serie, saison=saison, episode=episode)
            logger.info("Métadonnées résolues: %s", metadata)
        except Exception as exc:
            raise DownloadError("Impossible de résoudre l'épisode demandé.") from exc

        output_directory = ensure_directory(self.config.output_dir)
        filename = f"{serie}-s{saison:02d}-e{episode:02d}"
        if resolution:
            filename = f"{filename}-{resolution}"

        output_path = output_directory / f"{filename}.mp4"
        logger.info("Téléchargement simulé vers %s", output_path)
        return output_path
