from magia_stream.config import Config
from magia_stream.scraper import Scraper

cfg = Config.from_env()
with Scraper(cfg) as s:
    results = s.search_series_all_results("wistoria")
    print("RESULTS:", results)
