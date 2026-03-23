import urllib.request, json, urllib.error
req = urllib.request.Request('http://localhost:8000/assess/agentic', data=json.dumps({'borrower_id': 'borrower_001'}).encode('utf-8'), headers={'Content-Type': 'application/json'})
try:
    resp = urllib.request.urlopen(req)
    print(resp.read().decode())
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}:\n{e.read().decode()}")
