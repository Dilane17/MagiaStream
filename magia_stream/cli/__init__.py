"""Package CLI de MagiaStream."""

from magia_stream.cli import commands
from magia_stream.cli.commands import app, run, Scraper, Downloader

__all__ = ["app", "run", "Scraper", "Downloader"]
