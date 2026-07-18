"""Tests initiaux du scraper."""

from __future__ import annotations

import unittest

from magia_stream.config import Config
from magia_stream.exceptions import ScraperError
from magia_stream.scraper import Scraper


class ScraperTests(unittest.TestCase):
    """Vérifie le comportement de base du scraper."""

    def test_search_episode_not_implemented(self) -> None:
        scraper = Scraper(config=Config())

        with self.assertRaises(ScraperError):
            scraper.search_episode(serie="Test", saison=1, episode=1)
