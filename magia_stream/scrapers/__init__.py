"""Package de scrapers pour sites d'animes/streaming."""

from magia_stream.scrapers.base import BaseScraper
from magia_stream.scrapers.voiranime import VoirAnimeScraper

__all__ = ["BaseScraper", "VoirAnimeScraper"]
