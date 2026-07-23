from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://voir-anime.to/")
    page.wait_for_timeout(2000)
    
    inputs = page.query_selector_all("input")
    for idx, inp in enumerate(inputs):
        print(f"[{idx}] name={inp.get_attribute('name')} placeholder={inp.get_attribute('placeholder')} id={inp.get_attribute('id')}")

    # Let's try typing in the VF search bar
    # usually VF search bar might be the second one? Or has placeholder containing 'VF'
    vf_input = page.query_selector("input[placeholder*='VF']")
    if vf_input:
        vf_input.fill("wistoria")
        page.wait_for_timeout(3000)
        # find the dropdown
        results = page.query_selector_all("div.search-results a, ul.search-results a, div.live-search a, .ajax-search-results a")
        print(f"Found {len(results)} dropdown results using generic selectors")
        
    browser.close()
