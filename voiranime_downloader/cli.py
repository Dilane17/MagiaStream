"""Point d'entrée CLI de MagiaStream."""

from __future__ import annotations

import logging
from typing import Optional

import typer
from rich.console import Console

from voiranime_downloader.config import Config
from voiranime_downloader.downloader import Downloader
from voiranime_downloader.scraper import Scraper
from voiranime_downloader.utils import setup_logging

app = typer.Typer(help="CLI MagiaStream pour orchestrer le téléchargement d'épisodes.")
console = Console()
logger = logging.getLogger(__name__)


@app.command()
def download(
    serie: str = typer.Option(..., "--serie", help="Nom de la série à télécharger."),
    saison: int = typer.Option(1, "--saison", min=1, help="Numéro de saison."),
    episode: int = typer.Option(..., "--episode", min=1, help="Numéro d'épisode."),
    resolution: Optional[str] = typer.Option(
        None,
        "--resolution",
        help="Résolution cible, par exemple 720p ou 1080p.",
    ),
) -> None:
    """Télécharge un épisode à partir des paramètres fournis."""

    setup_logging()
    config = Config()
    scraper = Scraper(config=config)
    downloader = Downloader(config=config, scraper=scraper)

    try:
        result = downloader.download_episode(
            serie=serie,
            saison=saison,
            episode=episode,
            resolution=resolution,
        )
    except Exception as exc:  # pragma: no cover - remonte au CLI
        logger.exception("Échec du téléchargement")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Téléchargement terminé :[/green] {result}")


def main() -> None:
    """Lance l'interface CLI."""

    app()
