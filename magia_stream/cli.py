"""Point d'entrée CLI de MagiaStream."""

from __future__ import annotations

import logging
import sys
from typing import Optional, List

try:
    import typer  # type: ignore
    HAS_TYPER = True
except Exception:
    typer = None  # type: ignore
    HAS_TYPER = False

try:
    from rich.console import Console
except Exception:
    class Console:  # pragma: no cover - fallback
        def print(self, *args, **kwargs):
            print(*args)

from magia_stream.config import Config
from magia_stream.downloader import Downloader
from magia_stream.scraper import Scraper
from magia_stream.utils import setup_logging

app = typer.Typer(help="CLI MagiaStream pour orchestrer le téléchargement d'épisodes.") if HAS_TYPER else None
console = Console()
logger = logging.getLogger(__name__)


def _load_config(config_file: Optional[str]) -> Config:
    if config_file:
        # support for passing a custom .env file path
        from dotenv import load_dotenv

        load_dotenv(config_file)
    return Config.from_env()


def _configure_global(verbose: bool, config_file: Optional[str]) -> Config:
    """Charge la configuration et configure le logging global.

    Utilisé par Typer et par le fallback minimal.
    """

    cfg = _load_config(config_file)
    level = logging.DEBUG if verbose else getattr(logging, cfg.LOG_LEVEL.upper(), logging.INFO)
    setup_logging(level=level, log_file=cfg.TEMP_DIR / "magia.log", json_format=cfg.LOG_JSON)
    return cfg


if HAS_TYPER:
    @app.callback(invoke_without_command=True)
    def main(
        ctx: typer.Context,
        verbose: bool = typer.Option(False, "--verbose", help="Augmente le niveau de log."),
        config_file: Optional[str] = typer.Option(None, "--config-file", help="Chemin vers un .env personnalisé."),
    ) -> None:
        """Contexte global de l'application. Configure logging et charge la config."""

        cfg = _configure_global(verbose, config_file)
        ctx.obj = cfg


if HAS_TYPER:
    @app.command()
    def download(
        ctx: typer.Context,
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

        cfg: Config = ctx.obj or Config.from_env()
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
else:
    def download_fallback(argv: List[str]) -> None:
        """Fallback minimal pour 'download' si `typer` n'est pas installé.

        Supporte: --serie, --saison, --episode, --resolution (simple parsing).
        """

        import argparse

        parser = argparse.ArgumentParser(prog="magia download")
        parser.add_argument("--serie", required=True)
        parser.add_argument("--saison", type=int, default=1)
        parser.add_argument("--episode", type=int, required=True)
        parser.add_argument("--resolution", default=None)
        args = parser.parse_args(argv)

        cfg = _configure_global(verbose=False, config_file=None)
        scraper = Scraper(config=cfg)
        downloader = Downloader(config=cfg, scraper=scraper)

        try:
            result = downloader.download_episode(
                serie=args.serie, saison=args.saison, episode=args.episode, resolution=args.resolution
            )
        except Exception as exc:
            logger.exception("Échec du téléchargement")
            sys.exit(1)

        console.print(f"Téléchargement terminé : {result}")
    


if HAS_TYPER:
    @app.command(name="config")
    def config_show(ctx: typer.Context) -> None:
        """Affiche la configuration effective."""

        cfg: Config = ctx.obj or Config.from_env()
        for k, v in cfg.to_dict().items():
            console.print(f"[bold]{k}[/bold]: {v}")
else:
    def config_show_fallback() -> None:
        cfg = _configure_global(verbose=False, config_file=None)
        for k, v in cfg.to_dict().items():
            console.print(f"{k}: {v}")


if __name__ == "__main__":
    if HAS_TYPER:
        app()
    else:
        # minimal fallback: parse args to support --help, config show, download
        argv = sys.argv[1:]
        if not argv or "--help" in argv or "-h" in argv:
            console.print("MagiaStream (fallback) - fonctionnalités limitées:\n  config show\n  download --serie NAME --episode N [--saison N] [--resolution R]")
            sys.exit(0)

        if argv[0] == "config" and len(argv) > 1 and argv[1] == "show":
            config_show_fallback()
            sys.exit(0)

        if argv[0] == "download":
            download_fallback(argv[1:])
            sys.exit(0)

        console.print(f"Commande inconnue: {' '.join(argv)}")
        sys.exit(2)
