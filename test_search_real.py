from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://voir-anime.to/?s=wistoria")
    
    links = page.query_selector_all('a[href*="/anime/"]')
    for a in links:
        href = a.get_attribute("href")
        text = a.inner_text().strip()
        if href and "wistoria" in href.lower() and text:
            print(f"TEXT: {text} | HREF: {href}")
            
    browser.close()
