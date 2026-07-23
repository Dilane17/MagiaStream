"""Interface de base pour tous les extracteurs d'hébergeurs vidéo."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Any


class BaseExtractor(ABC):
    """Classe abstraite pour l'extraction de liens HLS / MP4 depuis des hébergeurs vidéo."""

    name: str = "base"

    @abstractmethod
    def can_handle(self, url_or_html: str) -> bool:
        """Vérifie si cet extracteur peut traiter l'URL ou le HTML fourni."""
        pass

    @abstractmethod
    def extract_stream_url(self, page_or_content: Any, **kwargs: Any) -> Optional[str]:
        """Extrait l'URL directe du flux vidéo (.m3u8 ou .mp4)."""
        pass
