"""Déclarations des commandes Typer pour MagiaStream CLI."""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Any

try:
    import typer
    HAS_TYPER = True
except Exception:
    typer = None  # type: ignore
    HAS_TYPER = False

from magia_stream.config import Config
from magia_stream.downloader import Downloader
from magia_stream.scraper import Scraper
from magia_stream.utils import setup_logging
from magia_stream.cli.ui import console, HAS_RICH
from magia_stream.cli.wizard import run_interactive_wizard

logger = logging.getLogger(__name__)

app: Any = typer.Typer(help="CLI MagiaStream pour orchestrer le téléchargement d'épisodes.") if HAS_TYPER else None
config_app: Any = typer.Typer() if HAS_TYPER else None
if HAS_TYPER:
    app.add_typer(config_app, name="config")


def _get_scraper(cfg: Config) -> Any:
    import magia_stream.cli
    return getattr(magia_stream.cli, "Scraper", Scraper)(config=cfg)


def _get_downloader(cfg: Config) -> Any:
    import magia_stream.cli
    return getattr(magia_stream.cli, "Downloader", Downloader)(config=cfg)


def _load_config(config_file: Optional[str]) -> Config:
    if config_file:
        from dotenv import load_dotenv
        load_dotenv(config_file)
    return Config.from_env()


def _configure_global(verbose: bool, config_file: Optional[str]) -> Config:
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
        cfg = _configure_global(verbose, config_file)
        ctx.obj = cfg


