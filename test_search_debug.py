import sys
import time
from typing import List, Dict

from magia_stream.config import Config
from magia_stream.scraper import Scraper

def test_search():
    cfg = Config.from_env()
    scraper = Scraper(cfg)
    
    try:
        scraper.browser_manager.start()
        print("[DEBUG] Browser started")
        
        with scraper.browser_manager.get_page() as page:
            print("[DEBUG] Page acquired")
            base_url = getattr(scraper.config, "BASE_URL", "https://voir-anime.to").rstrip("/")
            
            print(f"[DEBUG] Navigating to {base_url}/")
            scraper.browser_manager.goto_with_retry(page, f"{base_url}/", timeout=30000)
            time.sleep(2)
            
            # Count visible a tags
            existing_hrefs = set()
            try:
                for a in page.query_selector_all('a[href*="/anime/"]'):
                    if a.is_visible():
                        href = (a.get_attribute("href") or "").strip()
                        if href:
                            existing_hrefs.add(href)
            except Exception as e:
                print(f"[DEBUG] Error reading existing hrefs: {e}")
                
            print(f"[DEBUG] Found {len(existing_hrefs)} existing visible anime links")
            
            # Look for input
            search_selector = None
            inputs = page.query_selector_all("input")
            print(f"[DEBUG] Found {len(inputs)} input elements on the page")
            for i, inp in enumerate(inputs):
                placeholder = inp.get_attribute("placeholder") or ""
                name = inp.get_attribute("name") or ""
                inp_id = inp.get_attribute("id") or ""
                cls = inp.get_attribute("class") or ""
                print(f"  Input {i}: name='{name}', placeholder='{placeholder}', id='{inp_id}', class='{cls}'")
            
            for selector in ["input[placeholder*='VF']:visible", "input[placeholder*='vf']:visible", ".search-input:visible", "input[name='s']:visible"]:
                try:
                    if page.query_selector(selector):
                        search_selector = selector
                        print(f"[DEBUG] Chose selector: {search_selector}")
                        break
                except Exception:
                    continue
                    
            if not search_selector:
                print("[DEBUG] No search selector found!")
                return
                
            # Type
            print(f"[DEBUG] Typing 'wistoria' into {search_selector}")
            page.locator(search_selector).first.type("wistoria", delay=150)
            time.sleep(3)
            
            # Check new links
            anchors = page.query_selector_all('a[href*="/anime/"]')
            print(f"[DEBUG] Found {len(anchors)} total anime links after typing")
            
            results = []
            for anchor in anchors:
                try:
                    if not anchor.is_visible():
                        continue
                        
                    href = (anchor.get_attribute("href") or "").strip()
                    text = (anchor.inner_text() or "").strip()
                    
                    if href and text:
                        print(f"[DEBUG AFTER TYPE] text='{text}' | href='{href}' | in_existing={href in existing_hrefs}")
                        if href not in existing_hrefs:
                            slug = scraper._extract_slug_from_page_url(href)
                            print(f"  [NEW LINK] slug='{slug}'")
                            if slug and len(text) > 2:
                                if not any(r["slug"] == slug for r in results):
                                    clean_title = text.split('\n')[0].strip()
                                    results.append({"title": clean_title, "url": href, "slug": slug})
                except Exception as e:
                    print(f"  [ERROR parsing anchor]: {e}")
                    continue
                    
            print(f"[DEBUG] Final results: {results}")

    finally:
        scraper.browser_manager.stop()
        print("[DEBUG] Browser stopped")

if __name__ == "__main__":
    test_search()
