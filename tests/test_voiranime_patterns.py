"""Tests pour les motifs d'URLs d'épisodes et les configurations anti-bot."""

from __future__ import annotations

import unittest
from magia_stream.config import Config
from magia_stream.scrapers.voiranime import VoirAnimeScraper


class VoirAnimePatternsTests(unittest.TestCase):
    def test_series_page_patterns_3digit_padding_and_slug_cleaning(self) -> None:
        scraper = VoirAnimeScraper(config=Config())
        patterns = scraper._series_page_patterns("https://voir-anime.to", "bleach-vf", 29)

        # Vérifier que le format 29, 029 et bleach (sans -vf) sont présents dans les motifs
        self.assertIn("https://voir-anime.to/anime/bleach-vf/bleach-29-vf/", patterns)
        self.assertIn("https://voir-anime.to/anime/bleach-vf/bleach-029-vf/", patterns)
        self.assertIn("https://voir-anime.to/anime/bleach-vf/bleach-vf-29-vf/", patterns)
        self.assertIn("https://voir-anime.to/anime/bleach-vf/episode-29/", patterns)

    def test_config_proxy_and_delays(self) -> None:
        cfg = Config(HTTP_PROXY="http://proxy.local:8080", REQUEST_DELAY_MIN=2.0, REQUEST_DELAY_MAX=4.0)
        self.assertEqual(cfg.HTTP_PROXY, "http://proxy.local:8080")
        self.assertEqual(cfg.REQUEST_DELAY_MIN, 2.0)
        self.assertEqual(cfg.REQUEST_DELAY_MAX, 4.0)

        scraper = VoirAnimeScraper(config=cfg)
        self.assertEqual(scraper.config.HTTP_PROXY, "http://proxy.local:8080")


    def test_score_autocomplete_result(self) -> None:
        scraper = VoirAnimeScraper(config=Config())
        score_official = scraper._score_autocomplete_result("bleach", "Bleach (VF)", "bleach-vf")
        score_kai = scraper._score_autocomplete_result("bleach", "Bleach Kai (VF)", "bleach-kai-vf")
        score_movie = scraper._score_autocomplete_result("bleach", "Bleach Film 1", "bleach-memories-of-nobody-vf")

        # La série officielle doit avoir le score le plus élevé (Match exact / Priorité absolue)
        self.assertGreater(score_official, score_kai)
        self.assertGreater(score_official, score_movie)
        self.assertEqual(score_official, 100)


if __name__ == "__main__":
    unittest.main()
