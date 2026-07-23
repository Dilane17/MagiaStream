"""Registre des extracteurs d'hébergeurs vidéo."""

from __future__ import annotations

from typing import List, Optional, Any
from magia_stream.extractors.base import BaseExtractor
from magia_stream.extractors.vidmoly import VidmolyExtractor


class ExtractorRegistry:
    """Gestionnaire et registre central pour tous les extracteurs de flux."""

    def __init__(self) -> None:
        self._extractors: List[BaseExtractor] = [
            VidmolyExtractor(),
        ]

    def register(self, extractor: BaseExtractor) -> None:
        """Enregistre un nouvel extracteur dans le registre."""
        self._extractors.append(extractor)

    def find_extractor(self, url_or_html: str) -> Optional[BaseExtractor]:
        """Trouve le premier extracteur capable de traiter le contenu ou l'URL."""
        for extractor in self._extractors:
            if extractor.can_handle(url_or_html):
                return extractor
        return None

    def extract(self, url_or_html: str, page_or_content: Any, **kwargs: Any) -> Optional[str]:
        """Extrait le flux via l'extracteur approprié si trouvé."""
        extractor = self.find_extractor(url_or_html)
        if extractor:
            return extractor.extract_stream_url(page_or_content, **kwargs)
        return None
