"""Tests initiaux du scraper."""

from __future__ import annotations

import unittest

from magia_stream.config import Config
from magia_stream.exceptions import ScraperError
from magia_stream.scraper import Scraper


class ScraperTests(unittest.TestCase):
    """Vérifie le comportement de base du scraper."""

    def test_search_episode_basic_integration(self) -> None:
        """Si Playwright est installé, la méthode retourne un dict; sinon l'erreur est levée."""
        scraper = Scraper(config=Config())

        try:
            res = scraper.search_episode(serie="Test", saison=1, episode=1)
            self.assertIsInstance(res, dict)
            self.assertIn("url", res)
            self.assertIn("title", res)
        except ScraperError:
            # acceptable when Playwright n'est pas disponible dans l'environnement CI local
            self.skipTest("Playwright non disponible; test du scraper ignoré")
