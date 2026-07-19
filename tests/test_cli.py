import json
import os
import pytest
from typer.testing import CliRunner
from magia_stream.cli import app
from magia_stream.models import Episode

runner = CliRunner()

@pytest.fixture
def mock_scraper(mocker):
    # Mock des méthodes du Scraper pour éviter Playwright
    scraper_mock = mocker.patch("magia_stream.cli.Scraper")
    
    # Configuration du comportement de l'instance
    instance = scraper_mock.return_value
    instance.get_episodes_list.return_value = [1, 2, 3]
    instance._search_series_page_url.return_value = "https://voir-anime.to/anime/test-serie-vf/"
    instance._extract_slug_from_page_url.return_value = "test-serie-vf"
    
    # Mock de la méthode de recherche d'épisode
    def mock_search(serie, saison, episode, resolution, trace=False):
        if episode > 3:
            return None
        return Episode(
            series=serie,
            season=saison,
            episode=episode,
            page_url="https://fake",
            raw_url="https://fake/raw",
            stream_url="https://fake/stream.m3u8",
            headers={"User-Agent": "test", "Referer": "https://fake"}
        )
    instance.search_episode.side_effect = mock_search
    
    return instance

@pytest.fixture
def mock_downloader(mocker):
    # Mock du Downloader pour éviter l'appel à aria2c
    dl_mock = mocker.patch("magia_stream.cli.Downloader")
    instance = dl_mock.return_value
    instance.download_stream.return_value = 0  # Succès
    return instance

def test_list_command(mock_scraper):
    result = runner.invoke(app, ["list", "Wistoria", "--saison", "1"])
    assert result.exit_code == 0
    assert "Recherche des épisodes pour la série 'Wistoria'" in result.stdout
    assert mock_scraper.get_episodes_list.called

def test_search_command(mock_scraper):
    result = runner.invoke(app, ["search", "One Piece"])
    assert result.exit_code == 0
    assert "URL : https://voir-anime.to/anime/test-serie-vf/" in result.stdout
    assert "Slug officiel à utiliser : test-serie-vf" in result.stdout
    assert mock_scraper._search_series_page_url.called

def test_batch_command(mock_scraper, mock_downloader, tmp_path):
    # Création d'un fichier de batch temporaire
    batch_file = tmp_path / "test_jobs.json"
    jobs = [
        {
            "serie": "TestSerie",
            "saison": 1,
            "range": "1-2"
        }
    ]
    batch_file.write_text(json.dumps(jobs))
    
    result = runner.invoke(app, ["batch", str(batch_file)])
    
    assert result.exit_code == 0
    assert "Démarrage du batch avec 1 tâche(s)." in result.stdout
    assert "Traitement de la tâche 1/1 : TestSerie (Saison 1)" in result.stdout
    assert "Épisodes planifiés : [1, 2]" in result.stdout
    
    # Vérifie que search_episode a été appelé 2 fois (pour les épisodes 1 et 2)
    assert mock_scraper.search_episode.call_count == 2
    
    # Vérifie que le downloader a été appelé 2 fois
    print("STDOUT:", result.stdout)
    assert mock_downloader.download_stream.call_count == 2
