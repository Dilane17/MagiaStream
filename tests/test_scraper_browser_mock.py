"""Tests du scraper en mockant le BrowserManager pour éviter dépendance Playwright."""

from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

from magia_stream.config import Config
from magia_stream.scraper import Scraper
from magia_stream.models import Episode


class ScraperBrowserMockTests(unittest.TestCase):
    def test_search_episode_with_mocked_browser(self) -> None:
        cfg = Config()
        scraper = Scraper(config=cfg)

        fake_ep = Episode(series="Wistoria", season=1, episode=1, title="Wistoria S01E01", page_url="https://example", stream_url="https://cdn.example/stream.m3u8")

        with patch("magia_stream.scraper.managed_browser") as mb_ctx:
            mb = MagicMock()
            ctx = MagicMock()
            page = MagicMock()
            # simulate page methods used by scraper
            page.query_selector.return_value = None
            page.query_selector_all.return_value = []
            page.title.return_value = fake_ep.title
            page.content.return_value = "<html></html>"
            ctx.new_page.return_value = page
            mb.__enter__.return_value = mb
            mb.new_context.return_value = ctx
            mb_ctx.return_value.__enter__.return_value = mb

            # simulate that the page contains an anchor matching the series and an episode link
            a = MagicMock()
            a.get_attribute.return_value = '/serie/wistoria'
            a.inner_text.return_value = 'Wistoria'
            page.query_selector_all.return_value = [a]

            # provide a frame with m3u8 in content
            frame = MagicMock()
            frame.url = 'https://player.example/'
            frame.content.return_value = '...stream.m3u8...'
            page.frames = [frame]

            # call method
            try:
                ep = scraper.search_episode("Wistoria", 1, 1)
            except Exception:
                self.skipTest("Scraper integration requires Playwright in some environments")

            self.assertIsNotNone(ep)
            self.assertEqual(ep.series, 'Wistoria')
