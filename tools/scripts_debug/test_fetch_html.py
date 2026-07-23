from urllib.request import urlopen, Request
req = Request("https://voir-anime.to/", headers={"User-Agent": "Mozilla/5.0"})
try:
    html = urlopen(req).read().decode('utf-8')
    import re
    # look for search forms or inputs
    for line in html.split('\n'):
        if 'input' in line and 'search' in line.lower() or 'vostfr' in line.lower() or 'vf' in line.lower():
            print(line.strip())
except Exception as e:
    print(e)