if HAS_TYPER:
    @app.command()
    def download(
        ctx: typer.Context,
        serie: str = typer.Option(..., "--serie", help="Nom de la série à télécharger."),
        saison: int = typer.Option(1, "--saison", min=1, help="Numéro de saison."),
        episode: Optional[int] = typer.Option(None, "--episode", min=1, help="Numéro d'épisode."),
        all_episodes: bool = typer.Option(False, "--all", help="Télécharge tous les épisodes."),
        range_episodes: Optional[str] = typer.Option(None, "--range", help="Plage d'épisodes, ex: 1-5"),
        resolution: Optional[str] = typer.Option(None, "--resolution", help="Résolution cible, par exemple 720p ou 1080p."),
        dry_run: bool = typer.Option(False, "--dry-run", help="Ne fait que simuler la résolution de l'épisode."),
        trace: bool = typer.Option(False, "--trace", help="Affiche les URLs visitées et les requêtes captées."),
    ) -> None:
        cfg: Config = ctx.obj or Config.from_env()
        scraper = _get_scraper(cfg)
        downloader = _get_downloader(cfg)

        episodes_to_download: List[int] = []
        if all_episodes:
            found = scraper.get_episodes_list(serie=serie, saison=saison)
            if not found:
                console.print(f"[red]Aucun épisode trouvé pour {serie} S{saison}.[/red]")
                raise typer.Exit(code=1)
            episodes_to_download = found
        elif range_episodes:
            try:
                parts = range_episodes.split("-")
                if len(parts) == 2:
                    episodes_to_download = list(range(int(parts[0]), int(parts[1]) + 1))
                else:
                    episodes_to_download = [int(p.strip()) for p in range_episodes.split(",")]
            except Exception:
                console.print(f"[red]Plage d'épisodes invalide : {range_episodes}[/red]")
                raise typer.Exit(code=1)
        elif episode is not None:
            episodes_to_download = [episode]
        else:
            console.print("[red]Veuillez spécifier --episode, --range ou --all.[/red]")
            raise typer.Exit(code=1)

        out_dir = Path(cfg.OUTPUT_DIR) / serie

        for ep_num in episodes_to_download:
            out_name = f"S{saison:02d}E{ep_num:02d}.mp4"
            output_path = out_dir / out_name

            if output_path.exists() and output_path.stat().st_size > 0:
                console.print(f"[green]✔ L'épisode {ep_num} existe déjà. Ignoré.[/green]")
                continue

            try:
                ep_obj = scraper.search_episode(serie=serie, saison=saison, episode=ep_num, resolution=resolution, trace=trace)
                if not ep_obj or not getattr(ep_obj, "stream_url", None):
                    console.print(f"[red]Aucun flux trouvé pour S{saison}E{ep_num}.[/red]")
                    continue

                if dry_run:
                    console.print(f"[yellow][DRY RUN] Flux trouvé pour S{saison}E{ep_num} : {ep_obj.stream_url}[/yellow]")
                    continue

                out_dir.mkdir(parents=True, exist_ok=True)
                ret = downloader.download_stream(ep_obj.stream_url if hasattr(ep_obj, 'stream_url') else ep_obj, output_path, headers=getattr(ep_obj, 'headers', {}))
                if ret != 0:
                    console.print(f"[red]Échec du téléchargement (code={ret}) pour l'épisode {ep_num}[/red]")
                    continue

                console.print(f"[green]✔ Téléchargement réussi : {output_path}[/green]")
            except Exception as e:
                console.print(f"[red]Erreur lors du traitement de S{saison}E{ep_num} : {e}[/red]")

    @app.command("search")
    def search_command(
        ctx: typer.Context,
        serie: str = typer.Argument(..., help="Nom de la série à rechercher."),
        trace: bool = typer.Option(False, "--trace", help="Affiche les détails de recherche."),
    ) -> None:
        cfg: Config = ctx.obj or Config.from_env()
        scraper = _get_scraper(cfg)

        console.print(f"[cyan]Recherche de la série '{serie}'...[/cyan]")
        url = scraper._search_series_page_url(serie)

        if url:
            slug = scraper._extract_slug_from_page_url(url)
            console.print(f"[bold green]✔ Série trouvée ![/bold green]")
            console.print(f"URL : {url}")
            console.print(f"Slug officiel à utiliser : {slug}")
        else:
            console.print(f"[red]Aucune série trouvée pour '{serie}'.[/red]")

    @app.command("list")
    def list_command(
        ctx: typer.Context,
        serie: str = typer.Argument(..., help="Nom ou slug de la série."),
        saison: int = typer.Option(1, "--saison", help="Numéro de la saison."),
    ) -> None:
        cfg: Config = ctx.obj or Config.from_env()
        scraper = _get_scraper(cfg)

        console.print(f"[cyan]Recherche des épisodes pour la série '{serie}'...[/cyan]")
        episodes = scraper.get_episodes_list(serie=serie, saison=saison)

        if episodes:
            console.print(f"[bold green]✔ Épisodes disponibles ({len(episodes)}) :[/bold green]")
            console.print(f"{episodes}")
        else:
            console.print(f"[yellow]Aucun épisode trouvé pour {serie} S{saison}.[/yellow]")

    @app.command("batch")
    def batch_command(
        ctx: typer.Context,
        file: Path = typer.Argument(..., help="Chemin vers le fichier JSON contenant la liste des séries/épisodes."),
    ) -> None:
        cfg: Config = ctx.obj or Config.from_env()
        if not file.exists():
            console.print(f"[red]Fichier introuvable : {file}[/red]")
            raise typer.Exit(code=1)

        with open(file, "r", encoding="utf-8") as f:
            jobs = json.load(f)

        scraper = _get_scraper(cfg)
        downloader = _get_downloader(cfg)

        console.print(f"[bold cyan]Démarrage du batch avec {len(jobs)} tâche(s).[/bold cyan]")
        try:
            for i, job in enumerate(jobs, 1):
                serie = job.get("serie")
                saison = job.get("saison", 1)
                resolution = job.get("resolution", "1080p")
                all_episodes = job.get("all", False)
                range_episodes = job.get("range", None)
                episode = job.get("episode", None)

                episodes_to_download: List[int] = []
                console.print(
                    f"\n[bold magenta]Traitement de la tâche {i}/{len(jobs)} : {serie} (Saison {saison})[/bold magenta]"
                )

                if all_episodes:
                    found = scraper.get_episodes_list(serie=serie, saison=saison)
                    if not found:
                        console.print(f"[red]Aucun épisode trouvé pour la série {serie}.[/red]")
                        continue
                    episodes_to_download = found
                elif range_episodes:
                    try:
                        parts = str(range_episodes).split("-")
                        if len(parts) == 2:
                            episodes_to_download = list(range(int(parts[0]), int(parts[1]) + 1))
                        else:
                            episodes_to_download = [int(p.strip()) for p in str(range_episodes).split(",")]
                    except Exception:
                        console.print(f"[red]Format de range invalide pour {serie}.[/red]")
                        continue
                elif episode is not None:
                    episodes_to_download = [int(episode)]
                else:
                    console.print(f"[red]Tâche {i} ignorée : aucune stratégie spécifiée.[/red]")
                    continue

                console.print(f"[cyan]Épisodes planifiés : {episodes_to_download}[/cyan]")

                for ep_num in episodes_to_download:
                    console.print(f" -> Épisode {ep_num}")
                    ep_obj = scraper.search_episode(
                        serie=serie, saison=saison, episode=ep_num, resolution=resolution
                    )
                    if ep_obj:
                        downloader.download_stream(ep_obj.stream_url if hasattr(ep_obj, 'stream_url') else ep_obj, f"{serie}_S{saison}E{ep_num}.mp4")
        except KeyboardInterrupt:
            raise typer.Exit(code=130)

    @app.command("interactive")
    def interactive_command() -> None:
        cfg = Config.from_env()
        run_interactive_wizard(cfg, download)

    @app.command("update")
    def update_command() -> None:
        console.print("[bold cyan]Recherche de mises à jour pour MagiaStream...[/bold cyan]")
        if shutil.which("pipx"):
            res = subprocess.run(["pipx", "upgrade", "magiastream"])
            if res.returncode == 0:
                console.print("[bold green]Mise à jour réussie ![/bold green]")
            else:
                console.print("[bold red]Erreur lors de la mise à jour via pipx.[/bold red]")
        else:
            res = subprocess.run(["git", "pull"])
            if res.returncode == 0:
                subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."])
                console.print("[bold green]Mise à jour locale réussie ![/bold green]")

    @app.command("setup")
    def setup_command() -> None:
        missing = []
        if not shutil.which("aria2c"):
            missing.append("aria2c")
        if not shutil.which("ffmpeg"):
            missing.append("ffmpeg")

        if missing:
            console.print(f"[bold yellow]⚠️ Dépendances système manquantes : {', '.join(missing)}[/bold yellow]")
        else:
            console.print("[bold green]✔ aria2c et ffmpeg sont bien installés sur votre système.[/bold green]")

        console.print("\n[bold cyan]Installation du navigateur Playwright (Chromium)...[/bold cyan]")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])


def run() -> None:
    if HAS_TYPER:
        if len(sys.argv) == 1:
            sys.argv.append("interactive")
        app()
