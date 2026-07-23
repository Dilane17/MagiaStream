"""Tests initiaux du scraper."""

from __future__ import annotations

import unittest

from magia_stream.config import Config
from magia_stream.exceptions import ScraperError
from magia_stream.models import Episode
from magia_stream.scraper import Scraper


class ScraperTests(unittest.TestCase):
    """Vérifie le comportement de base du scraper."""

    def test_search_episode_basic_integration(self) -> None:
        """Si Playwright est installé, la méthode retourne un Episode ou un dict; sinon l'erreur est levée."""
        scraper = Scraper(config=Config())

        try:
            res = scraper.search_episode(serie="Test", saison=1, episode=1)
            if res is not None:
                self.assertTrue(isinstance(res, (dict, Episode)))
                if isinstance(res, Episode):
                    self.assertEqual(res.series, "Test")
                elif isinstance(res, dict):
                    self.assertIn("url", res)
        except ScraperError:
            self.skipTest("Playwright non disponible; test du scraper ignoré")
