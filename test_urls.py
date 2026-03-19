#!/usr/bin/env python3
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

url = 'https://www.dropbox.com/scl/fi/com7w5jltbmr3winc0cle/outlet_id_record.xlsx?rlkey=904zfoniyg3yksb5xg4g9cxq5&dl=0'

# Convert to dl=1
parsed = urlparse(url)
query = dict(parse_qsl(parsed.query, keep_blank_values=True))
query["dl"] = "1"
direct_url = urlunparse(parsed._replace(query=urlencode(query)))

print(f"Original URL: {url}")
print(f"Direct URL (dl=1): {direct_url}")

try:
    req = Request(direct_url, headers={"User-Agent": "network-webapp/1.0"})
    response = urlopen(req, timeout=10)
    content_type = response.headers.get("Content-Type", "")
    print(f"✓ URL is accessible")
    print(f"  Content-Type: {content_type}")
    print(f"  Content-Length: {response.headers.get('Content-Length', 'unknown')} bytes")
    response.close()
except Exception as e:
    print(f"✗ URL is NOT accessible: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
