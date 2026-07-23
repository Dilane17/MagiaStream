"""Façade de rétrocompatibilité pour la classe Scraper.

Ce module réexporte `VoirAnimeScraper` sous le nom `Scraper` afin d'assurer
une compatibilité totale avec les scripts et tests existants.
"""

from __future__ import annotations

from magia_stream.scrapers.voiranime import VoirAnimeScraper
try:
    from magia_stream.browser import managed_browser
except Exception:
    managed_browser = None  # type: ignore

# Alias de rétrocompatibilité
Scraper = VoirAnimeScraper

__all__ = ["Scraper", "VoirAnimeScraper", "managed_browser"]
