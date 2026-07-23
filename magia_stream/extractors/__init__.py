"""Package d'extracteurs pour hébergeurs vidéo (Vidmoly, Sibnet, Voe, etc.)."""

from magia_stream.extractors.base import BaseExtractor
from magia_stream.extractors.registry import ExtractorRegistry

__all__ = ["BaseExtractor", "ExtractorRegistry"]
