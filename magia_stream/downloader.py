"""Orchestration du téléchargement des épisodes (stub)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from magia_stream.config import Config
from magia_stream.exceptions import DownloadError
from magia_stream.scraper import Scraper
from magia_stream.utils import ensure_directory

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
        """Prépare le téléchargement et retourne le chemin cible (simulé)."""

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
