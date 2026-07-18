"""Point d'entrée CLI de MagiaStream."""

from __future__ import annotations

import logging
from typing import Optional

import typer
from rich.console import Console

from magia_stream.config import Config
from magia_stream.downloader import Downloader
from magia_stream.scraper import Scraper
from magia_stream.utils import setup_logging

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

    cfg = Config.from_env()
    level = getattr(logging, cfg.log_level.upper(), logging.INFO)
    setup_logging(level=level, log_file=cfg.temp_dir / "magia.log", json_format=cfg.log_json)

    scraper = Scraper(config=cfg)
    downloader = Downloader(config=cfg, scraper=scraper)

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
